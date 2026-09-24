"""Ghép một cảnh (dict JSON do Claude viết) thành SVG rồi PNG 1920x1080."""
import json
import zlib
from xml.sax.saxutils import escape

import resvg_py

from .pen import Pen, INK
from .character import character
from .props import PROPS
from .backgrounds import BACKGROUNDS, DARK

W, H = 1920, 1080
FONT = "Comic Sans MS"
RED = "#E0241B"


def _wrap(text, max_chars):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def text_block(pen, text, cx, cy, max_w, size, color=RED, outline=None, max_lines=3, measure=False):
    """Chữ viết tay kiểu bút lông: tự thu nhỏ cho vừa khung, mỗi dòng nghiêng nhẹ ngẫu nhiên."""
    char_w = 0.66 if text.isupper() else 0.56
    while size > 28:
        lines = _wrap(text, max(1, int(max_w / (size * char_w))))
        if len(lines) <= max_lines and max(len(l) for l in lines) * size * char_w <= max_w:
            break
        size -= 6
    lh = size * 1.12
    if measure:
        return "", lh * len(lines)
    top = cy - lh * (len(lines) - 1) / 2
    stroke = (f' stroke="{outline}" stroke-width="{max(4, size * 0.07):.0f}" paint-order="stroke" '
              f'stroke-linejoin="round"') if outline else ""
    out = []
    for i, line in enumerate(lines):
        y = top + i * lh
        rot = pen.jitter(0, 1.6)
        out.append(f'<text x="{cx:.0f}" y="{y:.0f}" text-anchor="middle" dominant-baseline="central" '
                   f'font-family="{FONT}" font-weight="bold" font-size="{size}" fill="{color}"{stroke} '
                   f'transform="rotate({rot:.2f} {cx:.0f} {y:.0f})">{escape(line)}</text>')
    return "".join(out)


def render_panel(pen, spec, x0, y0, w, h):
    bg_name = spec.get("bg", "neutral_default")
    bg_svg, ground_y, bg_color = BACKGROUNDS.get(bg_name, BACKGROUNDS["neutral_default"])(pen, x0, y0, w, h)
    dark = bg_name in DARK
    base = h / H
    parts = [bg_svg]
    for el in spec.get("elements", []):
        kind = el.get("type")
        ex = x0 + w * el.get("x", 0.5)
        ey = y0 + h * el["y"] if "y" in el else ground_y
        s = base * el.get("scale", 1.0)
        if kind == "character":
            svg, anchors = character(pen, ex, ey, el.get("variant", "you_main"), el.get("pose", "standing"),
                                     el.get("expression", "calm_content"), s, el.get("flip", False),
                                     el.get("extras", []))
            parts.append(svg)
            if el.get("holding") in PROPS:
                parts.append(PROPS[el["holding"]](pen, ex, ey, 1.0, {"hand": anchors["hand"], "char_scale": s}))
        elif kind == "prop" and el.get("name") in PROPS:
            parts.append(PROPS[el["name"]](pen, ex, ey, s, {"bg_color": bg_color}))
        elif kind == "label":
            ly = y0 + h * el.get("y", 0.14)
            color = {"red": RED, "white": "#FFFFFF", "black": INK}.get(el.get("color", "red"), RED)
            outline = INK if dark or color == "#FFFFFF" else None
            parts.append(text_block(pen, el["text"], ex, ly, w * 0.86, int(el.get("size", 110) * base * 1.0),
                                    color, outline))
        elif kind == "svg":  # đồ vật tự vẽ ngoài thư viện
            parts.append(f'<g transform="translate({ex:.1f},{ey:.1f}) scale({s})">{el["markup"]}</g>')
    return "".join(parts)


def scene_svg(spec):
    pen = Pen(zlib.crc32(json.dumps(spec, sort_keys=True).encode()))
    frame = spec.get("frame", "scene")
    body = []
    if frame == "concept_text":
        bg_svg, _, _ = BACKGROUNDS["neutral_default"](pen, 0, 0, W, H)
        body.append(bg_svg)
        main_svg, main_h = text_block(pen, spec["text"], 0, 0, W * 0.84, 250, RED, measure=True)
        sub_h = 110 if spec.get("sub") else 0
        top = (H - main_h - sub_h) / 2
        body.append(text_block(pen, spec["text"], W / 2, top + main_h / 2, W * 0.84, 250, RED))
        if sub_h:
            body.append(text_block(pen, spec["sub"], W / 2, top + main_h + sub_h / 2 + 10, W * 0.7, 70, INK))
    elif frame == "split":
        half = W / 2
        for i, side in enumerate(("left", "right")):
            panel = spec.get(side, {})
            body.append(f'<clipPath id="c{i}"><rect x="{i*half}" y="0" width="{half}" height="{H}"/></clipPath>')
            inner = render_panel(pen, panel, i * half, 0, half, H)
            if panel.get("title"):
                dark = panel.get("bg") in DARK
                inner += text_block(pen, panel["title"], i * half + half / 2, H * 0.12, half * 0.8, 120, RED,
                                    INK if dark else None)
            body.append(f'<g clip-path="url(#c{i})">{inner}</g>')
        body.append(pen.line([(half, -10), (half, H + 10)], width=12, amp=3))
    else:
        body.append(render_panel(pen, spec, 0, 0, W, H))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            + "".join(body) + "</svg>")


def render_scene(spec, out_path):
    png = resvg_py.svg_to_bytes(svg_string=scene_svg(spec))
    with open(out_path, "wb") as f:
        f.write(bytes(png))
    return out_path
