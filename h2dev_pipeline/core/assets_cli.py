"""Thêm asset mới cho thư viện (cách B): đăng ký metadata → Sonnet vẽ SVG → kiểm tra.

  asset new <name> --w W --h H --desc "..." [--center] [--grip X,Y] [--label CX,CY,W]
  asset new <name> --bg --ground-top N --feet-y N --sky "#hex" [--dark] --desc "..."
  asset check [name ...]      (bỏ trống = mọi asset có file .json)
"""
import io
import json
import math
import os
import re

import resvg_py
from PIL import Image, ImageDraw

from doodle import assets
from doodle.scene import scene_svg, render_png
from doodle.text import FONT_PATH

FORBIDDEN = re.compile(r"Gradient|<filter|\bfilter=|<mask|\bmask=|<pattern|<image|<text|<style|<script|@keyframes",
                       re.I)
MAX_KB = {"props": 15, "backgrounds": 50}


def _known_names():
    from doodle.props import PROPS
    from doodle.backgrounds import BACKGROUNDS
    return set(PROPS) | set(BACKGROUNDS)


def cmd_new(a):
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", a.name):
        print("[LỖI] Tên asset: chữ thường không dấu, số, gạch dưới (vd bone_needle)")
        return 1
    if a.name in _known_names():
        print(f"[LỖI] '{a.name}' đã có trong thư viện — dùng luôn, hoặc chọn tên khác")
        return 1
    if a.bg:
        kind = "backgrounds"
        if a.ground_top is None or a.feet_y is None:
            print("[LỖI] Nền cần --ground-top và --feet-y (theo khung 1080px)")
            return 1
        meta = {"desc": a.desc, "ground_top": a.ground_top, "feet_y": a.feet_y, "sky": a.sky or "#F5F1E6",
                "dark": bool(a.dark)}
    else:
        kind = "props"
        if not a.w or not a.h:
            print("[LỖI] Đồ vật cần --w (nửa bề ngang) và --h (chiều cao) ở khung 1080px")
            return 1
        meta = {"desc": a.desc, "w": a.w, "h": a.h, "anchor": "center" if a.center else "bottom"}
        if a.grip:
            meta["grip"] = [float(v) for v in a.grip.split(",")]
        if a.label:
            meta["label_box"] = [float(v) for v in a.label.split(",")]
    os.makedirs(os.path.join(assets.ASSET_DIR, kind), exist_ok=True)
    p = assets.path(kind, a.name, ".json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"[✓] Đã đăng ký {kind}/{a.name}.json — cần vẽ {assets.path(kind, a.name)}")
    if kind == "props":
        W, H = meta["w"], meta["h"]
        vb = f"{-W:g} {-H / 2:g} {2 * W:g} {H:g}" if a.center else f"{-W:g} {-H:g} {2 * W:g} {H:g}"
        print(f"    viewBox bắt buộc: \"{vb}\"")
    return 0


def _viewbox(svg):
    m = re.search(r"<svg\b[^>]*\bviewBox\s*=\s*\"([^\"]+)\"", svg)
    return [float(v) for v in re.split(r"[\s,]+", m.group(1).strip())] if m else None


def _check_one(name):
    """Trả về (kind, lỗi[], cảnh báo[])."""
    kind = next((k for k in ("props", "backgrounds") if os.path.exists(assets.path(k, name, ".json"))
                 or os.path.exists(assets.path(k, name))), None)
    if not kind:
        return None, [f"không có asset '{name}'"], []
    errs, warns = [], []
    svg_path = assets.path(kind, name)
    if not os.path.exists(svg_path):
        return kind, [f"thiếu file {svg_path}"], []
    with open(svg_path, "r", encoding="utf-8") as f:
        svg = f.read()
    kb = len(svg.encode()) / 1024
    if kb > MAX_KB[kind]:
        warns.append(f"file {kb:.0f} KB > {MAX_KB[kind]} KB")
    bad = sorted(set(m.group(0) for m in FORBIDDEN.finditer(svg)))
    if bad:
        errs.append(f"dùng tính năng bị cấm: {', '.join(bad)}")
    vb = _viewbox(svg)
    meta = assets.sidecars(kind).get(name)
    if kind == "props":
        from doodle.props import PROPS
        m = PROPS.get(name) or meta
        if m:
            W, H = m["w"], m["h"]
            want = [-W, -H / 2, 2 * W, H] if m.get("anchor") == "center" else [-W, -H, 2 * W, H]
            if not vb or any(abs(a - b) > 0.6 for a, b in zip(vb, want)):
                errs.append(f"viewBox {vb} ≠ bắt buộc {want}")
    else:
        if not vb or any(abs(a - b) > 0.6 for a, b in zip(vb, [0, 0, 1920, 1080])):
            errs.append(f"viewBox {vb} ≠ [0, 0, 1920, 1080]")
    try:
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg))
        img = Image.open(io.BytesIO(png)).convert("RGBA")
        from doodle.props import PROPS
        if kind == "props" and name in PROPS and PROPS[name]["anchor"] == "bottom":
            alpha = img.getchannel("A")
            band = alpha.crop((0, int(img.height * 0.96), img.width, img.height))
            if not band.getbbox():
                errs.append("vật không chạm đất (đáy khung y=0 trống) — sẽ trông như lơ lửng")
    except Exception as e:  # noqa: BLE001 — SVG hỏng
        errs.append(f"không render được: {e}")
    return kind, errs, warns


def _preview_spec(kind, name):
    if kind == "backgrounds":
        return {"frame": "scene", "bg": name, "elements": [
            {"type": "character", "x": 0.35, "scale": 1.1}, {"type": "prop", "name": "campfire", "x": 0.62}]}
    from doodle.props import PROPS
    m = PROPS[name]
    els = []
    if m["grip"]:
        els.append({"type": "character", "pose": "holding", "holding": name, "x": 0.3, "scale": 1.1})
    else:
        els.append({"type": "character", "x": 0.25, "scale": 1.0})
    el = {"type": "prop", "name": name, "x": 0.64}
    if m["anchor"] == "center":
        el["y"] = 0.35
    els.append(el)
    return {"frame": "scene", "bg": "outdoor_daytime", "elements": els}


def cmd_check(a, base_dir):
    names = a.names or sorted(set(assets.sidecars("props")) | set(assets.sidecars("backgrounds")))
    if not names:
        print("[i] Chưa có asset nào đăng ký bằng json.")
        return 0
    thumbs, n_err = [], 0
    for name in names:
        kind, errs, warns = _check_one(name)
        status = "LỖI" if errs else "✓"
        print(f"[{status}] {kind or '?'}/{name}")
        for e in errs:
            print(f"    ✗ {e}")
        for w in warns:
            print(f"    ⚠ {w}")
        n_err += bool(errs)
        if kind and not any("không render" in e or "thiếu file" in e for e in errs):
            try:
                img = Image.open(io.BytesIO(render_png(scene_svg(_preview_spec(kind, name))))).convert("RGB")
                img = img.resize((640, 360))
                d = ImageDraw.Draw(img)
                from PIL import ImageFont
                d.rectangle([0, 322, 640, 360], fill="#141414")
                d.text((10, 326), f"{name}{'  ✗' if errs else ''}", font=ImageFont.truetype(FONT_PATH, 26),
                       fill="#FF6B6B" if errs else "#FFFFFF")
                thumbs.append(img)
            except Exception as e:  # noqa: BLE001
                print(f"    ✗ không đặt được vào cảnh thử: {e}")
                n_err += 1
    if thumbs:
        cols = min(3, len(thumbs))
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new("RGB", (cols * 648 + 8, rows * 368 + 8), "#FFFFFF")
        for i, t in enumerate(thumbs):
            sheet.paste(t, (8 + (i % cols) * 648, 8 + (i // cols) * 368))
        out = os.path.join(assets.ASSET_DIR, "_asset_check.png")
        sheet.save(out)
        print(f"[i] Bảng xem trong cảnh thật (cạnh nhân vật chính): {out}")
    print("[✓] Tất cả đạt." if not n_err else f"[✗] {n_err} asset cần sửa.")
    return 1 if n_err else 0


def add_parser(sub, base_dir):
    p = sub.add_parser("asset", help="thêm/kiểm tra asset mới cho thư viện")
    s = p.add_subparsers(dest="asset_cmd", required=True)
    n = s.add_parser("new")
    n.add_argument("name")
    n.add_argument("--desc", required=True)
    n.add_argument("--w", type=float)
    n.add_argument("--h", type=float)
    n.add_argument("--center", action="store_true")
    n.add_argument("--grip")
    n.add_argument("--label")
    n.add_argument("--bg", action="store_true")
    n.add_argument("--ground-top", type=float)
    n.add_argument("--feet-y", type=float)
    n.add_argument("--sky")
    n.add_argument("--dark", action="store_true")
    n.set_defaults(fn=cmd_new)
    c = s.add_parser("check")
    c.add_argument("names", nargs="*")
    c.set_defaults(fn=lambda a: cmd_check(a, base_dir))
