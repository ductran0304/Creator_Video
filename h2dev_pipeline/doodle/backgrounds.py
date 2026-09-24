"""Nền màu phẳng theo cảm xúc (visual_style_dna.backgrounds). Mỗi hàm vẽ trong khung (x, y, w, h)
và trả về (svg, ground_y, sky_color)."""

CREAM = "#FBF5E8"


def _sky(x, y, w, h, color):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}"/>'


def _ground(pen, x, w, top, bottom, color):
    pts = [(x - 20, top)] + [(x + w * i / 8, top + pen.jitter(0, 6)) for i in range(1, 8)] + \
          [(x + w + 20, top), (x + w + 20, bottom + 20), (x - 20, bottom + 20)]
    return pen.poly(pts, color, width=6, amp=3)


def neutral_default(pen, x, y, w, h):
    return _sky(x, y, w, h, CREAM), y + h * 0.88, CREAM


def neutral_modern(pen, x, y, w, h):
    g = y + h * 0.8
    return _sky(x, y, w, h, CREAM) + _ground(pen, x, w, g, y + h, "#BDBDBD"), g + 30, CREAM


def outdoor_daytime(pen, x, y, w, h):
    g = y + h * 0.74
    return _sky(x, y, w, h, "#A8DDF5") + _ground(pen, x, w, g, y + h, "#D8B57C"), g + 40, "#A8DDF5"


def ancient_savanna(pen, x, y, w, h):
    g = y + h * 0.72
    svg = _sky(x, y, w, h, "#F7A440") + _ground(pen, x, w, g, y + h, "#D6AE74")
    for i in range(7):
        gx = x + w * (0.06 + 0.14 * i) + pen.jitter(0, 30)
        gy = g + 60 + pen.jitter(0, 70)
        svg += pen.line([(gx - 16, gy), (gx - 8, gy - 26), (gx, gy), (gx + 8, gy - 30), (gx + 16, gy)],
                        width=4, stroke="#6B8E23", amp=0.6)
    return svg, g + 40, "#F7A440"


def calm_night(pen, x, y, w, h):
    g = y + h * 0.76
    return _sky(x, y, w, h, "#1E2A5A") + _ground(pen, x, w, g, y + h, "#6E6E78"), g + 40, "#1E2A5A"


def deep_night(pen, x, y, w, h):
    g = y + h * 0.74
    svg = _sky(x, y, w, h, "#2B1E5C")
    for _ in range(int(w / 45)):
        sx, sy = x + pen.rng.uniform(20, w - 20), y + pen.rng.uniform(20, h * 0.6)
        r = pen.rng.uniform(2.5, 5.5)
        svg += f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{r:.1f}" fill="#FFF3B0"/>'
    svg += _ground(pen, x, w, g, y + h, "#6B4A2B")
    return svg, g + 40, "#2B1E5C"


BACKGROUNDS = {
    "neutral_default": neutral_default, "neutral_modern": neutral_modern, "outdoor_daytime": outdoor_daytime,
    "ancient_savanna": ancient_savanna, "calm_night": calm_night, "deep_night": deep_night,
}
DARK = {"calm_night", "deep_night"}
