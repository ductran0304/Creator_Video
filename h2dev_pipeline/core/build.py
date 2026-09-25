"""Dựng video hoàn chỉnh từ projects/<slug>/scenes.json.

Luồng: TTS từng câu (kèm mốc thời gian từng từ) → đo thời lượng thật → dòng thời gian → vẽ từng cú máy →
sinh khung hình (camera ảo, chuyển cảnh mượt, vẽ tay có bàn tay cầm bút) đẩy thẳng vào ffmpeg →
trộn thuyết minh + nhạc nền (tự nhỏ lại khi có lời) + SFX theo ý nghĩa → video dài 16:9 + các bản dọc 9:16
(core/vertical.py) → gói đăng tải projects/<slug>/publish/ (core/publish.py).

Mọi thứ đắt (audio, ảnh cảnh) đều cache theo nội dung trong projects/<slug>/cache/, nên chạy lại sau khi
sửa vài câu/cảnh chỉ làm lại phần thay đổi.
"""
import hashlib
import io
import json
import math
import os
import re
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from doodle.scene import scene_svg, render_png, W, H
from . import audio as A
from .project import line_states, validate
from .tts import synthesize, pick_voice, load_words

HIRES = 1.08          # vẽ ảnh cảnh to hơn 8% để zoom nền tối đa vẫn nét
ZOOM_MAX = 1.07       # mức zoom Ken Burns trong một cảnh (toàn cảnh)
FOCUS_MAX = 1.9       # zoom tối đa khi camera đẩy vào cận cảnh (focus)
CAM_S = 0.55          # thời gian camera lướt sang cú máy mới
PUNCH, PUNCH_S = 0.03, 0.45  # cú zoom nhẹ khi hiện vật mới / đổi biểu cảm
FADE_S = 0.18         # chuyển mờ khi hình đổi trong cùng cảnh
CUT_FADE_S = 0.12     # vào/ra B-roll (cut)
SCENE_FADE_S = 0.3    # chuyển cảnh: hoà hình cảnh trước sang cảnh sau (không mờ về đen)
DRAW_S = 0.75         # thời gian "vẽ tay" một thành phần mới
LEAD_IN, TAIL = 0.5, 1.5
CARD_SFX = {"stat_cards": "paper", "ledger": "paper", "compare": "paper", "document": "paper", "media_card": "paper",
            "checklist": "ding", "map": "pop", "headline": "thud", "deadline": "thud", "concept_text": "thud"}


def _log_time(log, label, t0):
    log(f"  ✓ {label} ({time.time() - t0:.1f}s)")


# ---------------- mốc thời gian từng từ (phụ đề karaoke) ----------------
def word_times(sub, text, start, dur, bounds=None):
    """Mốc (bắt đầu, kết thúc) tuyệt đối cho từng từ của `sub`.
    bounds: mốc từng từ của câu đọc (edge-tts, đã dời theo phần im lặng bị cắt) hoặc None.
    sub trùng lời đọc → dùng đúng mốc; khác (vd số viết bằng chữ số) → chia theo độ dài chữ trong khoảng có lời."""
    words = sub.split()
    if not words:
        return []
    if bounds and len(bounds) == len(words) and re.sub(r"\W", "", sub.lower()) == re.sub(r"\W", "", text.lower()):
        return [(start + max(0.0, b[0]), start + min(dur, max(b[1], b[0] + 0.05))) for b in bounds]
    a, b = (bounds[0][0], bounds[-1][1]) if bounds else (0.04, dur - 0.04)
    a, b = max(0.0, a), min(dur, max(b, a + 0.2))
    weights = [len(w) + 2 for w in words]
    tot = float(sum(weights))
    out, acc = [], 0.0
    for wgt in weights:
        s0 = a + (b - a) * acc / tot
        acc += wgt
        out.append((start + s0, start + a + (b - a) * acc / tot))
    return out


# ---------------- dòng thời gian ----------------
def _line_sfx(states, i, si):
    """Hiệu ứng âm thanh theo ý nghĩa cho câu i của một cảnh."""
    st, prev = states[i], states[i - 1] if i else None
    out = []
    frame = st["spec"].get("frame", "scene")
    if st["cut"] and not (prev and prev["cut"] and prev["spec"] == st["spec"]):
        out.append("thud" if frame in ("concept_text", "headline", "deadline", "stat_cards") else "whoosh")
    elif not st["cut"] and "_step" in st["spec"] and (not prev or prev["spec"].get("_step") != st["spec"]["_step"]):
        if i or si == 0:
            out.append(CARD_SFX.get(frame, "pop"))
    elif st["reveal"] and not st["cut"] and st["new"]:
        out.append("pop")
    return out


def build_timeline(project, durations, cfg, bounds=None):
    line_gap = cfg.get("line_gap", 0.25)
    scene_gap = cfg.get("scene_gap", 0.6)
    t = LEAD_IN
    k = 0
    scenes = []
    for si, sc in enumerate(project["scenes"]):
        start = t
        lines = []
        states = line_states(sc)
        for li, ln in enumerate(sc["lines"]):
            d = durations[k]
            sub = ln.get("sub") or ln["text"]
            lines.append({"text": ln["text"], "sub": sub, "start": t, "end": t + d, "audio_index": k,
                          "reveal": bool(ln.get("show")), "speaker": ln.get("speaker"),
                          "wt": word_times(sub, ln["text"], t, d, bounds[k] if bounds else None),
                          "sfx": _line_sfx(states, li, si),
                          "nosub": bool(sc.get("_auto_outro"))})  # màn kết đã có chữ, không cần phụ đề
            t += d
            k += 1
            t += scene_gap if li == len(sc["lines"]) - 1 else line_gap
        scenes.append({"index": si, "start": start, "lines": lines, "chapter": sc.get("chapter"),
                       "progress": sc.get("progress")})
    total = t - scene_gap + TAIL
    for i, s in enumerate(scenes):
        s["end"] = scenes[i + 1]["start"] if i + 1 < len(scenes) else total
    return scenes, total


def load_clips(paths):
    """→ (clips đã cắt im lặng, thời lượng, mốc từng từ đã dời) theo thứ tự."""
    clips, durs, bounds = [], [], []
    for p in paths:
        clip, lead = A.trim_silence(A.decode(p), with_lead=True)
        clips.append(clip)
        durs.append(len(clip) / A.SR)
        wb = load_words(p)
        bounds.append([(s - lead, e - lead, w) for s, e, w in wb] if wb else None)
    return clips, durs, bounds


# ---------------- ảnh từng cú máy ----------------
def _focus_view(box):
    """Khung bao element → (tâm x, tâm y theo tỉ lệ, mức zoom) để element chiếm ~60% chiều cao khung."""
    bw = max(60.0, box["x1"] - box["x0"])
    bh = max(60.0, box["bottom"] - box["top"])
    z = max(1.15, min(FOCUS_MAX, 0.62 * H / bh, 0.72 * W / bw))
    return ((box["x0"] + box["x1"]) / 2 / W, (box["top"] + box["bottom"]) / 2 / H, z)


def _map_view(spec):
    zm = spec.get("zoom")
    if not zm:
        return None
    from doodle.cards import map_xy
    x, y = map_xy(zm["lat"], zm["lon"])
    return (x / W, y / H, max(1.0, min(4.0, float(zm.get("z", 2.0)))))


def render_state(st, cache_dir, size=None, draw=False, scene=None):
    """Một cú máy → dict(path, view, cut, reveal, fit, draw). size=(w, h) chỉ dùng cho khung co giãn (bản dọc)."""
    from doodle.cards import RESPONSIVE
    frame = st["spec"].get("frame", "scene")
    native = bool(size) and frame in RESPONSIVE
    boxes = {}
    svg = scene_svg(st["spec"], None, st["visible"], st["seed"], boxes, size=size if native else None)
    view, res = None, HIRES
    if st["focus"] and st["focus"] in boxes:
        view = _focus_view(boxes[st["focus"]])
        res = max(HIRES, view[2] * 1.02)
    elif frame == "map" and _map_view(st["spec"]):
        view = _map_view(st["spec"])
        res = max(HIRES, view[2] * 1.02)
    p = os.path.join(cache_dir, hashlib.sha1(f"{res:.3f}|{svg}".encode()).hexdigest()[:16] + ".png")
    if not os.path.exists(p):
        with open(p, "wb") as f:
            f.write(render_png(svg, res))
    fit = None
    if size and not native:  # ảnh 16:9 đưa vào ô dọc: cảnh doodle/bản đồ cắt vừa ô, khung chữ thu vừa không cắt
        fit = "cover" if frame in ("scene", "map") else "contain"
        if frame == "scene":  # chữ tự do rộng hơn phần giữ lại khi cắt → thu cả khung thay vì cắt mất chữ
            from doodle.text import text_width
            keep = W * (size[0] / size[1]) / (W / H)
            for el in st["spec"].get("elements", []):
                if el.get("type") == "label" and not el.get("on") and \
                        min(text_width(el.get("text", ""), el.get("size", 110)), W * el.get("width", 0.84)) > keep * 0.92:
                    fit = "contain"
    draw_box = None
    if draw and st["new"] and not st["cut"] and scene is not None:
        els = scene.get("elements", [])
        bs = [boxes[els[i]["id"]] for i in st["new"] if i < len(els) and els[i].get("id") in boxes
              and els[i].get("type") in ("character", "prop", "photo")]
        if bs:
            draw_box = (min(b["x0"] for b in bs), min(b["top"] for b in bs), max(b["x1"] for b in bs),
                        max(b["bottom"] for b in bs))
    return {"path": p, "view": view, "cut": st["cut"], "reveal": st["reveal"], "fit": fit, "draw": draw_box,
            "native": native, "frame": frame}


def render_shots(project, cache_dir, log, draw=False):
    """Mỗi câu thoại một cú máy: list (theo cảnh) các list dict (xem render_state)."""
    os.makedirs(cache_dir, exist_ok=True)
    result, before = [], set(os.listdir(cache_dir))
    total = 0
    for sc in project["scenes"]:
        shots = [render_state(st, cache_dir, draw=draw, scene=sc) for st in line_states(sc)]
        total += len(shots)
        result.append(shots)
    made = len(set(os.listdir(cache_dir)) - before)
    log(f"  vẽ mới {made} ảnh, dùng lại {total - made} ảnh từ cache")
    return result


# ---------------- khung hình ----------------
def _ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(u, 0.0), 1.0))


def _lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


_HAND = {}


def hand_image(scale):
    """Ảnh bàn tay cầm bút (asset drawing_hand) + toạ độ đầu bút trong ảnh."""
    key = round(scale, 2)
    if key not in _HAND:
        from doodle import assets
        inner = assets.get("props", "drawing_hand")
        if not inner:
            _HAND[key] = None
        else:
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-130 -150 260 300" width="{260 * scale:.0f}" '
                   f'height="{300 * scale:.0f}">{inner}</svg>')
            import resvg_py
            im = Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg)))).convert("RGBA")
            _HAND[key] = (im, (15 * scale, 10 * scale))  # đầu bút ở (-115, -140) trong viewBox
    return _HAND[key]


class FrameMaker:
    """Camera ảo: toàn cảnh trôi nhẹ (Ken Burns) theo cảnh; câu có focus thì đẩy vào cận cảnh; câu làm hình
    thay đổi thì có cú zoom nhẹ; đổi ảnh thì chuyển mờ nhanh; sang cảnh mới thì hoà hình (không mờ về đen);
    thành phần mới có thể được "vẽ tay" (bàn tay cầm bút quét qua). Ảnh nguồn được cắt đúng tỉ lệ khung đích."""

    def __init__(self, timeline, shots, size, seed_base=0, zoom_max=ZOOM_MAX, paper="#F5F1E6"):
        self.timeline = timeline
        self.shots = shots
        self.size = size
        self.zoom_max = zoom_max
        self.paper = paper
        self._cache = {}
        self.motion = []
        for i, sc in enumerate(timeline):
            rng = np.random.default_rng(seed_base + i)
            self.motion.append((i % 2 == 0, 0.5 + rng.uniform(-0.06, 0.06), 0.5 + rng.uniform(-0.05, 0.05)))

    def _img(self, path):
        img = self._cache.get(path)
        if img is None:
            if len(self._cache) > 10:
                self._cache.pop(next(iter(self._cache)))
            img = Image.open(path).convert("RGB")
            self._cache[path] = img
        return img

    def _base(self, si, t, native=False):
        sc = self.timeline[si]
        u = _ease((t - sc["start"]) / max(0.01, sc["end"] - sc["start"]))
        zoom_in, fx, fy = self.motion[si]
        zmax = 1 + (self.zoom_max - 1) * (0.45 if native else 1.0)  # khung thẻ dọc: trôi rất nhẹ để không cắt chữ
        z = 1 + (zmax - 1) * (u if zoom_in else 1 - u)
        drift = 0.4 if native else 1.0
        return (0.5 + (fx - 0.5) * u * drift, 0.5 + (fy - 0.5) * u * drift, z)

    def _shot_view(self, si, k, t):
        shot = self.shots[si][k]
        ln = self.timeline[si]["lines"][k]
        if shot["view"]:
            cx, cy, z = shot["view"]
            local = min(1.0, max(0.0, (t - ln["start"]) / max(0.5, ln["end"] - ln["start"])))
            return (cx, cy, z * (1 + 0.03 * local))  # cận cảnh vẫn trôi rất nhẹ
        cx, cy, z = self._base(si, t, shot.get("native"))
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

    def _render(self, img, view, fit=None):
        cx, cy, z = view
        iw, ih = img.size
        tw, th = self.size
        if fit == "contain":  # thu cả khung (đã zoom) vào ô đích, phần thừa là nền giấy
            bw, bh = iw / z, ih / z
            x = min(max(iw * cx, bw / 2), iw - bw / 2)
            y = min(max(ih * cy, bh / 2), ih - bh / 2)
            s = min(tw / bw, th / bh)
            rw, rh = max(1, int(bw * s)), max(1, int(bh * s))
            part = img.resize((rw, rh), Image.BILINEAR, box=(x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2))
            out = Image.new("RGB", self.size, self.paper)
            out.paste(part, ((tw - rw) // 2, (th - rh) // 2))
            return out
        a = tw / th
        bw = iw / z
        bh = bw / a
        if bh > ih / z:
            bh = ih / z
            bw = bh * a
        x = min(max(iw * cx, bw / 2), iw - bw / 2)
        y = min(max(ih * cy, bh / 2), ih - bh / 2)
        return img.resize(self.size, Image.BILINEAR, box=(x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2))

    def _drawn(self, prev_img, cur_img, box, u):
        """Ảnh nguồn đang được vẽ dở: phần mới lộ dần trái → phải theo đầu bút, có bàn tay cầm bút."""
        k = cur_img.width / W
        x0, y0, x1, y1 = [v * k for v in box]
        pad = 20 * k
        x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(cur_img.width, x1 + pad), min(cur_img.height, y1 + pad)
        fx = x0 + (x1 - x0) * u
        img = prev_img.copy()
        if fx > x0 + 1:
            img.paste(cur_img.crop((int(x0), int(y0), int(fx), int(y1))), (int(x0), int(y0)))
        hand = hand_image(1.1 * k)
        if hand and u < 1:
            him, (tx, ty) = hand
            hy = y0 + (y1 - y0) * (0.5 + 0.42 * math.sin(u * math.pi * 7))
            img.paste(him, (int(fx - tx), int(hy - ty)), him)
        return img

    def frame(self, si, t):
        lines = self.timeline[si]["lines"]
        shots = self.shots[si]
        k = 0
        for j, ln in enumerate(lines):
            if t >= ln["start"]:
                k = j
        shot = shots[k]
        view = self._camera(si, k, t)
        a_draw = (t - lines[k]["start"]) / DRAW_S
        if shot.get("draw") and k > 0 and 0 <= a_draw < 1:
            src = self._drawn(self._img(shots[k - 1]["path"]), self._img(shot["path"]), shot["draw"], _ease(a_draw))
            return self._render(src, view, shot.get("fit"))
        cur = self._render(self._img(shot["path"]), view, shot.get("fit"))
        if k > 0 and shot["path"] != shots[k - 1]["path"]:
            fade = CUT_FADE_S if (shot["cut"] or shots[k - 1]["cut"]) else FADE_S
            a = (t - lines[k]["start"]) / fade
            if a < 1:
                prev = self._render(self._img(shots[k - 1]["path"]), self._shot_view(si, k - 1, t),
                                    shots[k - 1].get("fit"))
                cur = Image.blend(prev, cur, _ease(a))
        elif k == 0 and si > 0:  # sang cảnh mới: hoà hình từ cú máy cuối của cảnh trước
            a = (t - self.timeline[si]["start"]) / SCENE_FADE_S
            if a < 1:
                ps = self.shots[si - 1]
                prev = self._render(self._img(ps[-1]["path"]), self._shot_view(si - 1, len(ps) - 1, t),
                                    ps[-1].get("fit"))
                cur = Image.blend(prev, cur, _ease(a))
        return cur


def _hex_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


class Subtitles:
    """Phụ đề in thẳng lên hình, tô sáng đúng từ đang đọc (karaoke).
    style "box": chữ trắng trên nền mờ (video ngang) · "pill": chữ mực, từ đang đọc nằm trên vệt dạ quang (bản dọc).
    Câu dài hơn `rows` dòng được chia thành nhiều "trang" theo mốc thời gian từng từ. Mỗi trạng thái (trang, từ)
    chỉ vẽ khi cần rồi dán lên khung hình."""

    def __init__(self, timeline, size, font_px=None, max_w=None, rows=2, style="box", top=None, line_h=None,
                 speakers=None, font_file=None):
        from doodle.text import FONT_PATH
        from doodle.theme import T
        k = size[1] / 1080 if style == "box" else size[0] / 1080
        self.font = ImageFont.truetype(font_file or T.get("font_file") or FONT_PATH, font_px or int(46 * k))
        self.stroke = max(2, int(self.font.size * 0.076))
        self.lh = line_h or int(self.font.size * 1.3)
        self.k, self.size, self.style, self.top = k, size, style, top
        self.ink = _hex_rgb(T["title"]) if style == "pill" else (255, 255, 255)
        self.hl = _hex_rgb(T.get("highlight") or "#FFC93C")
        self.speakers = speakers or {}
        max_w = max_w or size[0] * 0.84
        lines = [ln for sc in timeline for ln in sc["lines"] if not ln.get("nosub")]
        self.pages = []  # (start, end, rows[[(word, wstart)]], color)
        for i, ln in enumerate(lines):
            words = ln["sub"].split()
            wt = ln.get("wt") or word_times(ln["sub"], ln["text"], ln["start"], ln["end"] - ln["start"])
            rows_, cur, cur_w = [], [], ""
            for w, (ws, _) in zip(words, wt):
                cand = f"{cur_w} {w}".strip()
                if cur and self.font.getlength(cand) > max_w:
                    rows_.append(cur)
                    cur, cur_w = [(w, ws)], w
                else:
                    cur.append((w, ws))
                    cur_w = cand
            if cur:
                rows_.append(cur)
            if not rows_:
                continue
            n_pages = max(1, math.ceil(len(rows_) / rows))
            per = math.ceil(len(rows_) / n_pages)
            groups = [rows_[j:j + per] for j in range(0, len(rows_), per)]
            end = ln["end"] + 0.3
            if i + 1 < len(lines):
                end = min(end, lines[i + 1]["start"])
            spk = self.speakers.get(ln.get("speaker")) or {}
            color = _hex_rgb(spk["color"]) if spk.get("color") else self.hl
            for j, g in enumerate(groups):
                start = g[0][0][1] if j else ln["start"]
                stop = groups[j + 1][0][0][1] if j + 1 < len(groups) else end
                self.pages.append((start, stop, g, color))
        self._i = 0
        self._key, self._layer = None, None

    def _render(self, rows, color, current):
        font, k = self.font, self.k
        pad_x, pad_y = int(24 * k), int(12 * k)
        widths = [font.getlength(" ".join(w for w, _ in r)) for r in rows]
        bw = int(max(widths)) + 2 * pad_x + 2 * self.stroke
        bh = self.lh * len(rows) + 2 * pad_y
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if self.style == "box":
            d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=int(14 * k), fill=(20, 20, 20, 150))
        space = font.getlength(" ")
        n = 0
        for r_i, (row, rw) in enumerate(zip(rows, widths)):
            x = (bw - rw) / 2
            y = pad_y + r_i * self.lh
            for w, _ in row:
                ww = font.getlength(w)
                is_cur = n == current
                if self.style == "pill":
                    if is_cur:
                        d.rounded_rectangle([x - 8 * k, y + self.lh * 0.06, x + ww + 8 * k, y + self.lh * 0.92],
                                            radius=int(12 * k), fill=color + (255,))
                    d.text((x, y), w, font=font, fill=self.ink + (255,))
                else:
                    d.text((x, y), w, font=font, fill=(color if is_cur else (255, 255, 255)) + (255,),
                           stroke_width=self.stroke, stroke_fill=(20, 20, 20, 255))
                x += ww + space
                n += 1
        return img

    def apply(self, frame, t):
        # thời gian luôn tăng dần → chỉ cần tiến con trỏ
        while self._i < len(self.pages) and t >= self.pages[self._i][1]:
            self._i += 1
        if self._i >= len(self.pages):
            return frame
        start, end, rows, color = self.pages[self._i]
        if not (start <= t < end):
            return frame
        flat = [ws for r in rows for _, ws in r]
        cur = max((j for j, ws in enumerate(flat) if ws <= t), default=0)
        key = (self._i, cur)
        if key != self._key:
            self._key, self._layer = key, self._render(rows, color, cur)
        img = self._layer
        y = self.top if self.top is not None else self.size[1] - img.height - int(34 * self.k)
        frame.paste(img, ((self.size[0] - img.width) // 2, int(y)), img)
        return frame


class Progress:
    """Bảng tiến độ ở góc (video dài): project["progress_items"] + scene["progress"] = mục đang nói (từ 1)."""

    def __init__(self, items, size):
        from doodle.text import FONT_PATH
        from doodle.theme import T
        self.items, self.size = items, size
        self.k = size[1] / 1080
        self.font = ImageFont.truetype(T.get("font_file") or FONT_PATH, int(26 * self.k))
        self.accent = _hex_rgb(T.get("accent") or T["alert"])
        self.teal = _hex_rgb(T["label"])
        self._cache = {}

    def layer(self, n):
        if n not in self._cache:
            k, f = self.k, self.font
            w = int(max(f.getlength(f"{i + 1}. {t}") for i, t in enumerate(self.items)) + 90 * k)
            rh = int(40 * k)
            h = rh * len(self.items) + int(24 * k)
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(16 * k), fill=(255, 255, 255, 225))
            for i, t in enumerate(self.items):
                y = int(12 * k) + i * rh
                cx, cy, r = int(28 * k), y + rh // 2, int(12 * k)
                if i + 1 < n:
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=self.teal + (255,))
                    d.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.4), (cx + r * 0.5, cy - r * 0.35)],
                           fill=(255, 255, 255, 255), width=max(2, int(4 * k)))
                elif i + 1 == n:
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=self.accent + (255,))
                else:
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(170, 178, 196, 255), width=max(2, int(3 * k)))
                col = (16, 26, 61, 255) if i + 1 == n else ((90, 98, 118, 255) if i + 1 < n else (150, 156, 172, 255))
                d.text((cx + r + int(14 * k), y + int(6 * k)), f"{i + 1}. {t}", font=f, fill=col)
            self._cache[n] = img
        return self._cache[n]


def _shot_at(timeline, shots, si, t):
    k = 0
    for j, ln in enumerate(timeline[si]["lines"]):
        if t >= ln["start"]:
            k = j
    return shots[si][k]


def encode_video(timeline, shots, total, audio_wav, out_path, fps, size, preset, crf, log, subs=False,
                 watermark=None, layout=None, progress=None, speakers=None):
    """layout (core.vertical.Layout) → bố cục dọc (ô nội dung + tiêu đề + phụ đề); không có → video ngang."""
    n_frames = int(math.ceil(total * fps))
    cmd = [A.FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
           "-r", str(fps), "-i", "-", "-i", audio_wav,
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    from doodle.theme import T
    fm = FrameMaker(timeline, shots, layout.frame_size if layout else size, paper=T["paper"])
    if subs:
        sub = layout.subtitles(timeline, speakers) if layout else Subtitles(timeline, size, speakers=speakers)
    else:
        sub = None
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
                img = layout.compose(img, t, si)
            if progress and timeline[si].get("progress") and _shot_at(timeline, shots, si, t).get("frame", "scene") == "scene":  # thẻ đã có tiêu đề riêng
                lay = progress.layer(timeline[si]["progress"])
                img.paste(lay, (int(36 * progress.k), int(36 * progress.k)), lay)
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
_SFX = {}


def _sfx(name, cfg, base_dir):
    if name not in _SFX:
        path = None
        key = {"page": ("sfx_path", "sfx_page.wav"), "pop": ("sfx_reveal_path", "sfx_pop.wav")}.get(name)
        if key:
            path = _asset(cfg, base_dir, *key)
        gen = {"page": A.default_page_flip, "pop": A.default_pop, "whoosh": A.sfx_whoosh, "ding": A.sfx_ding,
               "thud": A.sfx_thud, "paper": A.sfx_paper, "scribble": A.sfx_scribble}[name]
        _SFX[name] = A.decode(path) if path else gen()
    return _SFX[name]


SFX_GAIN = {"page": ("sfx_volume", 0.25), "pop": ("sfx_reveal_volume", 0.15), "whoosh": ("sfx_whoosh_volume", 0.22),
            "ding": ("sfx_ding_volume", 0.2), "thud": ("sfx_thud_volume", 0.35), "paper": ("sfx_paper_volume", 0.3),
            "scribble": ("sfx_scribble_volume", 0.5)}


def _asset(cfg, base_dir, key, default):
    p = cfg.get(key, default)
    for cand in (p, os.path.join("media", os.path.basename(p))):  # nhạc/SFX nằm trong media/
        cand = cand if os.path.isabs(cand) else os.path.join(base_dir, cand)
        if os.path.exists(cand):
            return cand
    return None


def mix_audio(timeline, clips, total, cfg, base_dir, log, draw_lines=()):
    voice = A.silence(total)
    for sc in timeline:
        for ln in sc["lines"]:
            A.place(voice, clips[ln["audio_index"]], ln["start"])
    track = voice.copy()

    bgm = _asset(cfg, base_dir, "bg_music_path", "bg_music.mp3")
    if bgm:
        music = A.fade(A.loop_to(A.decode(bgm), len(track)), 1.5, 3.0)
        vol = cfg.get("bg_music_volume", 0.05)
        boost = cfg.get("bg_music_gap_boost", 1.8)  # nhạc to lên ở khoảng nghỉ giữa các câu, nhỏ lại khi có lời
        env = A.speech_envelope(voice)
        track += music * vol * (boost - (boost - 1) * env)
        log(f"  + nhạc nền {os.path.basename(bgm)} (âm lượng {vol}, khoảng nghỉ ×{boost})")
    else:
        log("  [i] không có nhạc nền (đặt file media/bg_music.mp3 hoặc sửa bg_music_path trong config.json)")

    if cfg.get("sfx_enabled", True):
        # thiếu file (vd máy mới clone — *.wav bị gitignore) thì dùng âm tổng hợp sẵn
        vol = lambda n: cfg.get(SFX_GAIN[n][0], SFX_GAIN[n][1])
        for sc in timeline[1:]:
            A.place(track, _sfx("page", cfg, base_dir), max(0, sc["start"] - 0.12), vol("page"))
        for sc in timeline:
            for ln in sc["lines"]:
                for name in ln.get("sfx", []):
                    A.place(track, _sfx(name, cfg, base_dir), max(0, ln["start"] - (0.08 if name == "whoosh" else 0)),
                            vol(name))
        for t in draw_lines:
            A.place(track, _sfx("scribble", cfg, base_dir), t, vol("scribble"))
    return A.normalize(track)


# ---------------- phụ đề, chapters ----------------
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


def draw_enabled(project, cfg):
    """Hiệu ứng vẽ tay: mặc định bật cho kênh doodle (không thương hiệu), thương hiệu tự chọn qua draw_reveal."""
    brand = project.get("_brand") or {}
    return bool(project.get("draw_reveal", brand.get("draw_reveal", cfg.get("draw_reveal", not brand))))


def _draw_times(timeline, shots):
    return [ln["start"] for sc, ss in zip(timeline, shots) for ln, sh in zip(sc["lines"], ss) if sh.get("draw")]


def build(project, project_dir, cfg, base_dir, draft=False, log=print, subs=None, long=True, short=True):
    """Dựng video dài 16:9 và/hoặc các bản dọc 9:16, rồi ghi gói đăng tải projects/<slug>/publish/."""
    from . import publish, vertical
    errors, warnings, stats = validate(project, cfg=cfg)
    if errors:
        for e in errors:
            log(f"[LỖI] {e}")
        raise SystemExit("[✗] Kịch bản còn lỗi — chạy validate để xem chi tiết.")
    slug = os.path.basename(os.path.normpath(project_dir))
    cache = os.path.join(project_dir, "cache")
    pub = os.path.join(project_dir, "publish")
    yt_dir = os.path.join(pub, "youtube")
    vid_dir = os.path.join(pub, "draft") if draft else None
    for d in (cache, yt_dir) + ((vid_dir,) if vid_dir else ()):
        os.makedirs(d, exist_ok=True)
    state_file = os.path.join(cache, "publish_state.json")
    state = _load_json(state_file) or {}
    T0 = time.time()
    plans = vertical.plans(project) if short else []
    parts = " + ".join(p for p, on in (("video dài", long), (f"{len(plans)} bản dọc", short)) if on)
    log(f"=== BUILD {slug}: {stats['scenes']} cảnh, {stats['lines']} câu, {stats['words']} từ — {parts} "
        f"({'nháp' if draft else 'bản chuẩn'}) ===")

    log("[1/5] Giọng đọc")
    t0 = time.time()
    items = [(ln["text"], ln.get("speaker")) for sc in project["scenes"] for ln in sc["lines"]]
    extra = []  # câu riêng của các bản dọc (kịch bản short viết riêng + câu kết)
    for p in plans:
        p["_audio"] = []
        for sc, li in p["items"]:
            if p["own"]:
                ln = sc["lines"][li]
                p["_audio"].append(len(items) + len(extra))
                extra.append((ln["text"], ln.get("speaker")))
        p["_outro_audio"] = len(items) + len(extra)
        extra.append((p["outro_text"], None))
    paths = synthesize(items + extra, os.path.join(cache, "audio"), project, cfg, log)
    clips, durations, bounds = load_clips(paths)
    n_long = len(items)
    timeline, total = build_timeline(project, durations[:n_long], cfg, bounds[:n_long])
    _save_json(os.path.join(cache, "timeline.json"), {"total": total, "voice": pick_voice(project, cfg),
                                                      "scenes": timeline})
    _log_time(log, f"thuyết minh dài {total / 60:.1f} phút", t0)

    log("[2/5] Vẽ các cảnh")
    t0 = time.time()
    draw = draw_enabled(project, cfg)
    shots = render_shots(project, os.path.join(cache, "frames"), log, draw=draw)
    _log_time(log, "xong" + (" (có hiệu ứng vẽ tay)" if draw else ""), t0)
    if subs is None:  # CLI --subs > scenes.json burn_subtitles > config.json burn_subtitles
        subs = project.get("burn_subtitles", cfg.get("burn_subtitles", False))
    fps = 12 if draft else cfg.get("fps", 24)
    preset, crf = ("ultrafast", 30) if draft else ("veryfast", cfg.get("crf", 20))
    speakers = project.get("voices") or {}

    long_info = state.get("long")
    if long:
        log("[3/5] Video dài 16:9")
        t0 = time.time()
        mix = mix_audio(timeline, clips, total, cfg, base_dir, log, _draw_times(timeline, shots))
        mix_path = os.path.join(cache, "mix.wav")
        A.write_wav(mix_path, mix)
        if subs:
            log("  + phụ đề karaoke in trên hình")
        size = (960, 540) if draft else (W, H)
        prog = None
        if project.get("progress_items"):
            prog = Progress(project["progress_items"], size)
            log("  + bảng tiến độ ở góc")
        video = os.path.join(vid_dir or yt_dir, f"{slug}{'_draft' if draft else ''}.mp4")
        encode_video(timeline, shots, total, mix_path, video, fps, size, preset, crf, log, subs,
                     _brand_watermark(project, timeline, total, log), progress=prog, speakers=speakers)
        srt = os.path.join(yt_dir, f"{slug}.srt")
        write_srt(timeline, srt)
        thumb = publish.write_thumbnail(project, publish.load_seo(project_dir), os.path.join(yt_dir, "thumbnail.png"), log)
        long_info = {"video": video, "srt": srt, "thumbnail": thumb, "duration": round(total, 2), "draft": draft}
        _log_time(log, video, t0)
    else:
        log("[3/5] Video dài: bỏ qua (--short-only)")

    shorts_info = state.get("shorts") or ([dict(state["short"], id="main")] if state.get("short") else [])
    if short:
        log(f"[4/5] Bản dọc 9:16 (Shorts · TikTok · Reels): {len(plans)} bản")
        shorts_info = []
        offs, k = {}, 0
        for sc in project["scenes"]:
            offs[id(sc)] = k
            k += len(sc["lines"])
        size = (540, 960) if draft else (vertical.VW, vertical.VH)
        for p in plans:
            t0 = time.time()
            idx = [(offs[id(sc)] + li) for sc, li in p["items"]] if not p["own"] else list(p["_audio"])
            idx.append(p["_outro_audio"])
            segs, s_total, refs = vertical.timeline(p, [durations[i] for i in idx],
                                                    [bounds[i] for i in idx], cfg)
            layout = vertical.Layout(project, p, size, s_total, segs)
            s_shots = vertical.render_shots(p, refs, os.path.join(cache, "frames_v"), layout, draw)
            s_mix = mix_audio(segs, [clips[i] for i in idx], s_total, cfg, base_dir, lambda *_: None,
                              _draw_times(segs, s_shots))
            s_mix_path = os.path.join(cache, f"mix_short_{p['id']}.wav")
            A.write_wav(s_mix_path, s_mix)
            out_dir = os.path.join(pub, p["folder"])
            os.makedirs(out_dir, exist_ok=True)
            name = f"{slug}_{'short' if p['id'] == 'main' else p['id']}"
            video = os.path.join(vid_dir or out_dir, f"{name}{'_draft' if draft else ''}.mp4")
            encode_video(segs, s_shots, s_total, s_mix_path, video, fps, size, preset, crf, log, True, None, layout,
                         speakers=speakers)
            srt = os.path.join(out_dir, f"{name}.srt")
            write_srt(segs, srt)
            cover = publish.write_cover(project, publish.load_seo(project_dir), p, s_shots, segs,
                                        os.path.join(out_dir, "cover.png"), log)
            _save_json(os.path.join(cache, f"short_timeline_{p['id']}.json"), {"total": s_total, "scenes": segs})
            shorts_info.append({"id": p["id"], "folder": p["folder"], "video": video, "srt": srt, "cover": cover,
                                "duration": round(s_total, 2), "draft": draft, "hook": p["hook"]})
            _log_time(log, f"{video} ({s_total:.0f}s)", t0)
    else:
        log("[4/5] Bản dọc: bỏ qua (--no-short)")

    log("[5/5] Metadata YouTube · Shorts · TikTok · Reels")
    _save_json(state_file, {"long": long_info, "shorts": shorts_info})
    publish.write_all(project, project_dir, pub, long_info, shorts_info, chapters(timeline), log)
    log(f"[✓] Hoàn tất sau {time.time() - T0:.0f}s → {pub} (mở PUBLISH.md)")
    for w in warnings:
        log(f"  [⚠] {w}")
    return {"video": (long_info or {}).get("video"), "shorts": [s["video"] for s in shorts_info],
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
    shorts = state.get("shorts") or ([dict(state["short"], id="main", folder="short")] if state.get("short") else [])
    publish.write_all(project, project_dir, pub, state.get("long"), shorts, chapters(tl["scenes"]), log)
    return os.path.join(pub, "PUBLISH.md")
