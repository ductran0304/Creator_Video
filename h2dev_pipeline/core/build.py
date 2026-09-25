"""Dựng video hoàn chỉnh từ projects/<slug>/scenes.json.

Luồng: TTS từng câu → đo thời lượng thật → dòng thời gian → vẽ từng trạng thái hiện dần →
sinh khung hình (zoom nhẹ theo cảnh + mờ dần khi hiện thành phần mới) đẩy thẳng vào ffmpeg →
trộn thuyết minh + nhạc nền + SFX → MP4, SRT, chapters, thumbnail, metadata YouTube.

Mọi thứ đắt (audio, ảnh cảnh) đều cache theo nội dung trong projects/<slug>/cache/, nên chạy lại sau khi
sửa vài câu/cảnh chỉ làm lại phần thay đổi.
"""
import hashlib
import io
import json
import math
import os
import subprocess
import time

import numpy as np
from PIL import Image

from doodle.scene import scene_svg, render_png, W, H
from . import audio as A
from .project import line_states, scene_seed, final_state, validate
from .tts import synthesize, pick_voice

HIRES = 1.08          # vẽ ảnh cảnh to hơn 8% để zoom nền tối đa vẫn nét
ZOOM_MAX = 1.07       # mức zoom Ken Burns trong một cảnh (toàn cảnh)
FOCUS_MAX = 1.9       # zoom tối đa khi camera đẩy vào cận cảnh (focus)
CAM_S = 0.55          # thời gian camera lướt sang cú máy mới
PUNCH, PUNCH_S = 0.03, 0.45  # cú zoom nhẹ khi hiện vật mới / đổi biểu cảm
FADE_S = 0.18         # chuyển mờ khi hình đổi trong cùng cảnh
CUT_FADE_S = 0.12     # vào/ra B-roll (cut)
LEAD_IN, TAIL = 0.5, 1.5


def _log_time(log, label, t0):
    log(f"  ✓ {label} ({time.time() - t0:.1f}s)")


# ---------------- dòng thời gian ----------------
def build_timeline(project, durations, cfg):
    line_gap = cfg.get("line_gap", 0.25)
    scene_gap = cfg.get("scene_gap", 0.6)
    t = LEAD_IN
    k = 0
    scenes = []
    for si, sc in enumerate(project["scenes"]):
        start = t
        lines = []
        for li, ln in enumerate(sc["lines"]):
            d = durations[k]
            lines.append({"text": ln["text"], "sub": ln.get("sub") or ln["text"], "start": t, "end": t + d,
                          "audio_index": k, "reveal": bool(ln.get("show")),
                          "nosub": bool(sc.get("_auto_outro"))})  # màn kết đã có chữ, không cần phụ đề
            t += d
            k += 1
            t += scene_gap if li == len(sc["lines"]) - 1 else line_gap
        scenes.append({"index": si, "start": start, "lines": lines, "chapter": sc.get("chapter")})
    total = t - scene_gap + TAIL
    for i, s in enumerate(scenes):
        s["end"] = scenes[i + 1]["start"] if i + 1 < len(scenes) else total
    return scenes, total


# ---------------- ảnh từng cú máy ----------------
def _focus_view(box):
    """Khung bao element → (tâm x, tâm y theo tỉ lệ, mức zoom) để element chiếm ~60% chiều cao khung."""
    bw = max(60.0, box["x1"] - box["x0"])
    bh = max(60.0, box["bottom"] - box["top"])
    z = max(1.15, min(FOCUS_MAX, 0.62 * H / bh, 0.72 * W / bw))
    return ((box["x0"] + box["x1"]) / 2 / W, (box["top"] + box["bottom"]) / 2 / H, z)


def render_shots(project, cache_dir, log):
    """Mỗi câu thoại một cú máy: list (theo cảnh) các list dict(path, view, cut, reveal).
    Ảnh vẽ ở độ phân giải đủ cho mức zoom của cú máy (cận cảnh vẽ to hơn để không mờ)."""
    os.makedirs(cache_dir, exist_ok=True)
    result, made, total = [], 0, 0
    for sc in project["scenes"]:
        shots = []
        for st in line_states(sc):
            boxes = {}
            svg = scene_svg(st["spec"], None, st["visible"], st["seed"], boxes)
            view, res = None, HIRES
            if st["focus"] and st["focus"] in boxes:
                view = _focus_view(boxes[st["focus"]])
                res = max(HIRES, view[2] * 1.02)
            p = os.path.join(cache_dir, hashlib.sha1(f"{res:.3f}|{svg}".encode()).hexdigest()[:16] + ".png")
            if not os.path.exists(p):
                with open(p, "wb") as f:
                    f.write(render_png(svg, res))
                made += 1
            total += 1
            shots.append({"path": p, "view": view, "cut": st["cut"], "reveal": st["reveal"]})
        result.append(shots)
    log(f"  vẽ mới {made} ảnh, dùng lại {total - made} ảnh từ cache")
    return result


# ---------------- khung hình ----------------
def _ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(u, 0.0), 1.0))


def _lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


class FrameMaker:
    """Camera ảo: toàn cảnh trôi nhẹ (Ken Burns) theo cảnh; câu có focus thì đẩy vào cận cảnh; câu làm hình
    thay đổi thì có cú zoom nhẹ; đổi ảnh (hiện vật mới / B-roll) thì chuyển mờ rất nhanh."""

    def __init__(self, timeline, shots, size, seed_base=0):
        self.timeline = timeline
        self.shots = shots
        self.size = size
        self._cache = {}
        self.motion = []
        for i, sc in enumerate(timeline):
            rng = np.random.default_rng(seed_base + i)
            self.motion.append((i % 2 == 0, 0.5 + rng.uniform(-0.06, 0.06), 0.5 + rng.uniform(-0.05, 0.05)))

    def _img(self, path):
        img = self._cache.get(path)
        if img is None:
            if len(self._cache) > 8:
                self._cache.pop(next(iter(self._cache)))
            img = Image.open(path).convert("RGB")
            self._cache[path] = img
        return img

    def _base(self, si, t):
        sc = self.timeline[si]
        u = _ease((t - sc["start"]) / max(0.01, sc["end"] - sc["start"]))
        zoom_in, fx, fy = self.motion[si]
        z = 1 + (ZOOM_MAX - 1) * (u if zoom_in else 1 - u)
        return (0.5 + (fx - 0.5) * u, 0.5 + (fy - 0.5) * u, z)

    def _shot_view(self, si, k, t):
        shot = self.shots[si][k]
        ln = self.timeline[si]["lines"][k]
        if shot["view"]:
            cx, cy, z = shot["view"]
            local = min(1.0, max(0.0, (t - ln["start"]) / max(0.5, ln["end"] - ln["start"])))
            return (cx, cy, z * (1 + 0.03 * local))  # cận cảnh vẫn trôi rất nhẹ
        cx, cy, z = self._base(si, t)
        if shot["reveal"] and not shot["cut"]:  # cú zoom nhẹ khi vật mới xuất hiện
            a = (t - ln["start"]) / PUNCH_S
            if 0 <= a < 1:
                z *= 1 + PUNCH * math.sin(math.pi * a)
        return (cx, cy, z)

    def _camera(self, si, k, t):
        view = self._shot_view(si, k, t)
        if k == 0:
            return view
        a = (t - self.timeline[si]["lines"][k]["start"]) / CAM_S
        if a >= 1 or self.shots[si][k]["cut"] or self.shots[si][k - 1]["cut"]:
            return view  # vào/ra B-roll là cắt cảnh, không lướt camera
        return _lerp(self._shot_view(si, k - 1, t), view, _ease(a))

    def _render(self, img, view):
        cx, cy, z = view
        iw, ih = img.size
        bw, bh = iw / z, ih / z
        x = min(max(iw * cx, bw / 2), iw - bw / 2)
        y = min(max(ih * cy, bh / 2), ih - bh / 2)
        return img.resize(self.size, Image.BILINEAR, box=(x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2))

    def frame(self, si, t):
        lines = self.timeline[si]["lines"]
        shots = self.shots[si]
        k = 0
        for j, ln in enumerate(lines):
            if t >= ln["start"]:
                k = j
        cur = self._render(self._img(shots[k]["path"]), self._camera(si, k, t))
        if k > 0 and shots[k]["path"] != shots[k - 1]["path"]:
            fade = CUT_FADE_S if (shots[k]["cut"] or shots[k - 1]["cut"]) else FADE_S
            a = (t - lines[k]["start"]) / fade
            if a < 1:
                prev = self._render(self._img(shots[k - 1]["path"]), self._shot_view(si, k - 1, t))
                cur = Image.blend(prev, cur, _ease(a))
        return cur


class Subtitles:
    """Phụ đề in thẳng lên hình (dưới khung): chữ trắng viền đen trên nền mờ. Mỗi câu dựng sẵn một lớp
    RGBA một lần rồi dán lên các khung hình trong thời gian câu đó hiện, nên gần như không làm chậm render."""

    def __init__(self, timeline, size):
        from PIL import ImageDraw, ImageFont
        from doodle.text import FONT_PATH
        from doodle.theme import T
        k = size[1] / 1080
        font = ImageFont.truetype(T.get("font_file") or FONT_PATH, int(46 * k))  # phụ đề cùng font thương hiệu
        stroke = max(2, int(3.5 * k))
        max_w = size[0] * 0.84
        lines = [ln for sc in timeline for ln in sc["lines"] if not ln.get("nosub")]
        self.items = []
        for i, ln in enumerate(lines):
            words, rows, cur = ln["sub"].split(), [], ""
            for w in words:
                cand = f"{cur} {w}".strip()
                if cur and font.getlength(cand) > max_w:
                    rows.append(cur)
                    cur = w
                else:
                    cur = cand
            if cur:
                rows.append(cur)
            if len(rows) > 2:  # quá 2 dòng: chia đôi số từ
                mid = len(words) // 2
                rows = [" ".join(words[:mid]), " ".join(words[mid:])]
            lh = int(58 * k)
            pad_x, pad_y = int(22 * k), int(10 * k)
            tw = int(max(font.getlength(r) for r in rows)) + 2 * stroke
            bw, bh = tw + 2 * pad_x, lh * len(rows) + 2 * pad_y
            img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=int(14 * k), fill=(20, 20, 20, 150))
            for r_i, row in enumerate(rows):
                rw = font.getlength(row)
                d.text(((bw - rw) / 2, pad_y + r_i * lh), row, font=font, fill=(255, 255, 255, 255),
                       stroke_width=stroke, stroke_fill=(20, 20, 20, 255))
            end = ln["end"] + 0.3
            if i + 1 < len(lines):
                end = min(end, lines[i + 1]["start"])
            pos = ((size[0] - bw) // 2, size[1] - bh - int(34 * k))
            self.items.append((ln["start"], end, img, pos))
        self._i = 0

    def apply(self, frame, t):
        # thời gian luôn tăng dần → chỉ cần tiến con trỏ
        while self._i < len(self.items) and t >= self.items[self._i][1]:
            self._i += 1
        if self._i < len(self.items):
            start, end, img, pos = self.items[self._i]
            if start <= t < end:
                frame.paste(img, pos, img)
        return frame


def encode_video(timeline, state_paths, total, audio_wav, out_path, fps, size, preset, crf, log, subs=False,
                 watermark=None):
    n_frames = int(math.ceil(total * fps))
    cmd = [A.FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
           "-r", str(fps), "-i", "-", "-i", audio_wav,
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    fm = FrameMaker(timeline, state_paths, size)
    sub = Subtitles(timeline, size) if subs else None
    wm = None
    if watermark:  # (png bytes ở chiều cao 1080p, hết hiện từ giây t_stop, lề, độ mờ)
        png, t_stop, margin, opacity = watermark
        k = size[1] / 1080
        im = Image.open(io.BytesIO(png)).convert("RGBA")
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        if opacity < 1:
            im.putalpha(im.getchannel("A").point(lambda a: int(a * opacity)))
        wm = (im, (size[0] - im.width - int(margin * k), int(margin * k)), t_stop)
    black = Image.new("RGB", size, "black")
    si = 0
    t0 = time.time()
    try:
        for f in range(n_frames):
            t = f / fps
            while si + 1 < len(timeline) and t >= timeline[si + 1]["start"]:
                si += 1
            img = fm.frame(si, t)
            if sub:
                img = sub.apply(img, t)
            if wm and t < wm[2]:
                img.paste(wm[0], wm[1], wm[0])
            if t < 0.4:
                img = Image.blend(black, img, t / 0.4)
            elif t > total - 1.0:
                img = Image.blend(black, img, max(0.0, (total - t) / 1.0))
            proc.stdin.write(img.tobytes())
            if f % (fps * 30) == 0 and f:
                el = time.time() - t0
                log(f"  [video] {t/60:4.1f}/{total/60:.1f} phút — {f/el:.0f} fps, còn ~{(n_frames-f)/(f/el):.0f}s")
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode("utf-8", "replace")
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg lỗi: {err[-800:]}")


# ---------------- audio ----------------
def mix_audio(timeline, clips, total, cfg, base_dir, log):
    track = A.silence(total)
    for sc in timeline:
        for ln in sc["lines"]:
            A.place(track, clips[ln["audio_index"]], ln["start"])

    def asset(key, default):
        p = cfg.get(key, default)
        p = p if os.path.isabs(p) else os.path.join(base_dir, p)
        return p if os.path.exists(p) else None

    bgm = asset("bg_music_path", "bg_music.mp3")
    if bgm:
        music = A.fade(A.loop_to(A.decode(bgm), len(track)), 1.5, 3.0)
        # bg_music_volume nhân thẳng vào biên độ nhạc gốc (0.03 ≈ nhạc nhỏ hơn giọng đọc ~27 dB)
        track += music * cfg.get("bg_music_volume", 0.05)
        log(f"  + nhạc nền {os.path.basename(bgm)} (âm lượng {cfg.get('bg_music_volume', 0.05)})")
    else:
        log("  [i] không có nhạc nền (đặt file bg_music.mp3 hoặc sửa bg_music_path trong config.json)")

    if cfg.get("sfx_enabled", True):
        # thiếu file (vd máy mới clone — *.wav bị gitignore) thì dùng âm tổng hợp sẵn
        page = asset("sfx_path", "sfx_page.wav")
        s = A.decode(page) if page else A.default_page_flip()
        for sc in timeline[1:]:
            A.place(track, s, max(0, sc["start"] - 0.12), cfg.get("sfx_volume", 0.25))
        pop = asset("sfx_reveal_path", "sfx_pop.wav")
        s = A.decode(pop) if pop else A.default_pop()
        for sc in timeline:
            for ln in sc["lines"]:
                if ln["reveal"]:
                    A.place(track, s, ln["start"], cfg.get("sfx_reveal_volume", 0.15))
    return A.normalize(track)


# ---------------- phụ đề, chapters, metadata ----------------
def _srt_time(s):
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _wrap2(text, width=42):
    if len(text) <= width:
        return text
    mid = len(text) // 2
    cut = min((i for i, ch in enumerate(text) if ch == " "), key=lambda i: abs(i - mid), default=None)
    return text if cut is None else text[:cut] + "\n" + text[cut + 1:]


def write_srt(timeline, path):
    n = 1
    with open(path, "w", encoding="utf-8") as f:
        for sc in timeline:
            for ln in sc["lines"]:
                f.write(f"{n}\n{_srt_time(ln['start'])} --> {_srt_time(ln['end'])}\n{_wrap2(ln['sub'])}\n\n")
                n += 1


def chapters(timeline):
    out = []
    for sc in timeline:
        if sc["chapter"]:
            out.append((sc["start"], sc["chapter"]))
    if out and out[0][0] > 1:
        out.insert(0, (0.0, "Intro"))
    if out:
        out[0] = (0.0, out[0][1])
    fmt = lambda s: f"{int(s // 60):02d}:{int(s % 60):02d}" if s < 3600 else \
        f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}"
    return [f"{fmt(s)} {title}" for s, title in out]


def write_metadata(project_dir, out_dir, timeline, project, log):
    chap = chapters(timeline)
    seo_path = os.path.join(project_dir, "seo.json")
    seo = {}
    if os.path.exists(seo_path):
        with open(seo_path, "r", encoding="utf-8") as f:
            seo = json.load(f)
    desc = seo.get("description", "")
    chap_text = "\n".join(chap)
    desc = desc.replace("{{chapters}}", chap_text) if "{{chapters}}" in desc else \
        (desc + ("\n\n" + chap_text if chap else ""))
    from core.photos import used_credits
    from doodle import scene as ds
    credits = used_credits(project, ds.PHOTO_DIRS)  # ảnh CC BY bắt buộc ghi nguồn
    if credits:
        desc = desc.rstrip() + "\n\nNguồn ảnh:\n" + "\n".join(f"- {c}" for c in credits)
    lines = ["=== YOUTUBE METADATA ===", "", "--- TITLES ---"]
    lines += [f"{i + 1}. {t}" for i, t in enumerate(seo.get("titles") or [project["title"]])]
    lines += ["", "--- DESCRIPTION ---", desc.strip(), "", "--- TAGS ---", ", ".join(seo.get("tags", [])), "",
              "--- HASHTAGS ---", " ".join(seo.get("hashtags", []))]
    with open(os.path.join(out_dir, "youtube_metadata.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if len(chap) and len(chap) < 3:
        log("  [⚠] YouTube cần ≥3 chapters (mỗi cái ≥10s) mới hiện chapter — thêm 'chapter' vào các cảnh")
    if not seo:
        log("  [i] chưa có seo.json — metadata chỉ gồm tiêu đề + chapters")
    return seo


def write_thumbnail(project, seo, out_dir):
    spec = seo.get("thumbnail")
    svg = None
    if spec:
        try:
            svg = scene_svg(spec)
        except Exception as e:  # thumbnail lỗi không được làm hỏng cả bản build
            print(f"  [⚠] seo.json → thumbnail lỗi ({e}) — dùng cảnh đầu tiên thay thế")
    if svg is None:
        spec, visible = final_state(project["scenes"][0])
        svg = scene_svg(spec, None, visible, scene_seed(project["scenes"][0]))
    img = Image.open(io.BytesIO(render_png(svg))).convert("RGB").resize((1280, 720), Image.LANCZOS)
    p = os.path.join(out_dir, "thumbnail.png")
    img.save(p)
    return p


# ---------------- chính ----------------
def build(project, project_dir, cfg, base_dir, draft=False, log=print, subs=None):
    errors, warnings, stats = validate(project, cfg=cfg)
    if errors:
        for e in errors:
            log(f"[LỖI] {e}")
        raise SystemExit("[✗] Kịch bản còn lỗi — chạy validate để xem chi tiết.")
    slug = os.path.basename(os.path.normpath(project_dir))
    cache = os.path.join(project_dir, "cache")
    out_dir = os.path.join(project_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    T = time.time()
    log(f"=== BUILD {slug}: {stats['scenes']} cảnh, {stats['lines']} câu, {stats['words']} từ "
        f"({'nháp' if draft else 'bản chuẩn'}) ===")

    log("[1/5] Giọng đọc")
    t0 = time.time()
    texts = [ln["text"] for sc in project["scenes"] for ln in sc["lines"]]
    paths = synthesize(texts, os.path.join(cache, "audio"), project, cfg, log)
    clips = [A.trim_silence(A.decode(p)) for p in paths]
    durations = [len(c) / A.SR for c in clips]
    timeline, total = build_timeline(project, durations, cfg)
    with open(os.path.join(cache, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump({"total": total, "voice": pick_voice(project, cfg), "scenes": timeline}, f, ensure_ascii=False,
                  indent=1)
    _log_time(log, f"thuyết minh dài {total / 60:.1f} phút", t0)

    log("[2/5] Vẽ các cảnh")
    t0 = time.time()
    state_paths = render_shots(project, os.path.join(cache, "frames"), log)
    _log_time(log, "xong", t0)

    log("[3/5] Trộn âm thanh")
    t0 = time.time()
    mix = mix_audio(timeline, clips, total, cfg, base_dir, log)
    mix_path = os.path.join(cache, "mix.wav")
    A.write_wav(mix_path, mix)
    _log_time(log, "xong", t0)

    log("[4/5] Dựng video")
    t0 = time.time()
    if subs is None:  # CLI --subs > scenes.json burn_subtitles > config.json burn_subtitles
        subs = project.get("burn_subtitles", cfg.get("burn_subtitles", False))
    if subs:
        log("  + phụ đề in trên hình")
    video = os.path.join(out_dir, f"{slug}{'_draft' if draft else ''}.mp4")
    watermark = None
    brand = project.get("_brand")
    if brand and brand.get("watermark"):
        from .brand import watermark_png
        wmc = brand["watermark"]
        outro = [sc for sc, raw in zip(timeline, project["scenes"]) if raw.get("_auto_outro")]
        t_stop = outro[0]["start"] if outro else total + 1
        watermark = (watermark_png(brand, wmc.get("height", 84)), t_stop, wmc.get("margin", 26), wmc.get("opacity", 0.9))
        log(f"  + logo {brand.get('short', '')} ở góc")
    if draft:
        encode_video(timeline, state_paths, total, mix_path, video, 12, (960, 540), "ultrafast", 30, log, subs, watermark)
    else:
        encode_video(timeline, state_paths, total, mix_path, video, cfg.get("fps", 24), (W, H), "veryfast",
                     cfg.get("crf", 20), log, subs, watermark)
    _log_time(log, video, t0)

    log("[5/5] Phụ đề, chapters, thumbnail, metadata")
    write_srt(timeline, os.path.join(out_dir, f"{slug}.srt"))
    seo = write_metadata(project_dir, out_dir, timeline, project, log)
    write_thumbnail(project, seo, out_dir)
    log(f"[✓] Hoàn tất sau {time.time() - T:.0f}s → {out_dir}")
    for w in warnings:
        log(f"  [⚠] {w}")
    return {"video": video, "duration": total, "out_dir": out_dir}
