"""Thư viện đồ vật: khối đơn giản, màu phẳng, viền đen dày (visual_style_dna.animals_objects).

Mỗi đồ vật vẽ trong toạ độ cục bộ ở scale 1 (khung 1080px):
- anchor="bottom": gốc (0,0) là điểm giữa đáy, đặt lên mặt đất;
- anchor="center": gốc là tâm (đồ trên trời / biểu tượng).
Metadata: w = nửa bề ngang, h = chiều cao, grip = điểm tay cầm (cho `holding`),
label_box = (cx, cy, rộng) vùng viết chữ lên vật (cho label `on`).
"""
import math

from . import assets
from .palette import C
from .text import FONT_FAMILY

INK = C["ink"]
PROPS = {}


def prop(name, w, h, desc, anchor="bottom", grip=None, hand_scale=1.0, label_box=None):
    def deco(fn):
        PROPS[name] = {"fn": fn, "w": w, "h": h, "desc": desc, "anchor": anchor, "grip": grip,
                       "hand_scale": hand_scale,
                       "label_box": label_box or (0, -h / 2 if anchor == "bottom" else 0, w * 1.5)}
        return fn
    return deco


def prop_body(pen, name, ctx=None):
    """SVG cục bộ của đồ vật: asset vẽ sẵn nếu có (assets/props/<name>.svg), không thì vẽ bằng code."""
    ctx = ctx or {}
    body = assets.get("props", name)
    if body is None:
        return PROPS[name]["fn"](pen, ctx)
    if ctx.get("cracked"):  # vết nứt lớn vẽ đè lên asset = vật đang vỡ
        h = PROPS[name]["h"]
        body += pen.line([(-8, -h * 0.98), (14, -h * 0.7), (-18, -h * 0.5), (18, -h * 0.25), (0, 0)], width=7)
    return body


def draw_prop(pen, name, x, y, scale, ctx=None, flip=False):
    sx = -scale if flip else scale
    return f'<g transform="translate({x:.1f},{y:.1f}) scale({sx:.3f},{scale:.3f})">{prop_body(pen, name, ctx)}</g>'


def _cloud_pts(rx, ry, bumps=7, depth=0.22):
    pts = []
    for i in range(72):
        t = 2 * math.pi * i / 72
        k = 1 + depth * abs(math.sin(bumps * t / 2))
        pts.append((rx * k * math.cos(t), ry * k * math.sin(t)))
    return pts


# ---------------- thiên nhiên ----------------
@prop("tree", 115, 360, "cây tròn xanh")
def tree(pen, ctx):
    return pen.rect(-20, -170, 40, 170, C["wood_brown"]) + pen.circle(0, -250, 110, C["grass_green"], amp=4)


@prop("acacia", 230, 355, "cây keo tán dẹt (savan)")
def acacia(pen, ctx):
    return (pen.poly([(-18, 0), (-10, -190), (-75, -265), (-58, -272), (0, -212), (52, -280), (68, -272),
                      (12, -190), (20, 0)], C["wood_brown"])
            + pen.ellipse(0, -300, 230, 55, C["grass_green"], amp=4))


@prop("bush", 115, 135, "bụi cây")
def bush(pen, ctx):
    return pen.poly([(x, y - 60) for x, y in _cloud_pts(110, 60, 5, 0.25)] , C["grass_green"], amp=2)


@prop("berry_bush", 115, 135, "bụi quả mọng (hái lượm)")
def berry_bush(pen, ctx):
    out = bush(pen, ctx)
    for bx, by in ((-60, -70), (-20, -95), (30, -60), (65, -85), (0, -40), (-45, -35), (50, -30)):
        out += pen.circle(bx, by, 11, C["red_text"], width=3, amp=0.5)
    return out


@prop("boulder", 165, 200, "tảng đá xám lớn (hợp để viết chữ lên)", label_box=(0, -95, 250))
def boulder(pen, ctx):
    out = pen.poly([(-150, 0), (-165, -70), (-110, -165), (-10, -200), (95, -170), (160, -90), (150, 0)],
                   C["rock_gray"], amp=3.5)
    if ctx.get("cracked"):
        out += pen.line([(-10, -198), (15, -140), (-20, -100), (20, -50), (0, 0)], width=6)
    elif not ctx.get("labeled"):
        out += pen.line([(-60, -120), (-35, -80), (-50, -40)], width=4) + pen.line([(70, -130), (50, -95)], width=4)
    return out


@prop("rock", 60, 50, "hòn đá nhỏ")
def rock(pen, ctx):
    return pen.poly([(-60, 0), (-50, -35), (-10, -50), (40, -40), (60, 0)], C["rock_gray"], amp=2)


@prop("mountain", 380, 420, "núi có tuyết")
def mountain(pen, ctx):
    return (pen.poly([(-380, 0), (-40, -420), (380, 0)], C["rock_gray"], amp=4)
            + pen.poly([(-40, -420), (-120, -322), (-80, -300), (-40, -330), (0, -296), (40, -320)],
                       C["white"], amp=2))


@prop("sun", 110, 220, "mặt trời", anchor="center")
def sun(pen, ctx):
    out = ""
    for i in range(10):
        a = 2 * math.pi * i / 10
        out += pen.line([(95 * math.cos(a), 95 * math.sin(a)), (130 * math.cos(a), 130 * math.sin(a))],
                        width=7, stroke=INK)
    return out + pen.circle(0, 0, 72, C["yellow"])


@prop("moon", 70, 140, "trăng lưỡi liềm", anchor="center")
def moon(pen, ctx):
    bg = ctx.get("bg_color", C["night_navy"])
    return pen.circle(0, 0, 70, C["yellow"], width=5) + pen.circle(34, -18, 62, bg, width=0, amp=0)


@prop("cloud", 150, 110, "đám mây trắng", anchor="center")
def cloud(pen, ctx):
    return pen.poly(_cloud_pts(130, 50), C["white"], amp=1.5)


@prop("rain_cloud", 150, 260, "mây đen mưa (buồn bã, khó khăn)", anchor="center")
def rain_cloud(pen, ctx):
    out = ""
    for i, dx in enumerate((-90, -45, 0, 45, 90)):
        for j in range(2):
            x0, y0 = dx + (j * 22 if i % 2 else -j * 18), 85 + j * 70 + (i % 2) * 30
            out += pen.poly([(x0, y0 - 20), (x0 + 9, y0 + 2), (x0, y0 + 11), (x0 - 9, y0 + 2)], C["blue"],
                            width=3, amp=0.5)
    return out + pen.poly(_cloud_pts(130, 50), C["dark_gray"], amp=1.5)


# ---------------- đời sống tiền sử ----------------
@prop("campfire", 110, 175, "lửa trại")
def campfire(pen, ctx):
    return (pen.poly([(-110, -18), (95, -52), (105, -28), (-100, 6)], C["dirt_brown"])
            + pen.poly([(-95, -52), (110, -18), (100, 6), (-105, -28)], C["light_wood"])
            + pen.poly([(-62, -40), (-72, -110), (-35, -85), (-18, -175), (12, -95), (42, -140), (68, -40)],
                       C["orange"])
            + pen.poly([(-30, -42), (-34, -92), (-8, -72), (6, -125), (24, -78), (38, -42)], C["yellow"], width=4))


@prop("torch", 30, 240, "đuốc", grip=(0, -60), hand_scale=0.75)
def torch(pen, ctx):
    return (pen.line([(0, 0), (0, -175)], width=16, stroke=INK) + pen.line([(0, -2), (0, -173)], width=9,
                                                                        stroke=C["wood_brown"])
            + pen.poly([(-26, -170), (-30, -205), (-10, -195), (0, -240), (14, -198), (30, -210), (26, -170)],
                       C["orange"])
            + pen.poly([(-12, -172), (-10, -196), (2, -214), (12, -192), (12, -172)], C["yellow"], width=3))


@prop("spear", 22, 420, "giáo đá", grip=(0, -190), hand_scale=0.7)
def spear(pen, ctx):
    return (pen.line([(0, 0), (0, -360)], width=16, stroke=INK) + pen.line([(0, -2), (0, -358)], width=9,
                                                                        stroke=C["wood_brown"])
            + pen.poly([(-20, -350), (0, -420), (20, -350)], C["rock_gray"], width=5))


@prop("stone_tool", 45, 80, "rìu tay bằng đá", grip=(0, -20))
def stone_tool(pen, ctx):
    return (pen.poly([(-40, -10), (-30, -55), (0, -80), (30, -55), (40, -10), (0, 0)], C["rock_gray"], amp=1.5)
            + pen.line([(-15, -55), (0, -30), (15, -58)], width=3.5) + pen.line([(0, -30), (0, -8)], width=3.5))


@prop("cave", 320, 360, "hang đá có cửa tối")
def cave(pen, ctx):
    return (pen.poly([(-300, 0), (-270, -210), (-150, -330), (40, -360), (220, -290), (310, -120), (320, 0)],
                     C["rock_gray"], amp=4)
            + pen.poly([(-130, 0), (-120, -150), (-40, -215), (60, -200), (125, -120), (135, 0)], "#2A2A2A", amp=3))


@prop("hut", 175, 250, "lều cỏ tranh")
def hut(pen, ctx):
    out = pen.poly([(-175, 0), (-160, -110), (-90, -210), (0, -250), (90, -210), (160, -110), (175, 0)],
                   C["yellow"], amp=3)
    for x in (-110, -55, 0, 55, 110):
        out += pen.line([(x * 0.6, -215 + abs(x) * 0.5), (x, -10)], width=3.5, stroke=C["wood_brown"])
    return out + pen.poly([(-45, 0), (-45, -95), (0, -120), (45, -95), (45, 0)], "#3A2A1A", amp=1.5)


@prop("tent", 150, 290, "lều da thú hình nón")
def tent(pen, ctx):
    return (pen.line([(-30, -250), (15, -290)], width=7) + pen.line([(30, -250), (-15, -290)], width=7)
            + pen.poly([(-150, 0), (0, -260), (150, 0)], C["light_wood"], amp=3)
            + pen.poly([(-40, 0), (0, -110), (40, 0)], "#3A2A1A", amp=1.5)
            + pen.line([(-70, -60), (-40, -70)], width=4) + pen.line([(80, -40), (100, -55)], width=4))


@prop("basket", 62, 85, "giỏ đan")
def basket(pen, ctx):
    out = pen.poly([(-62, -85), (62, -85), (45, 0), (-45, 0)], C["light_wood"])
    for y in (-60, -35, -12):
        out += pen.line([(-55 + (85 + y) * 0.1, y), (55 - (85 + y) * 0.1, y)], width=3.5, stroke=C["wood_brown"])
    return out


@prop("clay_pot", 55, 100, "vò gốm")
def clay_pot(pen, ctx):
    return pen.poly([(-25, -100), (25, -100), (22, -85), (55, -50), (40, -8), (0, 0), (-40, -8), (-55, -50),
                     (-22, -85)], "#C0643A", amp=1.5) + pen.line([(-45, -50), (45, -50)], width=3.5)


@prop("meat", 62, 50, "đùi thịt nướng", grip=(-50, -25))
def meat(pen, ctx):
    return (pen.poly([(-62, -32), (-50, -38), (-42, -30), (-50, -12), (-62, -18)], C["white"], width=4, amp=0.6)
            + pen.line([(-46, -25), (-15, -25)], width=14, stroke=INK) + pen.line([(-46, -25), (-15, -25)], width=7,
                                                                           stroke=C["white"])
            + pen.ellipse(20, -25, 42, 25, C["dirt_brown"], amp=1.5))


@prop("fish", 75, 45, "con cá")
def fish(pen, ctx):
    return (pen.poly([(45, -22), (75, -44), (75, 0)], C["blue"], amp=1)
            + pen.ellipse(0, -22, 52, 22, C["blue"], amp=1.2) + f'<circle cx="-28" cy="-26" r="5" fill="{INK}"/>')


@prop("bone", 62, 26, "khúc xương")
def bone(pen, ctx):
    out = pen.line([(-45, -13), (45, -13)], width=20, stroke=INK) + pen.line([(-45, -13), (45, -13)], width=12,
                                                                           stroke=C["white"])
    for x in (-50, 50):
        out += pen.circle(x, -20, 11, C["white"], width=4, amp=0.5) + pen.circle(x, -6, 11, C["white"], width=4,
                                                                             amp=0.5)
    return out


@prop("skull", 50, 80, "hộp sọ (khảo cổ)")
def skull(pen, ctx):
    return (pen.rect(-24, -30, 48, 30, C["white"], amp=1) + pen.circle(0, -48, 48, C["white"], amp=1.2)
            + pen.ellipse(-18, -45, 12, 14, INK, width=2) + pen.ellipse(18, -45, 12, 14, INK, width=2)
            + pen.line([(-10, -18), (-10, -2)], width=3) + pen.line([(10, -18), (10, -2)], width=3))


@prop("lantern", 32, 95, "đèn lồng vàng", grip=(0, -92))
def lantern(pen, ctx):
    return (pen.shape("M-18,-75 Q0,-100 18,-75", width=5)
            + pen.rect(-30, -75, 60, 12, C["dark_gray"], width=4, amp=0.6)
            + pen.rect(-26, -63, 52, 52, C["yellow"], width=5, amp=1)
            + pen.rect(-30, -12, 60, 12, C["dark_gray"], width=4, amp=0.6))


@prop("shield", 60, 125, "khiên gỗ")
def shield(pen, ctx):
    return (pen.poly([(-60, -125), (60, -125), (55, -50), (0, 0), (-55, -50)], C["light_wood"], amp=1.5)
            + pen.line([(0, -120), (0, -8)], width=5) + pen.line([(-55, -85), (55, -85)], width=5))


@prop("crate", 90, 130, "thùng gỗ", label_box=(0, -65, 150))
def crate(pen, ctx):
    out = pen.rect(-90, -130, 180, 130, C["light_wood"])
    if not ctx.get("labeled"):
        out += pen.line([(-85, -125), (85, -5)], width=5) + pen.line([(-85, -5), (85, -125)], width=5)
    return out


@prop("hourglass", 60, 165, "đồng hồ cát (thời gian)", label_box=(0, -82, 90))
def hourglass(pen, ctx):
    return (pen.poly([(-45, -150), (45, -150), (5, -82), (45, -14), (-45, -14), (-5, -82)], C["cave_light_blue"],
                     amp=1)
            + pen.poly([(-26, -118), (26, -118), (0, -86)], C["yellow"], width=3, amp=0.5)
            + pen.poly([(-38, -18), (38, -18), (0, -52)], C["yellow"], width=3, amp=0.5)
            + pen.rect(-60, -165, 120, 16, C["wood_brown"], amp=0.8) + pen.rect(-60, -16, 120, 16, C["wood_brown"],
                                                                            amp=0.8))


# ---------------- động vật ----------------
@prop("mammoth", 240, 310, "voi ma mút (nhìn sang phải)")
def mammoth(pen, ctx):
    fur = C["dirt_brown"]
    out = ""
    for lx in (-150, -90, 60, 120):
        out += pen.rect(lx, -110, 48, 110, fur, amp=1)
    out += pen.poly([(x - 20, y - 185) for x, y in _cloud_pts(170, 105, 9, 0.08)], fur, amp=2)
    out += pen.circle(150, -230, 70, fur, amp=1.5)
    out += pen.line([(195, -205), (228, -140), (220, -60), (240, -30)], width=34, stroke=INK)
    out += pen.line([(195, -205), (228, -140), (220, -60), (240, -30)], width=22, stroke=fur)
    out += pen.shape("M175,-185 Q250,-150 265,-215", width=14, stroke=INK)
    out += pen.shape("M175,-185 Q250,-150 265,-215", width=8, stroke=C["white"])
    out += f'<circle cx="165" cy="-245" r="7" fill="{INK}"/>'
    return out


@prop("wolf", 125, 130, "sói xám (nhìn sang phải)")
def wolf(pen, ctx):
    g = C["rock_gray"]
    out = pen.poly([(-110, -80), (-160, -120), (-120, -70)], g, amp=1)
    for lx in (-80, -45, 40, 72):
        out += pen.rect(lx, -55, 20, 55, g, width=5, amp=0.6)
    out += pen.ellipse(-5, -75, 105, 40, g, amp=1.5)
    out += pen.poly([(70, -80), (85, -140), (100, -110), (118, -140), (125, -100), (160, -85), (110, -60)], g, amp=1)
    return out + f'<circle cx="112" cy="-100" r="5" fill="{INK}"/>'


@prop("deer", 115, 215, "hươu có gạc (nhìn sang phải)")
def deer(pen, ctx):
    t = C["sand_tan"]
    out = ""
    for lx in (-70, -40, 40, 65):
        out += pen.line([(lx, -90), (lx, 0)], width=10)
    out += pen.ellipse(0, -110, 90, 38, t, amp=1.5)
    out += pen.poly([(55, -130), (70, -190), (90, -190), (85, -125)], t, amp=1)
    out += pen.ellipse(100, -195, 30, 20, t, amp=1)
    out += pen.line([(80, -210), (70, -250), (55, -265)], width=5) + pen.line([(70, -250), (85, -270)], width=5)
    out += pen.line([(95, -212), (110, -250), (130, -262)], width=5)
    return out + f'<circle cx="108" cy="-200" r="4.5" fill="{INK}"/>'


# ---------------- đời sống hiện đại ----------------
@prop("phone", 25, 90, "điện thoại thông minh", grip=(0, -40))
def phone(pen, ctx):
    return pen.rect(-24, -90, 48, 90, INK, width=4, amp=0.8) + pen.rect(-17, -80, 34, 64, C["blue"], width=2, amp=0.5)


@prop("laptop", 95, 90, "laptop")
def laptop(pen, ctx):
    return (pen.poly([(-75, -20), (-65, -90), (65, -90), (75, -20)], C["dark_gray"], amp=1)
            + pen.poly([(-60, -28), (-52, -80), (52, -80), (60, -28)], C["blue"], width=3, amp=0.6)
            + pen.poly([(-95, 0), (-78, -22), (78, -22), (95, 0)], C["light_gray"], amp=1))


@prop("desk", 170, 150, "bàn làm việc")
def desk(pen, ctx):
    return (pen.rect(-150, -130, 22, 130, C["wood_brown"]) + pen.rect(128, -130, 22, 130, C["wood_brown"])
            + pen.rect(-170, -150, 340, 26, C["light_wood"]))


@prop("bed", 230, 110, "giường")
def bed(pen, ctx):
    return (pen.rect(-230, -70, 460, 55, C["light_wood"])
            + pen.rect(-230, -110, 40, 110, C["wood_brown"]) + pen.rect(190, -85, 40, 85, C["wood_brown"])
            + pen.rect(-185, -100, 110, 34, C["white"]) + pen.rect(-70, -96, 255, 30, C["blue"]))


@prop("crib", 130, 135, "nôi em bé")
def crib(pen, ctx):
    out = pen.rect(-130, -45, 260, 30, C["light_wood"])
    for x in range(-120, 130, 30):
        out += pen.line([(x, -130), (x, -45)], width=5)
    out += pen.line([(-130, -130), (130, -130)], width=7)
    return out + pen.rect(-130, -15, 18, 15, C["wood_brown"]) + pen.rect(112, -15, 18, 15, C["wood_brown"])


@prop("clock", 92, 184, "đồng hồ treo tường", anchor="center")
def clock(pen, ctx):
    return (pen.circle(0, 0, 90, C["white"], width=7) + pen.line([(0, 0), (0, -60)], width=7)
            + pen.line([(0, 0), (42, 20)], width=7))


@prop("alarm_clock", 62, 115, "đồng hồ báo thức")
def alarm_clock(pen, ctx):
    return (pen.line([(-35, -10), (-48, 0)], width=6) + pen.line([(35, -10), (48, 0)], width=6)
            + pen.circle(-38, -100, 20, C["yellow"], width=5) + pen.circle(38, -100, 20, C["yellow"], width=5)
            + pen.circle(0, -55, 52, C["red_text"]) + pen.circle(0, -55, 38, C["white"], width=4)
            + pen.line([(0, -55), (0, -80)], width=4) + pen.line([(0, -55), (18, -48)], width=4))


@prop("coffee", 42, 62, "cốc cà phê", grip=(-40, -32))
def coffee(pen, ctx):
    return (pen.shape("M28,-45 Q52,-35 28,-18", width=6)
            + pen.poly([(-30, -62), (30, -62), (25, 0), (-25, 0)], C["white"], amp=0.8)
            + pen.rect(-30, -45, 60, 15, C["dirt_brown"], width=0, amp=0.5))


@prop("burger", 65, 62, "bánh burger (đồ ăn nhanh)")
def burger(pen, ctx):
    return (pen.rect(-60, -18, 120, 18, C["yellow"], amp=0.8) + pen.rect(-65, -30, 130, 14, C["dirt_brown"], amp=0.8)
            + pen.poly([(-62, -32), (-40, -40), (0, -34), (40, -40), (62, -32)], C["grass_green"], width=4, amp=0.6)
            + pen.shape("M-60,-38 Q-58,-78 0,-80 Q58,-78 60,-38 Z", fill=C["yellow"]))


@prop("house", 190, 310, "nhà hiện đại", label_box=(0, -95, 240))
def house(pen, ctx):
    return (pen.rect(-160, -190, 320, 190, C["cream"])
            + pen.poly([(-190, -185), (0, -310), (190, -185)], C["red_text"], amp=2)
            + pen.rect(-35, -110, 70, 110, C["wood_brown"]) + pen.rect(70, -150, 60, 55, C["cave_light_blue"], amp=1)
            + pen.rect(-130, -150, 60, 55, C["cave_light_blue"], amp=1))


@prop("building", 120, 520, "toà nhà cao tầng / văn phòng")
def building(pen, ctx):
    out = pen.rect(-120, -520, 240, 520, "#9FB3C8", amp=2)
    for row in range(8):
        for col in range(3):
            out += pen.rect(-90 + col * 65, -490 + row * 58, 45, 36, C["cave_light_blue"], width=3.5, amp=0.5)
    return out


@prop("car", 175, 125, "ô tô (nhìn sang phải)")
def car(pen, ctx):
    return (pen.poly([(-110, -70), (-70, -125), (60, -125), (100, -70)], C["cave_light_blue"], amp=1)
            + pen.poly([(-175, -25), (-170, -75), (160, -75), (175, -25)], C["red_text"], amp=1.5)
            + pen.line([(-5, -120), (-5, -75)], width=5)
            + pen.circle(-105, -22, 32, INK, width=3) + pen.circle(105, -22, 32, INK, width=3)
            + pen.circle(-105, -22, 12, C["light_gray"], width=2) + pen.circle(105, -22, 12, C["light_gray"], width=2))


@prop("money", 75, 42, "tờ tiền", anchor="center", grip=(-60, 0))
def money(pen, ctx):
    return (pen.rect(-75, -40, 150, 80, "#8FCB7A", amp=1) + pen.circle(0, 0, 24, "#C9E8BE", width=4, amp=0.5)
            + f'<text x="0" y="2" text-anchor="middle" dominant-baseline="central" font-family="{FONT_FAMILY}" '
              f'font-size="38" fill="{INK}">$</text>')


@prop("book", 58, 45, "quyển sách", grip=(0, -22))
def book(pen, ctx):
    return (pen.rect(-58, -45, 116, 45, C["red_text"], amp=0.8) + pen.rect(-50, -12, 100, 8, C["white"], width=2,
                                                                         amp=0.4))


# ---------------- biểu tượng ----------------
@prop("lightbulb", 48, 110, "bóng đèn ý tưởng", anchor="center")
def lightbulb(pen, ctx):
    out = ""
    for a in (-150, -120, -90, -60, -30):
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        out += pen.line([(c * 62, s * 62 - 10), (c * 85, s * 85 - 10)], width=5)
    return (out + pen.circle(0, -10, 45, C["yellow"]) + pen.rect(-20, 30, 40, 26, C["light_gray"], width=5, amp=0.6))


@prop("heart", 52, 50, "trái tim", anchor="center")
def heart(pen, ctx):
    pts = [(3.2 * 16 * math.sin(t) ** 3, -3.2 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t)
                                               - math.cos(4 * t)))
           for t in [2 * math.pi * i / 48 for i in range(48)]]
    return pen.poly(pts, C["red_text"], amp=1)


def _symbol(ch, size=170):
    return (f'<text x="0" y="0" text-anchor="middle" dominant-baseline="central" font-family="{FONT_FAMILY}" '
            f'font-size="{size}" fill="{C["red_text"]}" stroke="{INK}" stroke-width="7" paint-order="stroke">{ch}</text>')


@prop("question_mark", 45, 170, "dấu hỏi lớn", anchor="center")
def question_mark(pen, ctx):
    return _symbol("?")


@prop("exclamation", 25, 170, "dấu chấm than lớn", anchor="center")
def exclamation(pen, ctx):
    return _symbol("!")


@prop("sign", 115, 235, "biển gỗ cắm đất (viết chữ lên)", label_box=(0, -170, 200))
def sign(pen, ctx):
    return pen.rect(-12, -150, 24, 150, C["wood_brown"]) + pen.rect(-115, -225, 230, 105, C["light_wood"])


# ---------------- asset thêm sau (không cần code) ----------------
def _missing_asset(name):
    def fn(pen, ctx):
        raise ValueError(f"prop '{name}' đã đăng ký nhưng chưa có file assets/props/{name}.svg")
    return fn


for _name, _m in assets.sidecars("props").items():
    if _name in PROPS:
        continue  # prop có sẵn trong code: json chỉ để tham khảo, metadata code thắng
    prop(_name, _m["w"], _m["h"], _m.get("desc", _name), anchor=_m.get("anchor", "bottom"),
         grip=tuple(_m["grip"]) if _m.get("grip") else None, hand_scale=_m.get("hand_scale", 1.0),
         label_box=tuple(_m["label_box"]) if _m.get("label_box") else None)(_missing_asset(_name))
