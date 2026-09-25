"""Ghép một cảnh (dict JSON do Claude viết) thành SVG rồi PNG 1920x1080.

Toạ độ trong JSON: x, y là tỉ lệ 0..1 của khung (hoặc nửa khung với frame=split); bỏ y thì vật đứng
trên mặt đất của nền. Có thể neo tương đối thay vì tự căn x:
- "attach": {"to": <id>, "side": "left"|"right", "gap": px}  — đứng sát trái/phải vật khác
  (nhân vật tự quay mặt về phía vật; tay của tư thế `pushing` chạm đúng mép vật);
- "above": <id>                                         — đặt ngay trên đầu vật/nhân vật khác;
- label "on": <id>                                      — viết chữ lên thân vật (tảng đá, biển gỗ...).
"""
import base64
import json
import math
import os
import zlib
from xml.sax.saxutils import escape as escape_xml

import resvg_py

from .pen import Pen
from .palette import C, NAMED
from .character import character, pose_extents, POSES, VARIANTS, EXPRESSIONS, EXTRAS, OUTFITS
from .props import PROPS, draw_prop, prop_body
from .backgrounds import BACKGROUNDS, DARK
from .text import text_block, FONT_PATH, FONT_FAMILY
from .theme import T

W, H = 1920, 1080
EXTRA_FONTS = []  # font thương hiệu (core/brand.py nạp) — dùng cho logo/màn kết
PHOTO_DIRS = []   # thư mục tìm ảnh thực tế (projects/<slug>/photos, brands/<tên>/photos) — make_video nạp
INK = C["ink"]
RED = C["red_text"]
FRAMES = {
    "scene": "Cảnh tự do: bg + elements",
    "concept_text": "Chữ đỏ lớn giữa nền kem (con số, thuật ngữ): text, sub",
    "split": "Chia đôi so sánh (THEN/NOW, trước/sau): left, right — mỗi bên là một cảnh có title",
    "timeline": "Dòng thời gian ngang: title, events[{label, text, icon}], highlight",
    "stats": "Thanh so sánh số liệu: title, bars[{label, value, display, color}]",
    "photo": "Ảnh thực tế toàn màn hình (B-roll): src, caption",
    "brand_card": "Màn kết thương hiệu (tự thêm từ brands/<tên>/brand.json): logo, headline, card_lines, note",
}
from .cards import CARD_FRAMES, RESPONSIVE  # noqa: E402  (khung thẻ kiểu báo)
FRAMES.update({name: desc for name, (_, desc) in CARD_FRAMES.items()})
ELEMENT_TYPES = {
    "character": "variant, pose, expression, extras[], holding, outfit, flip, scale",
    "prop": "name, scale, flip, cracked",
    "label": "text, color, size, on",
    "thought": "of (id nhân vật), text hoặc prop, side",
    "arrow": "from [x,y], to [x,y] hoặc between [id1, id2]",
    "red_x": "dấu X đỏ lớn phủ cả khung = 'không phải thế này'",
    "photo": "ảnh thực tế dán khung polaroid: src, w (tỉ lệ bề ngang), tilt, caption, frame (polaroid|plain)",
    "svg": "markup SVG tự vẽ (toạ độ cục bộ, gốc ở chân vật)",
}


class SceneError(ValueError):
    pass


def _check(value, allowed, what):
    if value not in allowed:
        raise SceneError(f"{what} '{value}' không hợp lệ. Chọn một trong: {', '.join(sorted(allowed))}")


# ---------------- bố cục ----------------
def _bbox_character(x, y, s, flip, pose):
    mn, mx, top = pose_extents(pose)
    x0, x1 = (x - mx * s, x - mn * s) if flip else (x + mn * s, x + mx * s)
    return {"x0": x0, "x1": x1, "top": y + top * s, "bottom": y, "cx": x, "ground": y}


def _bbox_prop(x, y, s, meta):
    w, h = meta["w"] * s, meta["h"] * s
    if meta["anchor"] == "center":
        return {"x0": x - w, "x1": x + w, "top": y - h / 2, "bottom": y + h / 2, "cx": x, "ground": y + h / 2}
    return {"x0": x - w, "x1": x + w, "top": y - h, "bottom": y, "cx": x, "ground": y}


def _layout(elements, x0, y0, w, h, ground_y, warnings):
    """Tính vị trí tuyệt đối cho từng element (theo thứ tự; neo chỉ được trỏ tới element đứng trước)."""
    base = h / H
    placed, boxes = [], {}
    for i, el in enumerate(elements):
        kind = el.get("type")
        _check(kind, ELEMENT_TYPES, "type")
        s = base * el.get("scale", 1.0)
        x = x0 + w * el.get("x", 0.5)
        y = y0 + h * el["y"] if "y" in el else ground_y
        flip = el.get("flip", False)
        info = {"el": el, "s": s, "x": x, "y": y, "flip": flip, "box": None}

        if kind == "character":
            _check(el.get("variant", "you_main"), VARIANTS, "variant")
            _check(el.get("pose", "standing"), POSES, "pose")
            _check(el.get("expression", "calm_content"), EXPRESSIONS, "expression")
            for fx in el.get("extras", []):
                _check(fx, EXTRAS, "extras")
            if el.get("outfit"):
                _check(el["outfit"], OUTFITS, "outfit")
            if el.get("holding"):
                _check(el["holding"], {k for k, m in PROPS.items() if m["grip"]}, "holding")
        if kind == "prop":
            _check(el.get("name"), PROPS, "prop name")
            if PROPS[el["name"]]["anchor"] == "center" and "y" not in el and "above" not in el:
                info["y"] = y = y0 + h * 0.2

        att = el.get("attach")
        if att and kind in ("character", "prop"):
            t = boxes.get(att.get("to"))
            if not t:
                raise SceneError(f"element #{i}: attach.to '{att.get('to')}' chưa có id ở element phía trước")
            gap = att.get("gap", 0) * base
            side = att.get("side", "left")
            _check(side, {"left", "right"}, "attach.side")
            if kind == "character":
                mn, mx, _ = pose_extents(el.get("pose", "standing"))
                flip = info["flip"] = el.get("flip", side == "right")
                reach = (mx if not flip else -mn) * s
                x = t["x0"] - gap - reach if side == "left" else t["x1"] + gap + reach
            else:
                half = PROPS[el["name"]]["w"] * s
                x = t["x0"] - gap - half if side == "left" else t["x1"] + gap + half
            info["x"] = x
            if "y" not in el:
                info["y"] = y = t["ground"]
        if el.get("above") and kind in ("character", "prop"):
            t = boxes.get(el["above"])
            if not t:
                raise SceneError(f"element #{i}: above '{el['above']}' chưa có id ở element phía trước")
            info["x"] = x = t["cx"]
            gap = 30 * base
            if kind == "prop" and PROPS[el["name"]]["anchor"] == "center":
                info["y"] = y = t["top"] - gap - PROPS[el["name"]]["h"] * s / 2
            else:
                info["y"] = y = t["top"] - gap

        if kind == "photo":
            iw, ih = photo_size(el.get("src"))
            pw = w * el.get("w", 0.4)
            ph = pw * ih / iw
            if "y" not in el:
                info["y"] = y = y0 + h * 0.5
            info["box"] = {"x0": x - pw / 2, "x1": x + pw / 2, "top": y - ph / 2, "bottom": y + ph / 2, "cx": x,
                           "ground": y + ph / 2}
            info["photo_wh"] = (pw, ph)
        if kind == "character":
            info["box"] = _bbox_character(x, y, s, info["flip"], el.get("pose", "standing"))
        elif kind == "prop":
            info["box"] = _bbox_prop(x, y, s, PROPS[el["name"]])
        if info["box"]:
            b = info["box"]
            if b["x0"] < x0 - 5 or b["x1"] > x0 + w + 5 or b["top"] < y0 - 5:
                warnings.append(f"element #{i} ({el.get('variant') or el.get('name')}) bị tràn ra ngoài khung")
            if el.get("id"):
                boxes[el["id"]] = b
        placed.append(info)
    return placed, boxes


# ---------------- thiết bị kể chuyện ----------------
def _thought(pen, info, boxes, placed_by_id, dark):
    el, s = info["el"], info["s"]
    target = placed_by_id.get(el.get("of"))
    if not target or target["el"].get("type") != "character":
        raise SceneError(f"thought.of '{el.get('of')}' phải là id của một nhân vật phía trước")
    b = target["box"]
    side = el.get("side", "left" if target["flip"] else "right")
    d = 1 if side == "right" else -1
    ts = target["s"]
    hx, hy = b["cx"], b["top"] + 40 * ts
    bx, by = hx + d * 230 * ts, b["top"] - 110 * ts
    rx, ry = 175 * ts, 105 * ts
    out = ""
    for k, r in ((0.25, 13), (0.45, 20)):
        out += pen.circle(hx + (bx - hx) * k + d * 40 * ts, hy + (by - hy) * k - 30 * ts, r * ts, C["white"], width=5)
    pts = []
    for j in range(72):
        t = 2 * math.pi * j / 72
        kk = 1 + 0.12 * abs(math.sin(4 * t))
        pts.append((bx + rx * kk * math.cos(t), by + ry * kk * math.sin(t)))
    out += pen.poly(pts, C["white"], amp=1.5)
    if el.get("prop"):
        _check(el["prop"], PROPS, "thought.prop")
        meta = PROPS[el["prop"]]
        ps = min(rx * 1.2 / (2 * meta["w"]), ry * 1.35 / meta["h"])
        py = by + (meta["h"] * ps / 2 if meta["anchor"] == "bottom" else 0)
        out += draw_prop(pen, el["prop"], bx, py, ps, {"bg_color": C["white"]})
    if el.get("text"):
        svg, _ = text_block(pen, el["text"], bx, by, rx * 1.5, int(110 * ts), T["title"], max_lines=2)
        out += svg
    return out


def _arrow(pen, p0, p1, width=14):
    (xa, ya), (xb, yb) = p0, p1
    ang = math.atan2(yb - ya, xb - xa)
    L = 46
    tip = (xb, yb)
    left = (xb - L * math.cos(ang - 0.5), yb - L * math.sin(ang - 0.5))
    right = (xb - L * math.cos(ang + 0.5), yb - L * math.sin(ang + 0.5))
    shaft_end = (xb - L * 0.7 * math.cos(ang), yb - L * 0.7 * math.sin(ang))
    return pen.line([p0, shaft_end], width=width) + pen.poly([tip, left, right], INK, width=5, amp=0.8)


def _red_x(pen, x0, y0, w, h):
    out = ""
    for a, b in (((x0 + w * .12, y0 + h * .12), (x0 + w * .88, y0 + h * .88)),
                 ((x0 + w * .88, y0 + h * .12), (x0 + w * .12, y0 + h * .88))):
        out += pen.line([a, b], width=54, stroke=INK, amp=4) + pen.line([a, b], width=38, stroke=T["alert"], amp=4)
    return out


# ---------------- vẽ khung ----------------
def render_panel(pen, spec, x0, y0, w, h, warnings, visible=None, boxes_out=None):
    root = pen
    bg_name = spec.get("bg", "neutral_default")
    _check(bg_name, BACKGROUNDS, "bg")
    bg_svg, ground_y, bg_color = BACKGROUNDS[bg_name](pen.child('bg'), x0, y0, w, h)
    dark = bg_name in DARK
    base = h / H
    elements = spec.get("elements", [])
    placed, boxes = _layout(elements, x0, y0, w, h, ground_y, warnings)
    if boxes_out is not None:  # khung bao từng element có id (toạ độ khung 1920x1080) — dùng cho camera focus
        boxes_out.update(boxes)
    by_id = {p["el"]["id"]: p for p in placed if p["el"].get("id")}
    labeled = {p["el"]["on"] for p in placed if p["el"].get("type") == "label" and p["el"].get("on")}

    parts = [bg_svg]
    for i, info in enumerate(placed):
        if visible is not None and i not in visible:
            continue
        el, s, x, y, flip = info["el"], info["s"], info["x"], info["y"], info["flip"]
        kind = el["type"]
        pen = root.child(i)
        if kind == "character":
            svg, anchors = character(pen, x, y, el.get("variant", "you_main"), el.get("pose", "standing"),
                                     el.get("expression", "calm_content"), s, flip, el.get("extras", []),
                                     el.get("outfit"))
            parts.append(svg)
            if el.get("holding"):
                meta = PROPS[el["holding"]]
                hs = s * meta["hand_scale"]
                gx, gy = meta["grip"]
                hx, hy = anchors["hand"]
                sx = -hs if flip else hs
                parts.append(f'<g transform="translate({hx - gx * sx:.1f},{hy - gy * hs:.1f}) scale({sx:.3f},{hs:.3f})">'
                             f'{prop_body(pen, el["holding"])}</g>')
        elif kind == "prop":
            ctx = {"bg_color": bg_color, "labeled": el.get("id") in labeled, "cracked": el.get("cracked", False)}
            parts.append(draw_prop(pen, el["name"], x, y, s, ctx, flip))
        elif kind == "label":
            color = (T["alert"] if el.get("color") == "red" else NAMED.get(el["color"], T["label"])) if el.get("color") else T["label"]  # "red" = màu nhấn/cảnh báo của thương hiệu
            if el.get("on"):
                t = by_id.get(el["on"])
                if not t or t["el"].get("type") != "prop":
                    raise SceneError(f"label.on '{el['on']}' phải là id của một prop phía trước")
                meta = PROPS[t["el"]["name"]]
                lcx, lcy, lw = meta["label_box"]
                ts = t["s"]
                color = NAMED.get(el.get("color", "white"), C["white"])
                svg, _ = text_block(pen, el["text"], t["x"] + lcx * ts, t["y"] + lcy * ts, lw * ts,
                                    int(el.get("size", 90) * ts), color,
                                    INK if color == C["white"] else None, max_lines=2)
            else:
                outline = INK if dark or color == C["white"] else None
                # chữ canh giữa tại x nên bề rộng tối đa bị giới hạn bởi mép gần nhất
                max_w = min(w * 0.86, 2 * min(x - x0, x0 + w - x) * 0.94)
                if el.get("width"):  # giới hạn bề ngang (tỉ lệ khung) để chữ xuống dòng, tránh đè nhân vật
                    max_w = min(max_w, w * el["width"])
                svg, _ = text_block(pen, el["text"], x, y0 + h * el.get("y", 0.14), max_w,
                                    int(el.get("size", 110) * base), color, outline)
            parts.append(svg)
        elif kind == "thought":
            parts.append(_thought(pen, info, boxes, by_id, dark))
        elif kind == "arrow":
            if el.get("between"):
                a, b = (boxes.get(k) for k in el["between"])
                if not a or not b:
                    raise SceneError("arrow.between cần 2 id đã khai báo phía trước")
                mid = lambda bb: (bb["top"] + bb["bottom"]) / 2
                yy = (mid(a) + mid(b)) / 2
                p0, p1 = (a["x1"] + 25 * base, yy), (b["x0"] - 25 * base, yy)
            else:
                (fx, fy), (tx, ty) = el["from"], el["to"]
                p0, p1 = (x0 + w * fx, y0 + h * fy), (x0 + w * tx, y0 + h * ty)
            parts.append(_arrow(pen, p0, p1, 14 * max(base, 0.6)))
        elif kind == "red_x":
            parts.append(_red_x(pen, x0, y0, w, h))
        elif kind == "photo":
            parts.append(_photo_card(pen, el, x, y, *info["photo_wh"], base))
        elif kind == "svg":
            parts.append(f'<g transform="translate({x:.1f},{y:.1f}) scale({s:.3f})">{el["markup"]}</g>')
    return "".join(parts)


def _concept_text(pen, spec):
    bg, _, _ = BACKGROUNDS["neutral_default"](pen, 0, 0, W, H)
    main, (_, mh) = text_block(pen, spec["text"], W / 2, 0, W * 0.84, 250, T["title"])  # đo chiều cao
    sub_h = 110 if spec.get("sub") else 0
    top = (H - mh - sub_h) / 2
    main, _ = text_block(pen, spec["text"], W / 2, top + mh / 2, W * 0.84, 250, T["title"])
    out = bg + main
    if sub_h:
        out += text_block(pen, spec["sub"], W / 2, top + mh + sub_h / 2 + 10, W * 0.7, 70, INK)[0]
    return out


def _split(pen, spec, warnings):
    half = W / 2
    out = ""
    for i, side in enumerate(("left", "right")):
        panel = spec.get(side, {})
        inner = render_panel(pen.child(side), panel, i * half, 0, half, H, warnings)
        if panel.get("title"):
            inner += text_block(pen, panel["title"], i * half + half / 2, H * 0.12, half * 0.8, 120, T["title"],
                                INK if panel.get("bg") in DARK else None)[0]
        out += (f'<clipPath id="c{i}"><rect x="{i*half}" y="0" width="{half}" height="{H}"/></clipPath>'
                f'<g clip-path="url(#c{i})">{inner}</g>')
    return out + pen.line([(half, -10), (half, H + 10)], width=12, amp=3)


def _timeline(pen, spec, warnings):
    bg_name = spec.get("bg", "neutral_default")
    _check(bg_name, BACKGROUNDS, "bg")
    out = BACKGROUNDS[bg_name](pen, 0, 0, W, H)[0]
    dark = bg_name in DARK
    ink = C["white"] if dark else INK
    if spec.get("title"):
        out += text_block(pen, spec["title"], W / 2, H * 0.11, W * 0.8, 100, T["title"], INK if dark else None)[0]
    events = spec.get("events", [])
    if not events:
        raise SceneError("timeline cần ít nhất 1 event")
    if len(events) > 6:
        warnings.append("timeline có hơn 6 event — chữ sẽ rất nhỏ")
    ly = H * 0.6
    out += _arrow(pen, (W * 0.05, ly), (W * 0.96, ly), 12)
    n = len(events)
    slot = W * 0.86 / n
    for i, ev in enumerate(events):
        cx = W * 0.07 + slot * (i + 0.5)
        hl = spec.get("highlight") == i
        out += pen.circle(cx, ly, 24 if hl else 16, T["highlight"] if hl else C["white"], width=6)
        if ev.get("icon"):
            _check(ev["icon"], PROPS, "timeline icon")
            meta = PROPS[ev["icon"]]
            # cỡ hiển thị đồng đều: vật nhỏ (xương, rìu) được phóng to, vật lớn thu nhỏ vào ô ~200px
            ps = min(slot * 0.62 / (2 * meta["w"]), 200 / meta["h"], 3.0)
            iy = ly - 50 - (0 if meta["anchor"] == "bottom" else meta["h"] * ps / 2)
            out += draw_prop(pen, ev["icon"], cx, iy, ps, {"bg_color": T["paper"]})
        # nhãn (năm) một dòng, tự thu nhỏ; mô tả đặt ngay dưới theo chiều cao thật của nhãn
        label_svg, (_, lh) = text_block(pen, ev.get("label", ""), cx, ly + 70, slot * 0.92, 64, T["title"],
                                        INK if dark else None, 1)
        out += label_svg
        if ev.get("text"):
            _, (_, th) = text_block(pen, ev["text"], cx, 0, slot * 0.92, 44, ink, None, 3, tilt=0)
            out += text_block(pen, ev["text"], cx, ly + 70 + lh / 2 + 20 + th / 2, slot * 0.92, 44, ink, None, 3,
                              tilt=0.8)[0]
    return out


def _stats(pen, spec, warnings):
    out = BACKGROUNDS["neutral_default"](pen, 0, 0, W, H)[0]
    if spec.get("title"):
        out += text_block(pen, spec["title"], W / 2, H * 0.13, W * 0.84, 100, T["title"])[0]
    bars = spec.get("bars", [])
    if not bars:
        raise SceneError("stats cần ít nhất 1 bar")
    vmax = max(b["value"] for b in bars) or 1
    top, bottom = H * 0.28, H * 0.9
    step = (bottom - top) / len(bars)
    bh = min(120, step * 0.62)
    colors = [C["orange"], C["grass_green"], C["blue"], C["purple_mauve"], C["yellow"]]
    lx, bx0, bmax = W * 0.12, W * 0.24, W * 0.56
    for i, b in enumerate(bars):
        cy = top + step * (i + 0.5)
        out += text_block(pen, b["label"], lx, cy, W * 0.2, 60, INK, None, 2, tilt=0.8)[0]
        bw = max(20, bmax * b["value"] / vmax)
        out += pen.rect(bx0, cy - bh / 2, bw, bh, NAMED.get(b.get("color"), colors[i % len(colors)]), amp=2)
        out += text_block(pen, b.get("display", str(b["value"])), bx0 + bw + 30 + W * 0.07, cy, W * 0.15, 70, T["title"],
                          None, 1)[0]
    return out


def scene_svg(spec, warnings=None, visible=None, seed=None, boxes_out=None, size=None):
    """spec → chuỗi SVG. warnings: list nhận cảnh báo bố cục. visible: tập chỉ số element cần hiện
    (dùng cho hiệu ứng hiện dần; chỉ áp dụng frame=scene). seed: giữ nét rung cố định giữa các trạng thái
    của cùng một cảnh (mặc định tính từ nội dung spec). size=(w, h): chỉ các khung trong RESPONSIVE vẽ theo kích
    thước khác 1920x1080 (ô nội dung bản dọc); khung khác luôn vẽ 16:9."""
    warnings = [] if warnings is None else warnings
    pen = Pen(seed if seed is not None else zlib.crc32(json.dumps(spec, sort_keys=True).encode()))
    frame = spec.get("frame", "scene")
    _check(frame, FRAMES, "frame")
    w, h = size if (size and frame in RESPONSIVE) else (W, H)
    if frame in CARD_FRAMES:
        body = CARD_FRAMES[frame][0](spec, w, h)
    elif (w, h) != (W, H) and frame in ("concept_text", "photo"):
        from .cards import concept, photo_full
        if frame == "concept_text" and not spec.get("text"):
            raise SceneError("concept_text cần trường 'text'")
        body = concept(spec, w, h) if frame == "concept_text" else photo_full(spec, w, h)
    elif frame == "concept_text":
        if not spec.get("text"):
            raise SceneError("concept_text cần trường 'text'")
        body = _concept_text(pen, spec)
    elif frame == "split":
        body = _split(pen, spec, warnings)
    elif frame == "timeline":
        body = _timeline(pen, spec, warnings)
    elif frame == "photo":
        body = _photo_frame(pen, spec)
    elif frame == "brand_card":
        body = _brand_card(pen, spec)
    elif frame == "stats":
        body = _stats(pen, spec, warnings)
    else:
        body = render_panel(pen, spec, 0, 0, W, H, warnings, visible, boxes_out)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">'
            + body + "</svg>")


# ---------------- ảnh thực tế ----------------
_PHOTO_CACHE = {}


def photo_path(src):
    if not src:
        raise SceneError("photo cần 'src' (tên file trong projects/<slug>/photos/)")
    if os.path.isabs(src) and os.path.exists(src):
        return src
    for d in PHOTO_DIRS:
        for cand in (os.path.join(d, src), os.path.join(d, src + ".jpg"), os.path.join(d, src + ".png")):
            if os.path.exists(cand):
                return cand
    raise SceneError(f"không tìm thấy ảnh '{src}' — tải bằng `make_video.py photo get` vào projects/<slug>/photos/")


def _photo(src):
    path = photo_path(src)
    if path not in _PHOTO_CACHE:
        from PIL import Image
        with Image.open(path) as im:
            wh = im.size
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        _PHOTO_CACHE[path] = (f"data:{mime};base64,{data}", wh)
    return _PHOTO_CACHE[path]


def photo_size(src):
    return _photo(src)[1]


def photo_credit(src):
    """'Ảnh: tác giả (giấy phép)' từ file .json cạnh ảnh (nếu có)."""
    base = os.path.splitext(photo_path(src))[0] + ".json"
    if not os.path.exists(base):
        return ""
    with open(base, "r", encoding="utf-8") as f:
        m = json.load(f)
    lic = {"cc0": "CC0", "pdm": "Public Domain", "by": "CC BY", "by-sa": "CC BY-SA"}.get(m.get("license"), m.get("license", ""))
    if m.get("license") in ("by", "by-sa") and m.get("license_version"):
        lic += " " + m["license_version"]
    return f"Ảnh: {m.get('creator') or 'không rõ'} ({lic})"


def _photo_card(pen, el, cx, cy, pw, ph, base):
    uri, _ = _photo(el["src"])
    tilt = el.get("tilt", pen.jitter(0, 2.5))
    polaroid = el.get("frame", "polaroid") == "polaroid"
    pad = 16 * base if polaroid else 0
    bottom = (66 if el.get("caption") else 22) * base if polaroid else 0
    fw, fh = pw + 2 * pad, ph + pad + bottom
    fx, fy = cx - fw / 2, cy - ph / 2 - pad
    key = "%s|%.0f|%.0f" % (el["src"], cx, cy)
    clip = "ph%d" % zlib.crc32(key.encode())
    out = []
    if polaroid:
        out.append(pen.rect(fx, fy, fw, fh, "#FFFFFF", width=5, amp=1.2))
    out.append(f'<clipPath id="{clip}"><rect x="{cx - pw / 2:.1f}" y="{cy - ph / 2:.1f}" width="{pw:.1f}" height="{ph:.1f}"/></clipPath>'
               f'<image href="{uri}" x="{cx - pw / 2:.1f}" y="{cy - ph / 2:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
               f'preserveAspectRatio="xMidYMid slice" clip-path="url(#{clip})"/>')
    if not polaroid:
        out.append(pen.rect(cx - pw / 2, cy - ph / 2, pw, ph, "none", width=5, amp=1.0))
    if polaroid and el.get("caption"):
        out.append(text_block(pen, el["caption"], cx, cy + ph / 2 + bottom / 2 + 4 * base, pw * 0.95, int(40 * base),
                              C["ink"], None, 1)[0])
    credit = el.get("credit", photo_credit(el["src"]))
    if credit:
        out.append(f'<text x="{fx + fw:.0f}" y="{fy + fh + 26 * base:.0f}" text-anchor="end" font-family="{FONT_FAMILY}" '
                   f'font-size="{20 * base:.0f}" fill="#7A85A6">{escape_xml(credit)}</text>')
    return f'<g transform="rotate({tilt:.2f} {cx:.1f} {cy:.1f})">{"".join(out)}</g>'


def _photo_frame(pen, spec):
    """Ảnh toàn màn hình (B-roll thực tế) + chú thích góc trên + ghi nguồn góc dưới-phải."""
    uri, _ = _photo(spec.get("src"))
    out = [f'<rect width="{W}" height="{H}" fill="#101A3D"/>',
           f'<image href="{uri}" x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="xMidYMid slice"/>']
    if spec.get("caption"):
        svg, (tw, th) = text_block(pen, spec["caption"], 0, 0, W * 0.6, 60, "#FFFFFF", None, 2, tilt=0)
        bw, bh = tw + 60, th + 30
        mx, my = 120, 90  # lề đủ rộng để camera zoom (tối đa ~7%) không cắt mất chú thích
        out.append(f'<rect x="{mx}" y="{my}" width="{bw:.0f}" height="{bh:.0f}" rx="16" fill="#101A3D" fill-opacity="0.82"/>')
        out.append(text_block(pen, spec["caption"], mx + bw / 2, my + bh / 2, W * 0.6, 60, "#FFFFFF", None, 2, tilt=0)[0])
    credit = spec.get("credit", photo_credit(spec["src"]))
    if credit:
        out.append(f'<rect x="{W - 110 - 14 * len(credit):.0f}" y="{H - 250}" width="{14 * len(credit):.0f}" height="34" rx="8" '
                   f'fill="#000000" fill-opacity="0.45"/>')
        out.append(f'<text x="{W - 120}" y="{H - 226}" text-anchor="end" font-family="{FONT_FAMILY}" font-size="22" '
                   f'fill="#FFFFFF">{escape_xml(credit)}</text>')
    return "".join(out)


def _brand_card(pen, spec):
    """Màn kết: nền mực đêm, logo thương hiệu (SVG gốc, font thương hiệu), lời mời + liên hệ + miễn trừ."""
    import re
    from xml.sax.saxutils import escape as esc
    navy, teal, yellow = "#101A3D", "#00C2A8", "#FFC93C"
    out = [f'<rect width="{W}" height="{H}" fill="{navy}"/>',
           f'<circle cx="{W - 170}" cy="190" r="430" fill="none" stroke="{teal}" stroke-opacity="0.35" stroke-width="4"/>',
           f'<circle cx="160" cy="{H - 80}" r="260" fill="none" stroke="{teal}" stroke-opacity="0.2" stroke-width="3"/>']
    lp = spec.get("logo_path")
    if lp:
        with open(lp, "r", encoding="utf-8") as f:
            raw = f.read()
        vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', raw).group(1).split()]
        inner = re.search(r"<svg\b[^>]*>(.*)</svg>", raw, re.S).group(1)
        lw = 1240
        k = lw / vb[2]
        out.append(f'<g transform="translate({(W - lw) / 2:.0f},150) scale({k:.3f}) translate({-vb[0]},{-vb[1]})">{inner}</g>')
    font = 'font-family="Be Vietnam Pro, Segoe UI, Arial, sans-serif" text-anchor="middle"'
    if spec.get("headline"):
        out.append(f'<text x="{W / 2}" y="560" {font} font-weight="800" font-size="96" fill="#FFFFFF">'
                   f'{esc(spec["headline"])}</text>')
    for i, line in enumerate(spec.get("card_lines", [])):
        out.append(f'<text x="{W / 2}" y="{690 + i * 100}" {font} font-weight="700" font-size="{66 if i == 0 else 54}" '
                   f'fill="{yellow if i == 0 else teal}">{esc(line)}</text>')
    if spec.get("disclaimer"):
        out.append(f'<text x="{W / 2}" y="900" {font} font-weight="400" font-size="30" fill="#9AA6C8">'
                   f'{esc(spec["disclaimer"])}</text>')
    return "".join(out)


def render_png(svg, zoom=1.0):
    """zoom > 1 vẽ ở độ phân giải cao hơn (dùng khi dựng video có hiệu ứng zoom để hình không bị mờ)."""
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, font_files=[FONT_PATH] + EXTRA_FONTS, skip_system_fonts=True,
                                       font_family=FONT_FAMILY, sans_serif_family=FONT_FAMILY,
                                       zoom=zoom if zoom != 1.0 else None))


def render_scene(spec, out_path, warnings=None, visible=None, seed=None):
    with open(out_path, "wb") as f:
        f.write(render_png(scene_svg(spec, warnings, visible, seed)))
    return out_path
