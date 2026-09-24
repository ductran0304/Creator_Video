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
from .project import scene_states, scene_seed, final_state, validate
from .tts import synthesize, pick_voice

HIRES = 1.05          # vẽ ảnh cảnh to hơn 5% để zoom tối đa vẫn nét
ZOOM_MAX = 1.04       # mức zoom Ken Burns trong một cảnh
FADE_S = 0.28         # thời gian mờ dần khi hiện thành phần mới / đổi biểu cảm
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
            lines.append({"text": ln["text"], "start": t, "end": t + d, "audio_index": k,
                          "reveal": bool(ln.get("show"))})
            t += d
            k += 1
            t += scene_gap if li == len(sc["lines"]) - 1 else line_gap
        scenes.append({"index": si, "start": start, "lines": lines, "chapter": sc.get("chapter")})
    total = t - scene_gap + TAIL
    for i, s in enumerate(scenes):
        s["end"] = scenes[i + 1]["start"] if i + 1 < len(scenes) else total
    return scenes, total


# ---------------- ảnh trạng thái ----------------
def render_states(project, cache_dir, log):
    """Trả về list[list[path]]: ảnh PNG (độ phân giải HIRES) cho từng câu của từng cảnh."""
    os.makedirs(cache_dir, exist_ok=True)
    result, made = [], 0
    for sc in project["scenes"]:
        seed = scene_seed(sc)
        paths = []
        for spec, visible in scene_states(sc):
            svg = scene_svg(spec, None, visible, seed)
            p = os.path.join(cache_dir, hashlib.sha1(f"{HIRES}|{svg}".encode()).hexdigest()[:16] + ".png")
            if not os.path.exists(p):
                with open(p, "wb") as f:
                    f.write(render_png(svg, HIRES))
                made += 1
            paths.append(p)
        result.append(paths)
    log(f"  vẽ mới {made} ảnh, dùng lại {sum(len(p) for p in result) - made} ảnh từ cache")
    return result


# ---------------- khung hình ----------------
def _ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(u, 0.0), 1.0))


class FrameMaker:
    def __init__(self, timeline, state_paths, size, seed_base=0):
        self.timeline = timeline
        self.state_paths = state_paths
        self.size = size
        self._cache = {}
        # mỗi cảnh: zoom vào hoặc zoom ra, điểm nhìn lệch nhẹ — xen kẽ để không đơn điệu
        self.motion = []
        for i, sc in enumerate(timeline):
            rng = np.random.default_rng(seed_base + i)
            zoom_in = i % 2 == 0
            fx, fy = 0.5 + rng.uniform(-0.06, 0.06), 0.5 + rng.uniform(-0.05, 0.05)
            self.motion.append((zoom_in, fx, fy))

    def _img(self, path):
        img = self._cache.get(path)
        if img is None:
            if len(self._cache) > 6:
                self._cache.pop(next(iter(self._cache)))
            img = Image.open(path).convert("RGB")
            self._cache[path] = img
        return img

    def _view(self, img, si, t):
        sc = self.timeline[si]
        u = _ease((t - sc["start"]) / max(0.01, sc["end"] - sc["start"]))
        zoom_in, fx, fy = self.motion[si]
        z = 1 + (ZOOM_MAX - 1) * (u if zoom_in else 1 - u)
        iw, ih = img.size
        bw, bh = iw / z, ih / z
        cx = min(max(iw * (0.5 + (fx - 0.5) * u), bw / 2), iw - bw / 2)
        cy = min(max(ih * (0.5 + (fy - 0.5) * u), bh / 2), ih - bh / 2)
        box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
        return img.resize(self.size, Image.BILINEAR, box=box)

    def frame(self, si, t):
        sc = self.timeline[si]
        paths = self.state_paths[si]
        # trạng thái hiện hành = câu cuối cùng đã bắt đầu (trước câu đầu tiên dùng trạng thái câu 1)
        k = 0
        for j, ln in enumerate(sc["lines"]):
            if t >= ln["start"]:
                k = j
        cur = self._view(self._img(paths[k]), si, t)
        if k > 0 and paths[k] != paths[k - 1]:
            a = (t - sc["lines"][k]["start"]) / FADE_S
            if a < 1:
                prev = self._view(self._img(paths[k - 1]), si, t)
                cur = Image.blend(prev, cur, _ease(a))
        return cur


def encode_video(timeline, state_paths, total, audio_wav, out_path, fps, size, preset, crf, log):
    n_frames = int(math.ceil(total * fps))
    cmd = [A.FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
           "-r", str(fps), "-i", "-", "-i", audio_wav,
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    fm = FrameMaker(timeline, state_paths, size)
    black = Image.new("RGB", size, "black")
    si = 0
    t0 = time.time()
    try:
        for f in range(n_frames):
            t = f / fps
            while si + 1 < len(timeline) and t >= timeline[si + 1]["start"]:
                si += 1
            img = fm.frame(si, t)
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
                f.write(f"{n}\n{_srt_time(ln['start'])} --> {_srt_time(ln['end'])}\n{_wrap2(ln['text'])}\n\n")
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
def build(project, project_dir, cfg, base_dir, draft=False, log=print):
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
    state_paths = render_states(project, os.path.join(cache, "frames"), log)
    _log_time(log, "xong", t0)

    log("[3/5] Trộn âm thanh")
    t0 = time.time()
    mix = mix_audio(timeline, clips, total, cfg, base_dir, log)
    mix_path = os.path.join(cache, "mix.wav")
    A.write_wav(mix_path, mix)
    _log_time(log, "xong", t0)

    log("[4/5] Dựng video")
    t0 = time.time()
    video = os.path.join(out_dir, f"{slug}{'_draft' if draft else ''}.mp4")
    if draft:
        encode_video(timeline, state_paths, total, mix_path, video, 12, (960, 540), "ultrafast", 30, log)
    else:
        encode_video(timeline, state_paths, total, mix_path, video, cfg.get("fps", 24), (W, H), "veryfast",
                     cfg.get("crf", 20), log)
    _log_time(log, video, t0)

    log("[5/5] Phụ đề, chapters, thumbnail, metadata")
    write_srt(timeline, os.path.join(out_dir, f"{slug}.srt"))
    seo = write_metadata(project_dir, out_dir, timeline, project, log)
    write_thumbnail(project, seo, out_dir)
    log(f"[✓] Hoàn tất sau {time.time() - T:.0f}s → {out_dir}")
    for w in warnings:
        log(f"  [⚠] {w}")
    return {"video": video, "duration": total, "out_dir": out_dir}
