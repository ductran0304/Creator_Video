"""Danh mục bộ vẽ doodle.

python -m doodle.catalog --json          → in toàn bộ từ vựng (frame, element, variant, pose, prop...)
python -m doodle.catalog <thư_mục_ra>    → vẽ các bảng xem trước (nhân vật, tư thế, biểu cảm, đồ vật, nền)
"""
import io
import json
import math
import os
import sys

from PIL import Image

from .backgrounds import BACKGROUNDS_DESC
from .character import VARIANTS, POSES, EXPRESSIONS, EXTRAS, OUTFITS
from .props import PROPS
from .scene import FRAMES, ELEMENT_TYPES, render_png, W, H
from .pen import Pen
from .props import draw_prop
from .text import text_block
from .palette import C


def vocabulary():
    return {
        "frames": FRAMES,
        "element_types": ELEMENT_TYPES,
        "backgrounds": BACKGROUNDS_DESC,
        "variants": VARIANTS,
        "poses": list(POSES),
        "expressions": EXPRESSIONS,
        "extras": EXTRAS,
        "outfits": OUTFITS,
        "props": {k: m["desc"] for k, m in PROPS.items()},
        "holdable_props": [k for k, m in PROPS.items() if m["grip"]],
        "sky_props": [k for k, m in PROPS.items() if m["anchor"] == "center"],
        "label_colors": ["red", "white", "black", "orange", "yellow", "blue", "green"],
    }


def _sheet(pngs, cols, cell=(640, 360)):
    rows = math.ceil(len(pngs) / cols)
    sheet = Image.new("RGB", (cols * cell[0] + (cols + 1) * 8, rows * cell[1] + (rows + 1) * 8), "#FFFFFF")
    for i, png in enumerate(pngs):
        img = Image.open(io.BytesIO(png)).resize(cell)
        sheet.paste(img, (8 + (i % cols) * (cell[0] + 8), 8 + (i // cols) * (cell[1] + 8)))
    return sheet


def _grid_svg(items, draw, cols, title_of):
    """Vẽ nhiều ô nhỏ lên MỘT khung 1920x1080 (dùng cho danh mục props/poses)."""
    pen = Pen(7)
    rows = math.ceil(len(items) / cols)
    cw, ch = W / cols, H / rows
    body = f'<rect width="{W}" height="{H}" fill="{C["cream"]}"/>'
    for i, it in enumerate(items):
        cx, top = cw * (i % cols) + cw / 2, ch * (i // cols)
        body += draw(pen, it, cx, top, cw, ch)
        body += text_block(pen, title_of(it), cx, top + ch - 22, cw * 0.95, 30, C["ink"], None, 1, tilt=0)[0]
        body += f'<rect x="{cw*(i%cols):.0f}" y="{top:.0f}" width="{cw:.0f}" height="{ch:.0f}" fill="none" stroke="#DDD"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{body}</svg>'


def _prop_cell(pen, name, cx, top, cw, ch):
    m = PROPS[name]
    s = min((cw * 0.8) / (2 * m["w"]), (ch - 60) * 0.85 / m["h"], 1.0)
    y = top + (ch - 45) if m["anchor"] == "bottom" else top + (ch - 45) / 2
    return draw_prop(pen, name, cx, y, s, {"bg_color": C["cream"]})


def render_catalog(out_dir):
    from .scene import scene_svg
    os.makedirs(out_dir, exist_ok=True)
    paths = []

    def save(name, png):
        p = os.path.join(out_dir, name)
        with open(p, "wb") as f:
            f.write(png)
        paths.append(p)

    # 1. đồ vật
    names = list(PROPS)
    for k in range(0, len(names), 24):
        chunk = names[k:k + 24]
        save(f"catalog_props_{k // 24 + 1}.png", render_png(_grid_svg(chunk, _prop_cell, 6, lambda n: n)))

    # 2. tư thế (you_main) và biến thể nhân vật
    poses = list(POSES)
    per_row = math.ceil(len(poses) / 2)
    spec = {"frame": "scene", "bg": "neutral_default", "elements": []}
    for i, p in enumerate(poses):
        col, row = i % per_row, i // per_row
        x = (col + 0.5) / per_row
        spec["elements"].append({"type": "character", "pose": p, "x": x, "y": 0.4 + row * 0.47, "scale": 0.72})
        spec["elements"].append({"type": "label", "text": p, "x": x, "y": 0.45 + row * 0.47, "size": 40,
                                 "color": "black"})
    save("catalog_poses.png", render_png(scene_svg(spec)))

    variants = list(VARIANTS)
    exprs = [e for e in EXPRESSIONS if e != "sleeping"]
    spec = {"frame": "scene", "bg": "neutral_default", "elements": []}
    for i, v in enumerate(variants):
        spec["elements"].append({"type": "character", "variant": v, "x": (i + 0.5) / len(variants), "y": 0.55,
                                 "scale": 0.9})
        spec["elements"].append({"type": "label", "text": v, "x": (i + 0.5) / len(variants), "y": 0.62, "size": 40,
                                 "color": "black"})
    for i, e in enumerate(exprs):
        spec["elements"].append({"type": "character", "expression": e, "x": (i + 0.5) / len(exprs), "y": 0.9,
                                 "scale": 0.62})
        spec["elements"].append({"type": "label", "text": e, "x": (i + 0.5) / len(exprs), "y": 0.955, "size": 30,
                                 "color": "black"})
    save("catalog_characters.png", render_png(scene_svg(spec)))

    # 3. nền
    pngs = [render_png(scene_svg({"frame": "scene", "bg": b, "elements": [
        {"type": "label", "text": b, "y": 0.5, "color": "white"}]})) for b in BACKGROUNDS_DESC]
    _sheet(pngs, 4, (480, 270)).save(os.path.join(out_dir, "catalog_backgrounds.png"))
    paths.append(os.path.join(out_dir, "catalog_backgrounds.png"))
    return paths


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(vocabulary(), ensure_ascii=False, indent=1))
    else:
        print("\n".join(render_catalog(sys.argv[1] if len(sys.argv) > 1 else "catalog")))
