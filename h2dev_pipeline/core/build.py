"""Dựng video hoàn chỉnh từ projects/<slug>/scenes.json.

Luồng: TTS từng câu → đo thời lượng thật → dòng thời gian → vẽ từng trạng thái hiện dần →
sinh khung hình (zoom nhẹ theo cảnh + mờ dần khi hiện thành phần mới) đẩy thẳng vào ffmpeg →
trộn thuyết minh + nhạc nền + SFX → video dài 16:9 + bản dọc 9:16 (core/vertical.py) →
gói đăng tải projects/<slug>/publish/ cho YouTube, Shorts, TikTok, Reels (core/publish.py).

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
    """Phụ đề in thẳng lên hình: chữ trắng viền đen (có nền mờ khi box=True). Câu dài hơn `rows` dòng được chia
    thành nhiều "trang" hiện lần lượt, thời gian chia theo số ký tự. Mỗi trang dựng sẵn một lớp RGBA rồi dán lên
    khung hình, nên gần như không làm chậm render. top=None → đặt sát đáy khung; top=y → mép trên cố định."""

    def __init__(self, timeline, size, font_px=None, max_w=None, rows=2, box=True, top=None, line_h=None):
        from PIL import ImageDraw, ImageFont
        from doodle.text import FONT_PATH
        from doodle.theme import T
        k = size[1] / 1080
        font = ImageFont.truetype(T.get("font_file") or FONT_PATH, font_px or int(46 * k))  # font thương hiệu
        stroke = max(2, int(font.size * 0.076))
        max_w = max_w or size[0] * 0.84
        lh = line_h or int(font.size * 1.26)
        lines = [ln for sc in timeline for ln in sc["lines"] if not ln.get("nosub")]
        self.items = []
        for i, ln in enumerate(lines):
            words, all_rows, cur = ln["sub"].split(), [], ""
            for w in words:
                cand = f"{cur} {w}".strip()
                if cur and font.getlength(cand) > max_w:
                    all_rows.append(cur)
                    cur = w
                else:
                    cur = cand
            if cur:
                all_rows.append(cur)
            n_pages = max(1, math.ceil(len(all_rows) / rows))
            per = math.ceil(len(all_rows) / n_pages)  # chia đều số dòng giữa các trang
            pages = [all_rows[j:j + per] for j in range(0, len(all_rows), per)] or [[""]]
            end = ln["end"] + 0.3
            if i + 1 < len(lines):
                end = min(end, lines[i + 1]["start"])
            chars = [sum(len(r) for r in pg) + 1 for pg in pages]
            t, acc = ln["start"], 0
            for j, pg in enumerate(pages):
                acc += chars[j]
                t_end = end if j == len(pages) - 1 else ln["start"] + (ln["end"] - ln["start"]) * acc / sum(chars)
                self.items.append((t, t_end, *self._layer(pg, font, stroke, lh, k, box, size, top)))
                t = t_end
        self._i = 0

    @staticmethod
    def _layer(rows, font, stroke, lh, k, box, size, top):
        from PIL import ImageDraw
        pad_x, pad_y = int(22 * k), int(10 * k)
        tw = int(max(font.getlength(r) for r in rows)) + 2 * stroke
        bw, bh = tw + 2 * pad_x, lh * len(rows) + 2 * pad_y
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if box:
            d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=int(14 * k), fill=(20, 20, 20, 150))
        for r_i, row in enumerate(rows):
            rw = font.getlength(row)
            d.text(((bw - rw) / 2, pad_y + r_i * lh), row, font=font, fill=(255, 255, 255, 255),
                   stroke_width=stroke, stroke_fill=(20, 20, 20, 255))
        y = top if top is not None else size[1] - bh - int(34 * k)
        return img, ((size[0] - bw) // 2, y)

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
                 watermark=None, layout=None):
    """layout (core.vertical.Layout) → khung 16:9 được đặt vào bố cục dọc; không có → video ngang như cũ."""
    n_frames = int(math.ceil(total * fps))
    cmd = [A.FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
           "-r", str(fps), "-i", "-", "-i", audio_wav,
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    fm = FrameMaker(timeline, state_paths, layout.frame_size if layout else size)
    sub = (layout.subtitles(timeline) if layout else Subtitles(timeline, size)) if subs else None
    fade_in = 0.0 if layout else 0.4  # bản dọc vào thẳng nội dung — 1 giây đầu quyết định người xem có lướt qua
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
            if layout:
                img = layout.compose(img, t)
            if sub:
                img = sub.apply(img, t)
            if wm and t < wm[2]:
                img.paste(wm[0], wm[1], wm[0])
            if t < fade_in:
                img = Image.blend(black, img, t / fade_in)
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
        for cand in (p, os.path.join("media", os.path.basename(p))):  # nhạc/SFX nằm trong media/
            cand = cand if os.path.isabs(cand) else os.path.join(base_dir, cand)
            if os.path.exists(cand):
                return cand
        return None

    bgm = asset("bg_music_path", "bg_music.mp3")
    if bgm:
        music = A.fade(A.loop_to(A.decode(bgm), len(track)), 1.5, 3.0)
        # bg_music_volume nhân thẳng vào biên độ nhạc gốc (0.03 ≈ nhạc nhỏ hơn giọng đọc ~27 dB)
        track += music * cfg.get("bg_music_volume", 0.05)
        log(f"  + nhạc nền {os.path.basename(bgm)} (âm lượng {cfg.get('bg_music_volume', 0.05)})")
    else:
        log("  [i] không có nhạc nền (đặt file media/bg_music.mp3 hoặc sửa bg_music_path trong config.json)")

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


# ---------------- chính ----------------
def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _brand_watermark(project, timeline, total, log):
    brand = project.get("_brand")
    if not (brand and brand.get("watermark")):
        return None
    from .brand import watermark_png
    wmc = brand["watermark"]
    outro = [sc for sc, raw in zip(timeline, project["scenes"]) if raw.get("_auto_outro")]
    t_stop = outro[0]["start"] if outro else total + 1
    log(f"  + logo {brand.get('short', '')} ở góc")
    return watermark_png(brand, wmc.get("height", 84)), t_stop, wmc.get("margin", 26), wmc.get("opacity", 0.9)


def build(project, project_dir, cfg, base_dir, draft=False, log=print, subs=None, long=True, short=True):
    """Dựng video dài 16:9 và/hoặc bản dọc 9:16, rồi ghi gói đăng tải projects/<slug>/publish/."""
    from . import publish, vertical
    errors, warnings, stats = validate(project, cfg=cfg)
    if errors:
        for e in errors:
            log(f"[LỖI] {e}")
        raise SystemExit("[✗] Kịch bản còn lỗi — chạy validate để xem chi tiết.")
    slug = os.path.basename(os.path.normpath(project_dir))
    cache = os.path.join(project_dir, "cache")
    pub = os.path.join(project_dir, "publish")
    yt_dir, sh_dir = os.path.join(pub, "youtube"), os.path.join(pub, "short")
    vid_dir = os.path.join(pub, "draft") if draft else None
    for d in (cache, yt_dir, sh_dir) + ((vid_dir,) if vid_dir else ()):
        os.makedirs(d, exist_ok=True)
    state_file = os.path.join(cache, "publish_state.json")
    state = _load_json(state_file) or {}
    T = time.time()
    parts = " + ".join(p for p, on in (("video dài", long), ("bản dọc", short)) if on)
    log(f"=== BUILD {slug}: {stats['scenes']} cảnh, {stats['lines']} câu, {stats['words']} từ — {parts} "
        f"({'nháp' if draft else 'bản chuẩn'}) ===")

    log("[1/5] Giọng đọc")
    t0 = time.time()
    plan = vertical.plan(project) if short else None
    texts = [ln["text"] for sc in project["scenes"] for ln in sc["lines"]]
    paths = synthesize(texts + ([plan["outro_text"]] if plan else []), os.path.join(cache, "audio"), project, cfg, log)
    clips = [A.trim_silence(A.decode(p)) for p in paths]
    durations = [len(c) / A.SR for c in clips]
    timeline, total = build_timeline(project, durations, cfg)
    _save_json(os.path.join(cache, "timeline.json"), {"total": total, "voice": pick_voice(project, cfg),
                                                      "scenes": timeline})
    _log_time(log, f"thuyết minh dài {total / 60:.1f} phút", t0)

    log("[2/5] Vẽ các cảnh")
    t0 = time.time()
    shots = render_shots(project, os.path.join(cache, "frames"), log)
    _log_time(log, "xong", t0)
    if subs is None:  # CLI --subs > scenes.json burn_subtitles > config.json burn_subtitles
        subs = project.get("burn_subtitles", cfg.get("burn_subtitles", False))
    fps = 12 if draft else cfg.get("fps", 24)
    preset, crf = ("ultrafast", 30) if draft else ("veryfast", cfg.get("crf", 20))

    long_info = state.get("long")
    if long:
        log("[3/5] Video dài 16:9")
        t0 = time.time()
        mix = mix_audio(timeline, clips, total, cfg, base_dir, log)
        mix_path = os.path.join(cache, "mix.wav")
        A.write_wav(mix_path, mix)
        if subs:
            log("  + phụ đề in trên hình")
        video = os.path.join(vid_dir or yt_dir, f"{slug}{'_draft' if draft else ''}.mp4")
        encode_video(timeline, shots, total, mix_path, video, fps, (960, 540) if draft else (W, H), preset, crf, log,
                     subs, _brand_watermark(project, timeline, total, log))
        srt = os.path.join(yt_dir, f"{slug}.srt")
        write_srt(timeline, srt)
        thumb = publish.write_thumbnail(project, publish.load_seo(project_dir), os.path.join(yt_dir, "thumbnail.png"), log)
        long_info = {"video": video, "srt": srt, "thumbnail": thumb, "duration": round(total, 2), "draft": draft}
        _log_time(log, video, t0)
    else:
        log("[3/5] Video dài: bỏ qua (--short-only)")

    short_info = state.get("short")
    if short:
        log("[4/5] Bản dọc 9:16 (Shorts · TikTok · Reels)")
        t0 = time.time()
        offs, k = [], 0
        for sc in project["scenes"]:
            offs.append(k)
            k += len(sc["lines"])
        idx = [offs[si] + li for si, li in plan["items"]] + [len(texts)]
        segs, s_total, refs = vertical.timeline(project, plan, [durations[i] for i in idx], cfg)
        s_shots = [[shots[si][li] for si, li in seg] for seg in refs]
        s_mix = mix_audio(segs, [clips[i] for i in idx], s_total, cfg, base_dir, log)
        s_mix_path = os.path.join(cache, "mix_short.wav")
        A.write_wav(s_mix_path, s_mix)
        size = (540, 960) if draft else (vertical.VW, vertical.VH)
        layout = vertical.Layout(project, plan["hook"], size, s_total)
        video = os.path.join(vid_dir or sh_dir, f"{slug}_short{'_draft' if draft else ''}.mp4")
        encode_video(segs, s_shots, s_total, s_mix_path, video, fps, size, preset, crf, log, True, None, layout)
        srt = os.path.join(sh_dir, f"{slug}_short.srt")
        write_srt(segs, srt)
        cover = publish.write_cover(project, publish.load_seo(project_dir), plan, s_shots[0][0]["path"],
                                    os.path.join(sh_dir, "cover.png"), log)
        _save_json(os.path.join(cache, "short_timeline.json"), {"total": s_total, "scenes": segs})
        short_info = {"video": video, "srt": srt, "cover": cover, "duration": round(s_total, 2), "draft": draft,
                      "hook": plan["hook"]}
        _log_time(log, f"{video} ({s_total:.0f}s)", t0)
    else:
        log("[4/5] Bản dọc: bỏ qua (--no-short)")

    log("[5/5] Metadata YouTube · Shorts · TikTok · Reels")
    _save_json(state_file, {"long": long_info, "short": short_info})
    publish.write_all(project, project_dir, pub, long_info, short_info, chapters(timeline), log)
    log(f"[✓] Hoàn tất sau {time.time() - T:.0f}s → {pub} (mở PUBLISH.md)")
    for w in warnings:
        log(f"  [⚠] {w}")
    return {"video": (long_info or {}).get("video"), "short": (short_info or {}).get("video"),
            "duration": total, "publish_dir": pub}


def republish(project, project_dir, log=print):
    """Chỉ ghi lại metadata/PUBLISH.md (vd sau khi sửa seo.json hoặc điền long_url) — không dựng lại video."""
    from . import publish
    cache = os.path.join(project_dir, "cache")
    tl = _load_json(os.path.join(cache, "timeline.json"))
    state = _load_json(os.path.join(cache, "publish_state.json")) or {}
    if not tl:
        raise SystemExit("[✗] Chưa build lần nào — chạy build trước.")
    pub = os.path.join(project_dir, "publish")
    seo = publish.load_seo(project_dir)
    if state.get("long"):
        publish.write_thumbnail(project, seo, state["long"]["thumbnail"], log)
    publish.write_all(project, project_dir, pub, state.get("long"), state.get("short"), chapters(tl["scenes"]), log)
    return os.path.join(pub, "PUBLISH.md")
