"""Nhân vật người que theo visual DNA của kênh (h2dev_knowledge_base.json → visual_style_dna).

Toạ độ cục bộ: gốc = điểm chân chạm đất, y hướng xuống, nhân vật mặc định nhìn sang PHẢI
(flip=True để nhìn sang trái). Kích thước ở scale 1 cao ~450px trên khung 1080px.
"""
import math

from .palette import C
from .text import FONT_FAMILY

INK = C["ink"]
HEAD_R = 62
LIMB = 7

VARIANTS = {
    "you_main": "Nhân vật chính 'you' — tóc cam dựng",
    "ancient_human": "Người tiền sử — tóc nâu bù xù",
    "modern_neutral": "Người hiện đại trung tính — đầu trọc",
    "elder_grandmother": "Bà cụ — tóc bạc búi + váy tím",
    "archaeologist": "Nhà khảo cổ — mũ thám hiểm nâu + ba lô",
}

EXPRESSIONS = {
    "calm_content": "cười mỉm (mặc định)",
    "happy": "cười tươi há miệng",
    "surprise": "mắt tròn, miệng chữ O",
    "worry_sadness": "lông mày cong, miệng méo",
    "strain_anger": "nghiến răng, lông mày chụm",
    "thinking": "một bên lông mày nhướn, miệng lệch",
    "sleeping": "nhắm mắt (tự dùng khi pose=sleeping)",
}

# neck/hip: thân; arms/legs: polyline vai→khuỷu→tay, hông→gối→chân; head: tâm đầu; tilt: góc đầu.
# hand: tay dùng để cầm đồ (mặc định tay thứ 2).
POSES = {
    "standing": {
        "head": (0, -362), "neck": (0, -300), "hip": (0, -170), "tilt": 0,
        "arms": [[(0, -285), (-50, -232), (-80, -178)], [(0, -285), (50, -232), (80, -178)]],
        "legs": [[(0, -170), (-22, -85), (-42, 0)], [(0, -170), (22, -85), (42, 0)]],
    },
    "walking": {
        "head": (8, -360), "neck": (4, -298), "hip": (0, -170), "tilt": 4,
        "arms": [[(2, -283), (-35, -230), (-72, -190)], [(2, -283), (40, -228), (62, -175)]],
        "legs": [[(0, -170), (-35, -90), (-78, -6)], [(0, -170), (38, -92), (58, 0)]],
    },
    "running": {
        "head": (40, -345), "neck": (26, -286), "hip": (0, -165), "tilt": 14,
        "arms": [[(22, -272), (-30, -250), (-70, -285)], [(22, -272), (70, -235), (110, -262)]],
        "legs": [[(0, -165), (-60, -110), (-120, -80)], [(0, -165), (60, -90), (40, 0)]],
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
    "holding": {
        "head": (0, -362), "neck": (0, -300), "hip": (0, -170), "tilt": 8,
        "arms": [[(0, -285), (-50, -232), (-80, -178)], [(0, -285), (62, -212), (118, -250)]],
        "legs": [[(0, -170), (-22, -85), (-42, 0)], [(0, -170), (22, -85), (42, 0)]],
    },
    "thinking": {
        "head": (0, -362), "neck": (0, -300), "hip": (0, -170), "tilt": -6,
        "arms": [[(0, -285), (-50, -232), (-80, -178)], [(0, -285), (58, -240), (28, -318)]],
        "legs": [[(0, -170), (-22, -85), (-42, 0)], [(0, -170), (22, -85), (42, 0)]],
    },
    "sitting": {
        "head": (0, -250), "neck": (0, -188), "hip": (0, -58), "tilt": 0,
        "arms": [[(0, -172), (-48, -118), (-78, -70)], [(0, -172), (48, -118), (78, -70)]],
        "legs": [[(0, -58), (-100, -34), (25, -8)], [(0, -58), (100, -34), (-25, -8)]],
    },
    "hugging_knees": {
        # nhìn thẳng: ngồi bệt, hai gối co lên, tay ôm gối, cằm tựa trên gối
        "head": (0, -238), "neck": (0, -178), "hip": (0, -40), "tilt": 0,
        "arms": [[(0, -168), (-62, -128), (22, -122)], [(0, -168), (62, -128), (-22, -122)]],
        "legs": [[(0, -40), (-42, -150), (-52, -6)], [(0, -40), (42, -150), (52, -6)]],
    },
    "pushing": {
        "head": (108, -318), "neck": (62, -268), "hip": (-18, -150), "tilt": 28,
        "arms": [[(55, -255), (120, -240), (175, -250)], [(55, -255), (115, -212), (170, -212)]],
        "legs": [[(-18, -150), (-60, -80), (-110, 0)], [(-18, -150), (20, -80), (10, 0)]],
    },
    "hunched": {  # dáng khom — dùng cho chuỗi tiến hoá
        "head": (95, -240), "neck": (55, -205), "hip": (-35, -140), "tilt": 20,
        "arms": [[(45, -198), (75, -120), (95, -12)], [(45, -198), (40, -110), (55, -12)]],
        "legs": [[(-35, -140), (-60, -70), (-55, 0)], [(-35, -140), (-5, -70), (-10, 0)]],
    },
    "sleeping": {  # nằm ngang, đầu bên trái
        "head": (-215, -64), "neck": (-150, -42), "hip": (15, -40), "tilt": -90,
        "arms": [[(-120, -42), (-60, -30), (0, -24)], [(-120, -44), (-70, -58), (-10, -50)]],
        "legs": [[(15, -40), (100, -38), (185, -30)], [(15, -40), (100, -52), (180, -50)]],
    },
}

EXTRAS = {
    "zzz": "chữ Z Z Z khi ngủ",
    "sweat": "giọt mồ hôi (lo lắng/gắng sức)",
    "shock_lines": "tia sốc quanh đầu",
    "sparkle": "lấp lánh vui vẻ",
    "tears": "nước mắt",
}


def _pt(rad, deg):
    return rad * math.cos(math.radians(deg)), rad * math.sin(math.radians(deg))


def _hair(pen, variant):
    r = HEAD_R
    if variant == "you_main":
        outer = [_pt(r + (34 if i % 2 else 6), -162 + 144 * i / 9) for i in range(10)]
        inner = [_pt(r - 18, a) for a in range(-18, -163, -12)]
        return pen.poly(outer + inner, C["orange"], amp=1.2)
    if variant == "ancient_human":
        outer = [_pt(r + pen.jitter(20 if i % 2 else 8, 5), -205 + 230 * i / 14) for i in range(15)]
        inner = [_pt(r - 12, a) for a in range(25, -206, -14)]
        return pen.poly(outer + inner, C["hair_brown"], amp=2.2)
    if variant == "elder_grandmother":
        outer = [_pt(r + 6, a) for a in range(-172, -7, 12)]
        inner = [_pt(r - 16, a) for a in range(-10, -173, -12)]
        return pen.circle(0, -r - 18, 26, C["hair_gray"]) + pen.poly(outer + inner, C["hair_gray"], amp=1.4)
    if variant == "archaeologist":
        # mũ thám hiểm đội cao trên trán để không che mắt
        dome = [(x, y - 26) for x, y in (_pt(r + 2, a) for a in range(-180, 1, 12))]
        return (pen.poly(dome, C["sand_tan"], amp=1.2)
                + pen.ellipse(0, -28, r + 34, 13, C["sand_tan"], amp=1)
                + pen.line([(-r + 6, -48), (r - 6, -48)], width=5, stroke=C["wood_brown"]))
    return ""


def _face(pen, expression):
    e = []
    bw = 4.5
    if expression == "sleeping":
        for sx in (-1, 1):
            e.append(pen.shape(f"M{sx*34},-4 Q{sx*22},6 {sx*10},-4", width=bw))
        e.append(pen.line([(-10, 28), (10, 28)], width=bw))
        return "".join(e)
    if expression == "surprise":
        for sx in (-1, 1):
            e.append(pen.circle(sx * 22, -6, 13, C["white"], width=4))
            e.append(f'<circle cx="{sx*22}" cy="-5" r="6" fill="{INK}"/>')
            e.append(pen.shape(f"M{sx*36},-34 Q{sx*22},-46 {sx*8},-36", width=bw))
        e.append(pen.ellipse(0, 30, 9, 13, INK, width=3))
        return "".join(e)

    for sx in (-1, 1):
        e.append(f'<circle cx="{sx*22}" cy="-4" r="7" fill="{INK}"/>')
    if expression == "strain_anger":
        for sx in (-1, 1):
            e.append(pen.line([(sx * 38, -34), (sx * 9, -20)], width=bw))
        e.append(pen.rect(-24, 18, 48, 17, C["white"], width=3.5))
        for x in (-12, 0, 12):
            e.append(f'<line x1="{x}" y1="19" x2="{x}" y2="34" stroke="{INK}" stroke-width="2.5"/>')
    elif expression == "worry_sadness":
        for sx in (-1, 1):
            e.append(pen.line([(sx * 38, -20), (sx * 10, -33)], width=bw))
        e.append(pen.shape("M-18,34 Q0,20 18,34", width=bw))
    elif expression == "happy":
        for sx in (-1, 1):
            e.append(pen.shape(f"M{sx*36},-28 Q{sx*24},-38 {sx*10},-30", width=bw))
        e.append(pen.shape("M-24,14 Q0,50 24,14 Z", fill=C["pink"], width=4))
    elif expression == "thinking":
        e.append(pen.line([(-36, -26), (-12, -28)], width=bw))
        e.append(pen.shape("M12,-34 Q24,-44 38,-36", width=bw))
        e.append(pen.line([(-6, 26), (20, 20)], width=bw))
    else:  # calm_content
        for sx in (-1, 1):
            e.append(pen.line([(sx * 36, -27), (sx * 12, -30)], width=bw))
        e.append(pen.shape("M-18,20 Q0,34 18,20", width=bw))
    return "".join(e)


def _head(pen, cx, cy, tilt, variant, expression):
    hair = _hair(pen, variant)  # vẽ tóc trước để đổi biểu cảm không làm tóc rung khác đi
    face = _face(pen, expression)
    if tilt <= -60:  # nằm: tóc xoay theo đầu, mặt giữ thẳng để vẫn đọc được biểu cảm
        face = f'<g transform="rotate({-tilt})">{face}</g>'
    body = pen.circle(0, 0, HEAD_R, C["white"]) + face + hair
    return f'<g transform="translate({cx:.1f},{cy:.1f}) rotate({tilt})">{body}</g>'


def _extras(pen, hx, hy, extras, d=1):
    """d = hướng nhìn (1 phải, -1 trái) để hiệu ứng nằm đúng phía mà chữ không bị lật."""
    out = []
    for fx in extras:
        if fx == "zzz":
            for dx, dy, fs in ((40, -110, 46), (85, -160, 60), (140, -220, 76)):
                out.append(f'<text x="{hx+d*dx}" y="{hy+dy}" font-family="{FONT_FAMILY}" font-size="{fs}" '
                           f'fill="{C["white"]}" stroke="{INK}" stroke-width="5" paint-order="stroke">Z</text>')
        elif fx == "sweat":
            for dx, dy in ((-80, -38), (-94, 12)):
                sx, sy = hx + d * dx, hy + dy
                out.append(pen.poly([(sx, sy - 22), (sx + 11, sy), (sx, sy + 10), (sx - 11, sy)],
                                    C["blue"], width=3.5, amp=0.8))
        elif fx == "tears":
            for sx in (-1, 1):
                x0 = hx + sx * 22
                out.append(pen.poly([(x0, hy + 6), (x0 + 8, hy + 30), (x0, hy + 40), (x0 - 8, hy + 30)],
                                    C["blue"], width=3, amp=0.6))
        elif fx == "shock_lines":
            for a in (-150, -120, -60, -30):
                c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
                out.append(pen.line([(hx + c * 90, hy + s * 90), (hx + c * 125, hy + s * 125)], width=5))
        elif fx == "sparkle":
            for dx, dy, r in ((-95, -60, 16), (100, -70, 20), (80, 20, 12)):
                x0, y0 = hx + d * dx, hy + dy
                out.append(pen.poly([(x0, y0 - r), (x0 + r * .3, y0 - r * .3), (x0 + r, y0), (x0 + r * .3, y0 + r * .3),
                                     (x0, y0 + r), (x0 - r * .3, y0 + r * .3), (x0 - r, y0), (x0 - r * .3, y0 - r * .3)],
                                    C["yellow"], width=3, amp=0.4))
    return "".join(out)


def pose_extents(pose):
    """Khung bao cục bộ (min_x, max_x, top) của một tư thế ở scale 1, chưa lật."""
    p = POSES.get(pose, POSES["standing"])
    pts = [pt for limb in p["arms"] + p["legs"] for pt in limb] + [p["neck"], p["hip"]]
    hx, hy = p["head"]
    xs = [x for x, _ in pts] + [hx - HEAD_R - 12, hx + HEAD_R + 12]
    return min(xs) - 12, max(xs) + 12, hy - HEAD_R - 40


def character(pen, x, ground_y, variant="you_main", pose="standing", expression="calm_content",
              scale=1.0, flip=False, extras=()):
    """Trả về (svg, anchors) — anchors là toạ độ tuyệt đối của đầu/tay/đỉnh để gắn đạo cụ, bong bóng."""
    p = POSES.get(pose, POSES["standing"])
    if pose == "sleeping" and expression == "calm_content":
        expression = "sleeping"
    parts = []
    upright = pose not in ("sleeping", "hugging_knees", "hunched", "sitting")
    if variant == "archaeologist" and upright:
        nx, ny = p["neck"]
        hipx, hipy = p["hip"]
        parts.append(pen.rect(nx - 62, ny + 8, 48, (hipy - ny) * 0.55, C["wood_brown"], amp=1))
    if variant == "elder_grandmother" and upright:
        nx, ny = p["neck"]
        parts.append(pen.poly([(nx - 14, ny + 6), (nx + 14, ny + 6), (nx + 62, p["hip"][1] + 40),
                               (nx - 62, p["hip"][1] + 40)], C["purple_mauve"]))
    parts.append(pen.line([p["neck"], p["hip"]], width=LIMB))
    for is_foot, limbs in ((True, p["legs"]), (False, p["arms"])):
        for limb in limbs:
            parts.append(pen.line(limb, width=LIMB))
            ex, ey = limb[-1]
            if is_foot:
                rx, ry = (8, 14) if pose == "sleeping" else (15, 8)
                parts.append(pen.ellipse(ex + (0 if pose == "sleeping" else 5), ey - 4, rx, ry, INK, width=2))
            else:
                parts.append(pen.ellipse(ex, ey, 11, 11, INK, width=2))
    hx, hy = p["head"]
    parts.append(_head(pen, hx, hy, p["tilt"], variant, expression))

    sx = -scale if flip else scale
    svg = f'<g transform="translate({x:.1f},{ground_y:.1f}) scale({sx},{scale})">{"".join(parts)}</g>'
    if extras:
        ax, ay = x + hx * sx, ground_y + hy * scale
        svg += (f'<g transform="translate({ax:.1f},{ay:.1f}) scale({scale})">'
                f'{_extras(pen, 0, 0, extras, -1 if flip else 1)}</g>')

    def to_abs(pt):
        return (x + pt[0] * sx, ground_y + pt[1] * scale)
    _, _, top = pose_extents(pose)
    anchors = {"head": to_abs(p["head"]), "hand": to_abs(p.get("hand", p["arms"][1][-1])),
               "top": to_abs((p["head"][0], top)), "scale": scale, "flip": flip}
    return svg, anchors
