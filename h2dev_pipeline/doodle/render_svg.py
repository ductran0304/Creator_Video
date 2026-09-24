"""Render file SVG → PNG bằng đúng bộ render của pipeline (resvg + font Pangolin), để tự kiểm tra asset.

python -m doodle.render_svg a.svg b.svg ...        → a.png, b.png cạnh file gốc
python -m doodle.render_svg --sheet out.png *.svg  → ghép tất cả thành một bảng xem nhanh
"""
import io
import math
import os
import sys

from PIL import Image

from .scene import render_png


def render_file(path):
    with open(path, "r", encoding="utf-8") as f:
        png = render_png(f.read())
    out = os.path.splitext(path)[0] + ".png"
    with open(out, "wb") as f:
        f.write(png)
    return out, png


def main(argv):
    sheet = None
    if argv and argv[0] == "--sheet":
        sheet, argv = argv[1], argv[2:]
    imgs = []
    for p in argv:
        try:
            out, png = render_file(p)
            print(f"[ok] {out}")
            imgs.append(Image.open(io.BytesIO(png)).convert("RGB"))
        except Exception as e:  # SVG hỏng → báo rõ để sửa
            print(f"[LỖI] {p}: {e}")
    if sheet and imgs:
        cell = 480
        cols = min(4, len(imgs))
        rows = math.ceil(len(imgs) / cols)
        board = Image.new("RGB", (cols * (cell + 8) + 8, rows * (cell + 8) + 8), "#DDDDDD")
        for i, im in enumerate(imgs):
            im.thumbnail((cell, cell))
            board.paste(im, (8 + (i % cols) * (cell + 8), 8 + (i // cols) * (cell + 8)))
        board.save(sheet)
        print(f"[ok] {sheet}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
