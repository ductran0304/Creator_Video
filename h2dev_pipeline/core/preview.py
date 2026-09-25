"""Vẽ nháp các cảnh + ghép bảng tổng hợp (contact sheet) để Claude/người dùng xem nhanh."""
import io
import math
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

from doodle.scene import scene_svg, render_png
from doodle.text import FONT_PATH
from .project import line_states, scene_seed, final_state

THUMB = (480, 270)
PER_SHEET = 20  # 4 cột x 5 hàng


def _badge(img, text):
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 30)
    w = d.textlength(text, font=font) + 20
    y = img.height - 48  # góc dưới-trái: tiêu đề cảnh thường nằm ở trên
    d.rounded_rectangle([6, y, 6 + w, y + 42], radius=10, fill="#141414")
    d.text((16, y + 3), text, font=font, fill="#FFFFFF")
    return img


def _sheet(images, cols=4):
    rows = math.ceil(len(images) / cols)
    sheet = Image.new("RGB", (cols * THUMB[0] + (cols + 1) * 8, rows * THUMB[1] + (rows + 1) * 8), "#FFFFFF")
    for i, img in enumerate(images):
        sheet.paste(img, (8 + (i % cols) * (THUMB[0] + 8), 8 + (i // cols) * (THUMB[1] + 8)))
    return sheet


def _png_to_img(png):
    return Image.open(io.BytesIO(png)).convert("RGB")


def preview_all(project, project_dir):
    """Vẽ trạng thái cuối của mọi cảnh. Trả về danh sách đường dẫn contact sheet."""
    out = os.path.join(project_dir, "preview")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    thumbs = []
    for i, sc in enumerate(project["scenes"], 1):
        spec, visible = final_state(sc)
        img = _png_to_img(render_png(scene_svg(spec, None, visible, scene_seed(sc))))
        img.save(os.path.join(out, f"scene_{i:02d}.png"))
        thumbs.append(_badge(img.resize(THUMB), f"{i} · {len(sc.get('lines', []))} câu"))
    sheets = []
    for k in range(0, len(thumbs), PER_SHEET):
        p = os.path.join(out, f"sheet_{k // PER_SHEET + 1}.png")
        _sheet(thumbs[k:k + PER_SHEET]).save(p)
        sheets.append(p)
    return sheets


def preview_scene_steps(project, project_dir, n):
    """Vẽ từng bước hiện dần (mỗi câu thoại một hình) của cảnh số n (bắt đầu từ 1)."""
    scenes = project["scenes"]
    if not 1 <= n <= len(scenes):
        raise ValueError(f"Cảnh {n} không tồn tại (có {len(scenes)} cảnh)")
    sc = scenes[n - 1]
    out = os.path.join(project_dir, "preview")
    os.makedirs(out, exist_ok=True)
    from .build import _focus_view
    thumbs = []
    for k, st in enumerate(line_states(sc), 1):
        boxes = {}
        svg = scene_svg(st["spec"], None, st["visible"], st["seed"], boxes)
        img = _png_to_img(render_png(svg))
        tag = ""
        if st["focus"] in boxes:  # mô phỏng camera cận cảnh
            cx, cy, z = _focus_view(boxes[st["focus"]])
            bw, bh = img.width / z, img.height / z
            x = min(max(img.width * cx, bw / 2), img.width - bw / 2)
            y = min(max(img.height * cy, bh / 2), img.height - bh / 2)
            img = img.crop((int(x - bw / 2), int(y - bh / 2), int(x + bw / 2), int(y + bh / 2)))
            tag = " [focus]"
        if st["cut"]:
            tag = " [cut]" + tag
        text = sc["lines"][k - 1]["text"]
        thumbs.append(_badge(img.resize(THUMB), f"câu {k}{tag}: {text[:22]}{'…' if len(text) > 22 else ''}"))
    p = os.path.join(out, f"scene_{n:02d}_steps.png")
    _sheet(thumbs, cols=min(4, len(thumbs))).save(p)
    return p
