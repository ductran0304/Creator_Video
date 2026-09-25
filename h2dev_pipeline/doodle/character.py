"""Nhân vật người que theo visual DNA của kênh (h2dev_knowledge_base.json → visual_style_dna).

Toạ độ cục bộ: gốc = điểm chân chạm đất, y hướng xuống, nhân vật mặc định nhìn sang PHẢI
(flip=True để nhìn sang trái). Kích thước ở scale 1 cao ~450px trên khung 1080px.
"""
import math

from .palette import C
from .text import FONT_FAMILY

INK = C["ink"]
HEAD_R = 62
LIMB = 8

VARIANTS = {
    "you_main": "Nhân vật chính 'you' — tóc cam dựng",
    "ancient_human": "Người tiền sử — tóc nâu bù xù",
    "modern_neutral": "Người hiện đại trung tính — đầu trọc",
    "elder_grandmother": "Bà cụ — tóc bạc búi + váy tím",
    "archaeologist": "Nhà khảo cổ — mũ thám hiểm nâu + ba lô",
    "shop_owner": "Chủ hộ kinh doanh / chủ tiệm — tóc bob đen, tạp dề hồng san hô",
    "kttg_accountant": "Kế toán viên KTTG — tóc rẽ ngôi, kính, áo xanh ngọc có thẻ nhân viên",
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
        # ngồi bệt co gối, hai tay đặt trên đầu gối
        "head": (0, -262), "neck": (0, -200), "hip": (0, -60), "tilt": 0,
        "arms": [[(0, -184), (-52, -150), (-74, -112)], [(0, -184), (52, -150), (76, -110)]],
        "legs": [[(0, -60), (-78, -118), (-62, -6)], [(0, -60), (80, -116), (66, -6)]],
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



def _pt(rad, deg):
    return rad * math.cos(math.radians(deg)), rad * math.sin(math.radians(deg))


def _hair(pen, variant):
    r = HEAD_R
    if variant == "you_main":
        # tóc dựng: chỏm dài ngắn khác nhau, ngọn hất về phía trước (không đều như vương miện)
        tips = [(-150, 26), (-128, 40), (-104, 50), (-80, 46), (-56, 38), (-34, 26)]
        outer = [_pt(r + 4, -170)]
        for i, (a, L) in enumerate(tips):
            outer.append(_pt(r + L, a + 9))                       # ngọn lệch về trước
            nxt = tips[i + 1][0] if i + 1 < len(tips) else -12
            outer.append(_pt(r + 6 + (i % 2) * 4, (a + nxt) / 2))  # chân chỏm
        inner = [_pt(r - 18, a) for a in range(-12, -171, -12)]
        return pen.poly(outer + inner, C["orange"], amp=1.0)
    if variant == "ancient_human":
        outer = [_pt(r + pen.jitter(22 if i % 2 else 9, 5), -210 + 240 * i / 16) for i in range(17)]
        inner = [_pt(r - 12, a) for a in range(30, -211, -14)]
        out = pen.poly(outer + inner, C["hair_brown"], amp=2.0)
        for a in (-140, -95, -50):  # vài sợi tóc rối
            x0, y0 = _pt(r + 2, a)
            x1, y1 = _pt(r + 16, a + 12)
            out += pen.line([(x0, y0), (x1, y1)], width=3.5)
        return out
    if variant == "elder_grandmother":
        outer = [_pt(r + 7, a) for a in range(-174, -5, 12)]
        inner = [_pt(r - 16, a) for a in range(-8, -175, -12)]
        return pen.circle(0, -r - 18, 26, C["hair_gray"]) + pen.poly(outer + inner, C["hair_gray"], amp=1.4)
    if variant == "shop_owner":
        outer = [_pt(r + 9, a) for a in range(-196, 17, 12)]
        inner = [_pt(r - 14, a) for a in range(16, -197, -12)]
        inner = [(x, max(y, -r * 0.55)) if -150 < math.degrees(math.atan2(y, x)) < -30 else (x, y) for x, y in inner]
        return pen.poly(outer + inner, "#1E1E24", amp=1.2)
    if variant == "kttg_accountant":
        outer = [_pt(r + 8, a) for a in range(-178, -1, 12)]
        inner = [_pt(r - 17, a) for a in range(-2, -179, -12)]
        return (pen.poly(outer + inner, "#1E1E24", amp=1.0)
                + pen.line([_pt(r - 6, -125), _pt(r + 6, -118)], width=3.5, stroke="#F4F7FF"))
    if variant == "archaeologist":
        # mũ thám hiểm đội cao trên trán để không che mắt
        dome = [(x, y - 26) for x, y in (_pt(r + 2, a) for a in range(-180, 1, 12))]
        return (pen.poly(dome, C["sand_tan"], amp=1.2)
                + pen.ellipse(0, -28, r + 34, 13, C["sand_tan"], amp=1)
                + pen.line([(-r + 6, -48), (r - 6, -48)], width=5, stroke=C["wood_brown"]))
    return ""


def _eyes(e, dx=22, y=-4, r=7.5):
    for sx in (-1, 1):
        e.append(f'<circle cx="{sx*dx}" cy="{y}" r="{r}" fill="{INK}"/>')
        e.append(f'<circle cx="{sx*dx + 2.6:.1f}" cy="{y - 2.8:.1f}" r="{r * 0.3:.1f}" fill="#FFFFFF"/>')


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
            e.append(f'<circle cx="{sx*22 + 2}" cy="-7" r="1.8" fill="#FFFFFF"/>')
            e.append(pen.shape(f"M{sx*36},-34 Q{sx*22},-46 {sx*8},-36", width=bw))
        e.append(pen.ellipse(0, 30, 9, 13, INK, width=3))
        return "".join(e)

    _eyes(e)
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
            e.append(f'<ellipse cx="{sx*38}" cy="14" rx="10" ry="6" fill="{C["pink"]}" fill-opacity="0.75"/>')
        e.append(pen.shape("M-24,14 Q0,50 24,14 Z", fill=C["pink"], width=4))
    elif expression == "thinking":
        e.append(pen.line([(-36, -26), (-12, -28)], width=bw))
        e.append(pen.shape("M12,-34 Q24,-44 38,-36", width=bw))
        e.append(pen.line([(-6, 26), (20, 20)], width=bw))
    else:  # calm_content
        for sx in (-1, 1):
            e.append(pen.line([(sx * 36, -27), (sx * 12, -30)], width=bw))
            e.append(f'<ellipse cx="{sx*38}" cy="14" rx="8" ry="4.5" fill="{C["pink"]}" fill-opacity="0.45"/>')
        e.append(pen.shape("M-18,20 Q0,34 18,20", width=bw))
    return "".join(e)


def _head(pen, cx, cy, tilt, variant, expression):
    hair = _hair(pen, variant)  # vẽ tóc trước để đổi biểu cảm không làm tóc rung khác đi
    face = _face(pen, expression)
    if tilt <= -60:  # nằm: tóc xoay theo đầu, mặt giữ thẳng để vẫn đọc được biểu cảm
        face = f'<g transform="rotate({-tilt})">{face}</g>'
    if variant == "kttg_accountant":  # kính gọng tròn
        glasses = "".join(pen.circle(sx * 22, -4, 16, "none", width=4, amp=0.4) for sx in (-1, 1))
        glasses += pen.line([(-6, -6), (6, -6)], width=4)
        face = face + (f'<g transform="rotate({-tilt})">{glasses}</g>' if tilt <= -60 else glasses)
    body = pen.circle(0, 0, HEAD_R, C["white"]) + face + hair
    return f'<g transform="translate({cx:.1f},{cy:.1f}) rotate({tilt})">{body}</g>'


def _curve(a, j, b, n=10):
    """Đường cong bậc 2 đi QUA khớp j (khuỷu/gối) — tay chân mềm thay vì gãy góc."""
    cx, cy = 2 * j[0] - (a[0] + b[0]) / 2, 2 * j[1] - (a[1] + b[1]) / 2
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u * u * a[0] + 2 * u * t * cx + t * t * b[0], u * u * a[1] + 2 * u * t * cy + t * t * b[1]))
    return pts


def _limb_pts(limb):
    return _curve(*limb) if len(limb) == 3 else limb


OUTFITS = {
    "none": "không mặc gì thêm (người que thuần)",
    "fur": "áo da thú tiền sử",
    "shirt": "áo sơ mi kaki (nhà thám hiểm)",
    "dress": "váy dài (bà cụ)",
    "apron": "tạp dề bán hàng (chủ tiệm)",
    "kttg_shirt": "áo xanh ngọc + dây đeo thẻ KTTG",
}
DEFAULT_OUTFIT = {"ancient_human": "fur", "archaeologist": "shirt", "elder_grandmother": "dress",
                  "shop_owner": "apron", "kttg_accountant": "kttg_shirt"}


def _outfit(pen, p, kind):
    """Áo vẽ dọc trục cổ→hông nên đúng với mọi tư thế (kể cả nằm, khom)."""
    (nx, ny), (hx, hy) = p["neck"], p["hip"]
    L = math.hypot(hx - nx, hy - ny) or 1
    ux, uy = (hx - nx) / L, (hy - ny) / L
    vx, vy = -uy, ux

    def at(d, off):
        return (nx + ux * d + vx * off, ny + uy * d + vy * off)
    if kind == "fur":
        hem = L + 48
        pts = [at(10, -24), at(4, 6), at(12, 30), at(L * 0.55, 42)]
        for i in range(8):  # gấu áo răng cưa
            off = 50 - 100 * i / 7
            pts.append(at(hem + (12 if i % 2 else -4), off))
        pts.append(at(L * 0.5, -40))
        out = pen.poly(pts, C["light_wood"], amp=1.6)
        for d, off in ((L * 0.35, 12), (L * 0.7, -18), (L * 0.9, 20)):
            x, y = at(d, off)
            out += pen.ellipse(x, y, 9, 6, C["wood_brown"], width=0, amp=0.6)
        return out
    if kind == "shirt":
        out = pen.poly([at(6, -30), at(6, 30), at(L + 18, 34), at(L + 18, -34)], "#C8B27A", amp=1.2)
        return out + pen.line([at(10, 0), at(L + 10, 0)], width=3)
    if kind == "apron":
        out = pen.poly([at(L * 0.18, -26), at(L * 0.18, 26), at(L + 46, 40), at(L + 46, -40)], "#FF5C7A", amp=1.2)
        out += pen.line([at(4, -18), at(L * 0.2, -22)], width=4) + pen.line([at(4, 18), at(L * 0.2, 22)], width=4)
        return out + pen.rect(*at(L * 0.62, -16), 32, 22, "#FFD1DA", width=3.5, amp=0.5)
    if kind == "kttg_shirt":
        out = pen.poly([at(6, -32), at(6, 32), at(L + 16, 36), at(L + 16, -36)], "#00C2A8", amp=1.2)
        out += pen.line([at(6, -12), at(L * 0.5, 0), at(6, 12)], width=4, stroke="#101A3D")
        bx, by = at(L * 0.5, 0)
        return out + pen.rect(bx - 12, by, 24, 30, "#FFC93C", width=3.5, amp=0.5)
    if kind == "dress":
        return pen.poly([at(4, -16), at(4, 16), at(L + 40, 64), at(L + 40, -64)], C["purple_mauve"])
    return ""


def pose_extents(pose):
    """Khung bao cục bộ (min_x, max_x, top) của một tư thế ở scale 1, chưa lật."""
    p = POSES.get(pose, POSES["standing"])
    pts = [pt for limb in p["arms"] + p["legs"] for pt in limb] + [p["neck"], p["hip"]]
    hx, hy = p["head"]
    xs = [x for x, _ in pts] + [hx - HEAD_R - 12, hx + HEAD_R + 12]
    return min(xs) - 12, max(xs) + 12, hy - HEAD_R - 40


def character(pen, x, ground_y, variant="you_main", pose="standing", expression="calm_content",
              scale=1.0, flip=False, extras=(), outfit=None):
    """Trả về (svg, anchors) — anchors là toạ độ tuyệt đối của đầu/tay/đỉnh để gắn đạo cụ, bong bóng."""
    p = POSES.get(pose, POSES["standing"])
    if pose == "sleeping" and expression == "calm_content":
        expression = "sleeping"
    outfit = outfit or DEFAULT_OUTFIT.get(variant, "none")
    if pose == "sleeping" and outfit != "none":  # áo nằm ngang trông như khúc gỗ → bỏ
        outfit = "none"
    parts = []
    upright = pose not in ("sleeping", "hugging_knees", "hunched", "sitting")
    if variant == "archaeologist" and upright:  # ba lô sau lưng
        nx, ny = p["neck"]
        hipy = p["hip"][1]
        parts.append(pen.rect(nx - 66, ny + 8, 50, (hipy - ny) * 0.58, C["wood_brown"], amp=1))
        parts.append(pen.line([(nx - 60, ny + 30), (nx - 22, ny + 30)], width=3.5))

    for leg in p["legs"]:
        parts.append(pen.line(_limb_pts(leg), width=LIMB))
        ex, ey = leg[-1]
        if pose == "sleeping":
            parts.append(pen.ellipse(ex, ey - 4, 9, 16, INK, width=2))
        else:  # giày nhô về phía trước
            parts.append(pen.ellipse(ex + 8, ey - 6, 19, 10, INK, width=2))
    parts.append(pen.line([p["neck"], p["hip"]], width=LIMB))
    parts.append(_outfit(pen, p, outfit))
    for arm in p["arms"]:
        parts.append(pen.line(_limb_pts(arm), width=LIMB))
        ex, ey = arm[-1]
        parts.append(pen.ellipse(ex, ey, 12.5, 12, INK, width=2))
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
