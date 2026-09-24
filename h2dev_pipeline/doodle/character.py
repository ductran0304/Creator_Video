"""Nhân vật người que theo visual DNA của kênh (h2dev_knowledge_base.json → visual_style_dna)."""
import math
from .pen import INK

HEAD_R = 62
LIMB = 7

HAIR = {
    "you_main": "#FF8A1F",        # tóc cam dựng — nhân vật "you"
    "ancient_human": "#7A4A21",   # tóc nâu rối — người tiền sử
    "modern_neutral": None,       # đầu trọc
    "elder_grandmother": "#BDBDBD",
}
DRESS = "#8E5BB5"

# Khung xương theo từng tư thế. Gốc toạ độ = chân chạm đất, trục y hướng xuống.
# neck/hip: điểm thân; arms/legs: danh sách polyline (vai→khuỷu→tay, hông→gối→chân);
# head: tâm đầu; tilt: góc xoay đầu (độ).
POSES = {
    "standing": {
        "head": (0, -362), "neck": (0, -300), "hip": (0, -170), "tilt": 0,
        "arms": [[(0, -285), (-50, -232), (-80, -178)], [(0, -285), (50, -232), (80, -178)]],
        "legs": [[(0, -170), (-22, -85), (-42, 0)], [(0, -170), (22, -85), (42, 0)]],
    },
    "arms_up": {
        "head": (0, -362), "neck": (0, -300), "hip": (0, -170), "tilt": 0,
        "arms": [[(0, -285), (-78, -372), (-112, -468)], [(0, -285), (78, -372), (112, -468)]],
        "legs": [[(0, -170), (-24, -85), (-48, 0)], [(0, -170), (24, -85), (48, 0)]],
    },
    "pointing": {
        "head": (0, -362), "neck": (0, -300), "hip": (0, -170), "tilt": 0,
        "arms": [[(0, -285), (-45, -230), (-70, -178)], [(0, -285), (75, -290), (150, -300)]],
        "legs": [[(0, -170), (-22, -85), (-42, 0)], [(0, -170), (22, -85), (42, 0)]],
    },
    "holding": {  # một tay đưa lên ngang mặt (cầm điện thoại, đuốc...)
        "head": (0, -362), "neck": (0, -300), "hip": (0, -170), "tilt": 8,
        "arms": [[(0, -285), (-50, -232), (-80, -178)], [(0, -285), (62, -212), (118, -250)]],
        "legs": [[(0, -170), (-22, -85), (-42, 0)], [(0, -170), (22, -85), (42, 0)]],
        "hand": (118, -250),
    },
    "sitting": {
        "head": (0, -250), "neck": (0, -188), "hip": (0, -58), "tilt": 0,
        "arms": [[(0, -172), (-48, -118), (-78, -70)], [(0, -172), (48, -118), (78, -70)]],
        "legs": [[(0, -58), (-100, -34), (25, -8)], [(0, -58), (100, -34), (-25, -8)]],
    },
    "pushing": {
        "head": (108, -318), "neck": (62, -268), "hip": (-18, -150), "tilt": 28,
        "arms": [[(55, -255), (120, -240), (175, -250)], [(55, -255), (115, -212), (170, -212)]],
        "legs": [[(-18, -150), (-60, -80), (-110, 0)], [(-18, -150), (20, -80), (10, 0)]],
    },
    "sleeping": {  # nằm ngang, đầu bên trái
        "head": (-215, -64), "neck": (-150, -42), "hip": (15, -40), "tilt": -90,
        "arms": [[(-120, -42), (-60, -30), (0, -24)], [(-120, -44), (-70, -58), (-10, -50)]],
        "legs": [[(15, -40), (100, -38), (185, -30)], [(15, -40), (100, -52), (180, -50)]],
    },
}


def _hair(pen, variant):
    color = HAIR.get(variant)
    if not color:
        return ""
    r = HEAD_R
    pt = lambda rad, deg: (rad * math.cos(math.radians(deg)), rad * math.sin(math.radians(deg)))
    parts = []
    if variant == "you_main":
        # tóc dựng: răng cưa nhọn phía trên, mép trong ôm theo đỉnh đầu
        outer = []
        n = 9
        for i in range(n + 1):
            a = -162 + 144 * i / n
            outer.append(pt(r + (34 if i % 2 else 6), a))
        inner = [pt(r - 18, a) for a in range(-18, -163, -12)]
        parts.append(pen.poly(outer + inner, color, amp=1.2))
    elif variant == "ancient_human":
        # tóc bù xù: nhiều búi tròn, phủ xuống hai bên đầu
        outer = []
        n = 14
        for i in range(n + 1):
            a = -205 + 230 * i / n
            outer.append(pt(r + pen.jitter(20 if i % 2 else 8, 5), a))
        inner = [pt(r - 12, a) for a in range(25, -206, -14)]
        inner = [(x, y) if y < -10 else (x * 1.02, y) for x, y in inner]
        parts.append(pen.poly(outer + inner, color, amp=2.2))
    elif variant == "elder_grandmother":
        parts.append(pen.circle(0, -r - 18, 26, color))
        outer = [pt(r + 6, a) for a in range(-172, -7, 12)]
        inner = [pt(r - 16, a) for a in range(-10, -173, -12)]
        parts.append(pen.poly(outer + inner, color, amp=1.4))
    return "".join(parts)


def _face(pen, expression):
    e = []
    brow_w = 4.5
    if expression == "sleeping":
        for sx in (-1, 1):
            e.append(pen.shape(f"M{sx*34},-4 Q{sx*22},6 {sx*10},-4", width=4.5))
        e.append(pen.line([(-10, 28), (10, 28)], width=4.5))
        return "".join(e)

    if expression == "surprise":
        for sx in (-1, 1):
            e.append(pen.circle(sx * 22, -6, 13, "#FFFFFF", width=4))
            e.append(f'<circle cx="{sx*22}" cy="-5" r="6" fill="{INK}"/>')
            e.append(pen.shape(f"M{sx*36},-34 Q{sx*22},-46 {sx*8},-36", width=brow_w))
        e.append(pen.ellipse(0, 30, 9, 13, INK, width=3))
        return "".join(e)

    for sx in (-1, 1):
        e.append(f'<circle cx="{sx*22}" cy="-4" r="7" fill="{INK}"/>')
    if expression == "strain_anger":
        for sx in (-1, 1):
            e.append(pen.line([(sx * 38, -34), (sx * 9, -20)], width=brow_w))
        e.append(pen.rect(-24, 18, 48, 17, "#FFFFFF", width=3.5))
        for x in (-12, 0, 12):
            e.append(f'<line x1="{x}" y1="19" x2="{x}" y2="34" stroke="{INK}" stroke-width="2.5"/>')
    elif expression == "worry_sadness":
        for sx in (-1, 1):
            e.append(pen.line([(sx * 38, -20), (sx * 10, -33)], width=brow_w))
        e.append(pen.shape("M-18,34 Q0,20 18,34", width=4.5))
    else:  # calm_content (mặc định)
        for sx in (-1, 1):
            e.append(pen.line([(sx * 36, -27), (sx * 12, -30)], width=brow_w))
        e.append(pen.shape("M-18,20 Q0,34 18,20", width=4.5))
    return "".join(e)


def _head(pen, cx, cy, tilt, variant, expression):
    face = _face(pen, expression)
    if tilt <= -60:  # nằm: tóc xoay theo đầu, mặt giữ thẳng để vẫn đọc được biểu cảm
        face = f'<g transform="rotate({-tilt})">{face}</g>'
    body = pen.circle(0, 0, HEAD_R, "#FFFFFF") + face + _hair(pen, variant)
    return f'<g transform="translate({cx:.1f},{cy:.1f}) rotate({tilt})">{body}</g>'


def character(pen, x, ground_y, variant="you_main", pose="standing", expression="calm_content",
              scale=1.0, flip=False, extras=()):
    """Trả về (svg, anchors). anchors chứa toạ độ tuyệt đối của đầu/tay để gắn đạo cụ, hiệu ứng."""
    p = POSES.get(pose, POSES["standing"])
    if pose == "sleeping" and expression == "calm_content":
        expression = "sleeping"
    parts = []
    if variant == "elder_grandmother" and pose in ("standing", "pointing", "holding", "arms_up"):
        nx, ny = p["neck"]
        parts.append(pen.poly([(nx - 14, ny + 6), (nx + 14, ny + 6), (nx + 62, p["hip"][1] + 40),
                               (nx - 62, p["hip"][1] + 40)], DRESS))
    parts.append(pen.line([p["neck"], p["hip"]], width=LIMB))
    for limb in p["legs"] + p["arms"]:
        parts.append(pen.line(limb, width=LIMB))
        ex, ey = limb[-1]
        is_foot = limb in p["legs"]
        rx, ry = (15, 8) if is_foot else (11, 11)
        if is_foot and pose == "sleeping":
            rx, ry = 8, 14
        parts.append(pen.ellipse(ex + (5 if is_foot and pose != "sleeping" else 0), ey - (4 if is_foot else 0),
                                 rx, ry, INK, width=2))
    hx, hy = p["head"]
    parts.append(_head(pen, hx, hy, p["tilt"], variant, expression))

    for fx in extras:
        if fx == "zzz":
            for i, (dx, dy, fs) in enumerate(((40, -110, 46), (85, -160, 60), (140, -220, 76))):
                parts.append(f'<text x="{hx+dx}" y="{hy+dy}" font-family="Comic Sans MS" font-weight="bold" '
                             f'font-size="{fs}" fill="#FFFFFF" stroke="{INK}" stroke-width="3" '
                             f'paint-order="stroke">Z</text>')
        elif fx == "sweat":
            for dx, dy in ((-80, -38), (-94, 12)):
                sx, sy = hx + dx, hy + dy
                parts.append(pen.poly([(sx, sy - 22), (sx + 11, sy), (sx, sy + 10), (sx - 11, sy)],
                                      "#5BC0F0", width=3.5, amp=0.8))
        elif fx == "shock_lines":
            for a in (-150, -120, -60, -30):
                c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
                parts.append(pen.line([(hx + c * 85, hy + s * 85), (hx + c * 120, hy + s * 120)], width=5))

    sx = -scale if flip else scale
    svg = f'<g transform="translate({x:.1f},{ground_y:.1f}) scale({sx},{scale})">{"".join(parts)}</g>'

    def to_abs(pt):
        return (x + pt[0] * sx, ground_y + pt[1] * scale)
    anchors = {"head": to_abs(p["head"]), "hand": to_abs(p.get("hand", p["arms"][1][-1])), "scale": scale}
    return svg, anchors
