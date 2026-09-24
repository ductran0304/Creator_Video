"""Chữ viết tay (font Pangolin, OFL) — đo độ rộng thật bằng Pillow để xuống dòng/thu nhỏ chính xác."""
import os
from functools import lru_cache
from xml.sax.saxutils import escape

from PIL import ImageFont

from .palette import C

FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Pangolin-Regular.ttf")
FONT_FAMILY = "Pangolin"
_REF_SIZE = 100


@lru_cache(maxsize=1)
def _font():
    return ImageFont.truetype(FONT_PATH, _REF_SIZE)


def text_width(text, size):
    # +8% cho nét "đậm giả" (stroke cùng màu) vẽ quanh chữ
    return _font().getlength(text) * size / _REF_SIZE * 1.08


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
    color = color or C["red_text"]
    lines, size = fit(text, max_w, size, max_lines)
    lh = size * 1.1
    top = cy - lh * (len(lines) - 1) / 2
    if outline:
        stroke = f' stroke="{outline}" stroke-width="{max(5, size * 0.12):.1f}"'
    else:
        stroke = f' stroke="{color}" stroke-width="{max(1.5, size * 0.045):.1f}"'
    out = []
    for i, line in enumerate(lines):
        y = top + i * lh
        rot = pen.jitter(0, tilt) if tilt else 0
        out.append(f'<text x="{cx:.0f}" y="{y:.0f}" text-anchor="middle" dominant-baseline="central" '
                   f'font-family="{FONT_FAMILY}" font-size="{size}" fill="{color}"{stroke} '
                   f'paint-order="stroke" stroke-linejoin="round" '
                   f'transform="rotate({rot:.2f} {cx:.0f} {y:.0f})">{escape(line)}</text>')
    w = max(text_width(l, size) for l in lines) if lines else 0
    return "".join(out), (w, lh * len(lines))
