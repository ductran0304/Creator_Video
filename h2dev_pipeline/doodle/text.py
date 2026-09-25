"""Chữ trên hình. Mặc định: chữ viết tay (font Pangolin, OFL) nghiêng lệch nhẹ + nét "đậm giả".
Thương hiệu có thể đổi sang font nghiêm chỉnh qua theme (font_family / font_file / font_weight / handwritten=False).
Độ rộng chữ được đo bằng Pillow với đúng file font để xuống dòng/thu nhỏ chính xác."""
import os
from functools import lru_cache
from xml.sax.saxutils import escape

from PIL import ImageFont

from .palette import C

FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Pangolin-Regular.ttf")
FONT_FAMILY = "Pangolin"
_REF_SIZE = 100


def _style():
    from .theme import T
    return (T.get("font_family") or FONT_FAMILY, T.get("font_file") or FONT_PATH, T.get("font_weight"),
            T.get("handwritten", True))


@lru_cache(maxsize=8)
def _font(path=FONT_PATH):
    return ImageFont.truetype(path, _REF_SIZE)


def text_width(text, size):
    family, path, weight, hand = _style()
    # chữ viết tay: +8% cho nét "đậm giả" (stroke cùng màu) vẽ quanh chữ
    return _font(path).getlength(text) * size / _REF_SIZE * (1.08 if hand else 1.02)


def _wrap(text, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and text_width(cand, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def fit(text, max_w, size, max_lines=3, min_size=28):
    """Trả về (lines, size): cỡ chữ lớn nhất ≤ size mà vừa max_w trong tối đa max_lines dòng."""
    while True:
        lines = _wrap(text, size, max_w)
        if size <= min_size or (len(lines) <= max_lines and max(text_width(l, size) for l in lines) <= max_w):
            return lines, size
        size -= 4


def text_block(pen, text, cx, cy, max_w, size, color=None, outline=None, max_lines=3, tilt=1.6):
    """Khối chữ canh giữa tại (cx, cy). Trả về (svg, (w, h))."""
    from .theme import T
    family, _, weight, hand = _style()
    color = color or T["title"]
    lines, size = fit(text, max_w, size, max_lines)
    lh = size * (1.1 if hand else 1.18)
    top = cy - lh * (len(lines) - 1) / 2
    if outline:
        stroke = f' stroke="{outline}" stroke-width="{max(5, size * (0.12 if hand else 0.09)):.1f}"'
    elif hand:
        stroke = f' stroke="{color}" stroke-width="{max(1.5, size * 0.045):.1f}"'
    else:
        stroke = ""  # font nghiêm chỉnh đã có độ đậm thật, không cần nét giả
    weight_attr = f' font-weight="{weight}"' if weight else ""
    out = []
    for i, line in enumerate(lines):
        y = top + i * lh
        rot = pen.jitter(0, tilt) if tilt else 0
        if not hand:
            rot = 0
        out.append(f'<text x="{cx:.0f}" y="{y:.0f}" text-anchor="middle" dominant-baseline="central" '
                   f'font-family="{family}" font-size="{size}"{weight_attr} fill="{color}"{stroke} '
                   f'paint-order="stroke" stroke-linejoin="round" '
                   f'transform="rotate({rot:.2f} {cx:.0f} {y:.0f})">{escape(line)}</text>')
    w = max(text_width(l, size) for l in lines) if lines else 0
    return "".join(out), (w, lh * len(lines))
