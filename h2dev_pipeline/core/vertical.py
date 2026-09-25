"""Bản dọc 9:16 (YouTube Shorts / TikTok / Reels) cắt từ chính video dài.

scenes.json (tuỳ chọn):
  "short": {
    "lines": ["1", "3.1-3.4", "5.4"],   # cảnh (đánh số từ 1) · "S.L" một câu · "S.L-M" hoặc "S.L-S.M" dải câu; mặc định: cả cảnh 1
    "hook": "BỎ THUẾ KHOÁN 2026",        # chữ to ở dải trên cùng; mặc định = title
    "outro": "Xem bản đầy đủ trên kênh nhé."  # câu đọc cuối; mặc định brand.short_outro hoặc câu chung
  }

Giọng đọc, ảnh từng cú máy và camera dùng lại y nguyên video dài (đã cache), nên dựng bản dọc chỉ tốn thời gian
encode. Bố cục 1080x1920: dải hook trên cùng · khung 16:9 ở giữa (kèm thanh tiến độ) · phụ đề to · logo + CTA —
tất cả nằm trong vùng an toàn, tránh chỗ nút bấm/caption của TikTok/Reels (mép phải và ~1/5 dưới cùng).
"""
import io
import os
import re

from PIL import Image, ImageDraw, ImageFont

VW, VH = 1080, 1920
FRAME_Y = 520                      # khung 16:9 (1080x608) đặt từ y này
FRAME_H = 608
HOOK_BOX = (60, 150, 1020, 490)    # vùng chữ hook
SUB_TOP, SUB_MAX_W = 1175, 840     # phụ đề: mép trên, bề ngang tối đa (chừa cột nút bấm bên phải)
FOOT_Y = 1410                      # logo + CTA
LEAD_IN, TAIL = 0.25, 1.2
DEFAULT_OUTRO = {"en": "Watch the full story on the channel.", "vi": "Xem bản đầy đủ trên kênh nhé."}
DEFAULT_LOOK = {"background": "#1B1B24", "title_color": "#FFFFFF", "accent": "#F58220", "text_color": "#E8E8EE"}


class ShortError(Exception):
    pass


# ---------------- chọn câu ----------------
def _parse_ref(ref, scenes):
    """'3' | '3.2' | '3.2-4' | 3 → list (si, li) 0-based."""
    m = re.fullmatch(r"\s*(\d+)(?:\.(\d+)(?:\s*-\s*(?:(\d+)\.)?(\d+))?)?\s*", str(ref))
    if not m or (m.group(3) and m.group(3) != m.group(1)):
        raise ShortError(f"short.lines: '{ref}' sai cú pháp (dùng 'S', 'S.L' hoặc 'S.L-M', đánh số từ 1; dải câu phải trong cùng một cảnh)")
    s = int(m.group(1)) - 1
    if not 0 <= s < len(scenes):
        raise ShortError(f"short.lines: '{ref}' — không có cảnh {s + 1}")
    n = len(scenes[s].get("lines", []))
    a = int(m.group(2)) - 1 if m.group(2) else 0
    b = int(m.group(4)) - 1 if m.group(4) else (a if m.group(2) else n - 1)
    if not (0 <= a <= b < n):
        raise ShortError(f"short.lines: '{ref}' — cảnh {s + 1} chỉ có {n} câu")
    return [(s, i) for i in range(a, b + 1)]


def plan(project):
    """→ dict(items=[(si, li)], hook, outro_text, outro_scene). Ném ShortError nếu cấu hình sai."""
    cfg = project.get("short") or {}
    scenes = project["scenes"]
    refs = cfg.get("lines") or ["1"]
    items = []
    for r in refs:
        for it in _parse_ref(r, scenes):
            if it not in items:
                items.append(it)
    brand = project.get("_brand") or {}
    lang = project.get("language", "en")
    outro_text = cfg.get("outro") or brand.get("short_outro") or DEFAULT_OUTRO.get(lang, DEFAULT_OUTRO["en"])
    outro_scene = next((i for i, s in enumerate(scenes) if s.get("_auto_outro")), None)
    if outro_scene is not None and any(si == outro_scene for si, _ in items):
        outro_scene = None  # đã chọn thẳng màn kết thì không thêm lần nữa
    return {"items": items, "hook": cfg.get("hook") or project.get("title", ""), "outro_text": outro_text,
            "outro_scene": outro_scene}


def check(project, wpm):
    """Lỗi/cảnh báo cho mục short (dùng trong validate). Trả (errors, warnings, ước lượng giây)."""
    from .project import words
    try:
        p = plan(project)
    except ShortError as e:
        return [str(e)], [], 0
    scenes = project["scenes"]
    n_words = sum(words(scenes[si]["lines"][li]["text"]) for si, li in p["items"]) + words(p["outro_text"])
    secs = n_words / wpm * 60 * 0.85 + 0.3 * len(p["items"])  # edge-tts đọc nhanh hơn WPM ước lượng ~15%
    warnings = []
    if secs > 60:
        warnings.append(f"Bản dọc (short) ước ~{secs:.0f}s > 60s — Shorts/Reels/TikTok giữ chân tốt nhất ở 30–60s; "
                        "bớt câu trong short.lines")
    if secs < 15:
        warnings.append(f"Bản dọc (short) chỉ ~{secs:.0f}s — nên 30–60s (thêm câu vào short.lines)")
    if len(p["hook"]) > 60:
        warnings.append(f"short.hook dài {len(p['hook'])} ký tự — nên ≤ 40 để đọc kịp trên điện thoại")
    return [], warnings, secs


def timeline(project, p, durations, cfg):
    """Dòng thời gian bản dọc. durations: theo thứ tự p['items'] rồi câu outro.
    → (segments, total, shot_refs) — shot_refs[seg][k] = (si, li) để lấy ảnh cú máy của video dài."""
    line_gap = cfg.get("line_gap", 0.25)
    seg_gap = 0.35
    t = LEAD_IN
    segs, refs = [], []
    k = 0
    scenes = project["scenes"]
    for si, li in p["items"]:
        new = not segs or refs[-1][-1][0] != si or refs[-1][-1][1] + 1 != li
        if new:
            if segs:
                t += seg_gap - line_gap
            segs.append({"index": len(segs), "start": t, "lines": [], "chapter": None})
            refs.append([])
        ln = scenes[si]["lines"][li]
        d = durations[k]
        segs[-1]["lines"].append({"text": ln["text"], "sub": ln.get("sub") or ln["text"], "start": t, "end": t + d,
                                  "audio_index": k, "reveal": bool(ln.get("show")) and bool(segs[-1]["lines"]),
                                  "nosub": False})
        refs[-1].append((si, li))
        t += d + line_gap
        k += 1
    # câu kết: màn thương hiệu (nếu có) hoặc giữ nguyên cú máy cuối
    d = durations[k]
    ln = {"text": p["outro_text"], "sub": p["outro_text"], "audio_index": k, "reveal": False}
    if p["outro_scene"] is not None:
        t += seg_gap - line_gap
        segs.append({"index": len(segs), "start": t, "lines": [], "chapter": None})
        refs.append([])
        ln["nosub"] = True
        refs[-1].append((p["outro_scene"], 0))
    else:
        ln["nosub"] = False
        refs[-1].append(refs[-1][-1])
    ln.update(start=t, end=t + d)
    segs[-1]["lines"].append(ln)
    total = t + d + TAIL
    for i, s in enumerate(segs):
        s["end"] = segs[i + 1]["start"] if i + 1 < len(segs) else total
    return segs, total, refs


# ---------------- bố cục ----------------
def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _font_path(look):
    from doodle.text import FONT_PATH
    from doodle.theme import T
    return look.get("_font") or T.get("font_file") or FONT_PATH


def _wrap(draw, text, font, max_w):
    rows, cur = [], ""
    for w in text.split():
        cand = f"{cur} {w}".strip()
        if cur and draw.textlength(cand, font=font) > max_w:
            rows.append(cur)
            cur = w
        else:
            cur = cand
    return rows + ([cur] if cur else [])


def look_for(project):
    brand = project.get("_brand") or {}
    look = dict(DEFAULT_LOOK)
    from doodle.theme import T
    if brand:
        look.update({"background": T.get("title", look["background"]), "accent": T.get("highlight", look["accent"])})
    v = dict(brand.get("vertical") or {})
    look.update({k: val for k, val in v.items() if not k.endswith("_file") and k != "logo"})
    if brand and v.get("font_file"):
        p = os.path.join(brand["_dir"], v["font_file"])
        if os.path.isfile(p):
            look["_font"] = p
    if brand and (v.get("logo") or (brand.get("outro") or {}).get("logo")):
        look["_logo"] = os.path.join(brand["_dir"], v.get("logo") or brand["outro"]["logo"])
    look.setdefault("footer", (project.get("short") or {}).get("footer", ""))
    return look


class Layout:
    """Khung dọc tĩnh vẽ một lần; mỗi khung hình chỉ dán ảnh 16:9 + thanh tiến độ."""

    def __init__(self, project, hook, size=(VW, VH), total=None):
        self.size = size
        self.k = k = size[0] / VW
        self.total = total
        look = self.look = look_for(project)
        self.frame_size = (size[0], int(round(FRAME_H * k)))
        self.frame_pos = (0, int(round(FRAME_Y * k)))
        bg = Image.new("RGB", size, _hex(look["background"]))
        d = ImageDraw.Draw(bg)
        fp = _font_path(look)
        # hook: to nhất có thể, tối đa 3 dòng, căn giữa trong HOOK_BOX
        x0, y0, x1, y1 = [v * k for v in HOOK_BOX]
        text = hook.strip()
        for px in range(104, 50, -4):
            font = ImageFont.truetype(fp, int(px * k))
            rows = _wrap(d, text, font, x1 - x0)
            lh = int(px * 1.18 * k)
            if len(rows) <= 3 and lh * len(rows) <= (y1 - y0):
                break
        y = y0 + ((y1 - y0) - lh * len(rows)) / 2
        for r in rows:
            w = d.textlength(r, font=font)
            d.text(((size[0] - w) / 2, y), r, font=font, fill=_hex(look["title_color"]))
            y += lh
        # vạch nhấn dưới hook
        bar_w = 160 * k
        d.rounded_rectangle([(size[0] - bar_w) / 2, y1 + 4 * k, (size[0] + bar_w) / 2, y1 + 14 * k],
                            radius=int(5 * k), fill=_hex(look["accent"]))
        # logo + CTA
        fy = FOOT_Y * k
        if look.get("_logo"):
            logo = _logo(look["_logo"], int(86 * k))
            if logo is not None:
                bg.paste(logo, (int((size[0] - logo.width) / 2), int(fy)), logo)
                fy += logo.height + 18 * k
        if look.get("footer"):
            font = ImageFont.truetype(fp, int(38 * k))
            for r in _wrap(d, look["footer"], font, SUB_MAX_W * k):
                w = d.textlength(r, font=font)
                d.text(((size[0] - w) / 2, fy), r, font=font, fill=_hex(look["text_color"]))
                fy += 50 * k
        self.base = bg

    def compose(self, frame, t):
        img = self.base.copy()
        img.paste(frame, self.frame_pos)
        if self.total:
            d = ImageDraw.Draw(img)
            y = self.frame_pos[1] + self.frame_size[1]
            h = max(3, int(8 * self.k))
            d.rectangle([0, y, int(self.size[0] * min(1.0, t / self.total)), y + h], fill=_hex(self.look["accent"]))
        return img

    def cover(self, frame_img):
        return self.compose(frame_img.resize(self.frame_size, Image.LANCZOS), 0)

    def subtitles(self, tl):
        from .build import Subtitles
        k = self.k
        return Subtitles(tl, self.size, font_px=int(62 * k), max_w=SUB_MAX_W * k, rows=2, box=False,
                         top=int(SUB_TOP * k), line_h=int(76 * k))


def _logo(svg_path, height):
    try:
        import resvg_py
        from doodle import scene as ds
        from doodle.text import FONT_PATH
        with open(svg_path, "r", encoding="utf-8") as f:
            svg = f.read()
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, height=int(height), skip_system_fonts=True,
                                          font_files=[FONT_PATH] + ds.EXTRA_FONTS))
        return Image.open(io.BytesIO(png)).convert("RGBA")
    except Exception:
        return None
