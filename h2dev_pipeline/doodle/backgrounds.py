"""Nền màu phẳng theo cảm xúc (visual_style_dna.backgrounds). Mỗi hàm vẽ trong khung (x, y, w, h)
và trả về (svg, ground_y, sky_color)."""
from . import assets
from .palette import C

BACKGROUNDS_DESC = {
    "neutral_default": "Nền kem trơn — mặc định, khung chữ, trung tính",
    "neutral_modern": "Nền kem + dải sàn xám — cảnh hiện đại / 'limbo'",
    "outdoor_daytime": "Trời xanh + đất nâu nhạt — ngoài trời ban ngày, thiên nhiên",
    "ancient_savanna": "Trời cam + đất vàng + cỏ — thời tiền sử, bình minh/hoàng hôn",
    "calm_night": "Xanh navy + đất xám — đêm yên tĩnh",
    "deep_night": "Tím chàm + sao + đất nâu — đêm sâu / giấc ngủ",
    "cave_interior": "Trong hang đá tối, sàn đất — sinh hoạt trong hang, tranh hang động",
    "ice_age_winter": "Trời xám xanh + tuyết rơi + đất phủ tuyết — mùa đông, kỷ băng hà, giá lạnh",
}
DARK = {"calm_night", "deep_night", "cave_interior"}


def _sky(x, y, w, h, color):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{color}"/>'


def _ground(pen, x, w, top, bottom, color):
    pts = [(x - 20, top)] + [(x + w * i / 8, top + pen.jitter(0, 6)) for i in range(1, 8)] + \
          [(x + w + 20, top), (x + w + 20, bottom + 20), (x - 20, bottom + 20)]
    return pen.poly(pts, color, width=6, amp=3)


def neutral_default(pen, x, y, w, h):
    return _sky(x, y, w, h, C["cream"]), y + h * 0.88, C["cream"]


def neutral_modern(pen, x, y, w, h):
    g = y + h * 0.8
    return _sky(x, y, w, h, C["cream"]) + _ground(pen, x, w, g, y + h, C["light_gray"]), g + 30, C["cream"]


def outdoor_daytime(pen, x, y, w, h):
    g = y + h * 0.74
    return (_sky(x, y, w, h, C["cave_light_blue"]) + _ground(pen, x, w, g, y + h, C["sand_tan"]),
            g + 40, C["cave_light_blue"])


def ancient_savanna(pen, x, y, w, h):
    g = y + h * 0.72
    svg = _sky(x, y, w, h, C["savanna_orange"]) + _ground(pen, x, w, g, y + h, C["sand_tan"])
    for i in range(7):
        gx = x + w * (0.06 + 0.14 * i) + pen.jitter(0, 30)
        gy = g + 60 + pen.jitter(0, 70)
        for dx, lean in ((-12, -10), (0, 2), (12, 12)):
            svg += pen.shape(f"M{gx+dx*0.4:.0f},{gy:.0f} Q{gx+dx:.0f},{gy-16:.0f} {gx+dx+lean:.0f},{gy-30:.0f}",
                             stroke=C["leaf_dark"], width=4)
    return svg, g + 40, C["savanna_orange"]


def calm_night(pen, x, y, w, h):
    g = y + h * 0.76
    return (_sky(x, y, w, h, C["night_navy"]) + _ground(pen, x, w, g, y + h, "#6E6E78"),
            g + 40, C["night_navy"])


def deep_night(pen, x, y, w, h):
    g = y + h * 0.74
    svg = _sky(x, y, w, h, C["deep_indigo"])
    for _ in range(int(w / 45)):
        sx, sy = x + pen.rng.uniform(20, w - 20), y + pen.rng.uniform(20, h * 0.6)
        svg += f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{pen.rng.uniform(2.5, 5.5):.1f}" fill="#FFF3B0"/>'
    svg += _ground(pen, x, w, g, y + h, C["dirt_brown"])
    return svg, g + 40, C["deep_indigo"]


def cave_interior(pen, x, y, w, h):
    g = y + h * 0.78
    wall = "#4A4346"
    svg = _sky(x, y, w, h, wall)
    # vòm hang sáng hơn ở giữa
    arch = [(x + w * 0.08, g + 10), (x + w * 0.1, y + h * 0.35), (x + w * 0.3, y + h * 0.1), (x + w * 0.7, y + h * 0.08),
            (x + w * 0.9, y + h * 0.3), (x + w * 0.93, g + 10)]
    svg += pen.poly(arch, "#6A6064", width=6, amp=5)
    for _ in range(int(w / 240)):
        cx, cy = x + pen.rng.uniform(w * 0.15, w * 0.85), y + pen.rng.uniform(h * 0.2, h * 0.6)
        svg += pen.line([(cx, cy), (cx + pen.jitter(0, 30), cy + 40), (cx + pen.jitter(0, 30), cy + 80)], width=4)
    svg += _ground(pen, x, w, g, y + h, C["wood_brown"])
    return svg, g + 35, wall


def ice_age_winter(pen, x, y, w, h):
    g = y + h * 0.74
    svg = _sky(x, y, w, h, "#9DB4C8")
    for _ in range(int(w / 22)):
        sx, sy = x + pen.rng.uniform(10, w - 10), y + pen.rng.uniform(10, h * 0.72)
        svg += f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{pen.rng.uniform(3, 7):.1f}" fill="#FFFFFF"/>'
    svg += _ground(pen, x, w, g, y + h, "#F4F7FA")
    for i in range(5):  # vệt tuyết đọng
        gx, gy = x + w * (0.1 + 0.2 * i) + pen.jitter(0, 40), g + 70 + pen.jitter(0, 60)
        svg += pen.shape(f"M{gx-40:.0f},{gy:.0f} Q{gx:.0f},{gy-14:.0f} {gx+40:.0f},{gy:.0f}", stroke="#B9C9D6",
                         width=4)
    return svg, g + 40, "#9DB4C8"


def _with_plate(name, fn):
    """Có tấm nền vẽ sẵn (assets/backgrounds/<name>.svg) thì dùng nó; hàm code vẫn chạy để lấy
    ground_y/màu trời (tấm nền được vẽ theo đúng các mốc đó). Khung hẹp hơn 16:9 (split) thì
    phóng theo chiều cao và cắt giữa."""
    def draw(pen, x, y, w, h):
        svg, ground_y, sky = fn(pen, x, y, w, h)
        plate = assets.get("backgrounds", name)
        if plate is not None:
            s = h / 1080
            ox = x + (w - 1920 * s) / 2
            svg = f'<g transform="translate({ox:.1f},{y:.1f}) scale({s:.4f})">{plate}</g>'
        return svg, ground_y, sky
    return draw


BACKGROUNDS = {name: _with_plate(name, globals()[name]) for name in BACKGROUNDS_DESC}


# ---------------- nền thêm sau (không cần code) ----------------
def _custom(meta):
    """Nền chỉ có tấm vẽ sẵn + json: ground_top/feet_y theo khung 1080, màu trời để khoét trăng."""
    def fn(pen, x, y, w, h):
        s = h / 1080
        return _sky(x, y, w, h, meta.get("sky", C["cream"])), y + meta["feet_y"] * s, meta.get("sky", C["cream"])
    return fn


for _name, _m in assets.sidecars("backgrounds").items():
    if _name in BACKGROUNDS:
        continue
    BACKGROUNDS_DESC[_name] = _m.get("desc", _name)
    BACKGROUNDS[_name] = _with_plate(_name, _custom(_m))
    if _m.get("dark"):
        DARK.add(_name)
