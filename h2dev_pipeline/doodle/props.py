"""Thư viện đồ vật: khối đơn giản, màu phẳng, viền đen dày (visual_style_dna.animals_objects).

Mỗi hàm nhận (pen, x, ground_y, scale, ctx) với x là tâm, ground_y là mặt đất; trả về chuỗi SVG.
ctx chứa thông tin phụ như màu nền (để khoét trăng lưỡi liềm) hoặc điểm neo tay nhân vật.
"""
from .pen import INK


def _g(x, y, scale, body):
    return f'<g transform="translate({x:.1f},{y:.1f}) scale({scale})">{body}</g>'


def campfire(pen, x, y, scale, ctx):
    b = [
        pen.poly([(-110, -18), (95, -52), (105, -28), (-100, 6)], "#8B5A2B"),
        pen.poly([(-95, -52), (110, -18), (100, 6), (-105, -28)], "#A0683A"),
        pen.poly([(-62, -40), (-72, -110), (-35, -85), (-18, -175), (12, -95), (42, -140), (68, -40)], "#FF8A1F"),
        pen.poly([(-30, -42), (-34, -92), (-8, -72), (6, -125), (24, -78), (38, -42)], "#FFD23F", width=4),
    ]
    return _g(x, y, scale, "".join(b))


def boulder(pen, x, y, scale, ctx):
    b = [pen.poly([(-150, 0), (-165, -70), (-110, -165), (-10, -200), (95, -170), (160, -90), (150, 0)],
                  "#8C8C8C", amp=3.5),
         pen.line([(-60, -120), (-35, -80), (-50, -40)], width=4),
         pen.line([(70, -130), (50, -95)], width=4)]
    return _g(x, y, scale, "".join(b))


def acacia(pen, x, y, scale, ctx):
    b = [pen.poly([(-18, 0), (-10, -190), (-75, -265), (-58, -272), (0, -212), (52, -280), (68, -272),
                   (12, -190), (20, 0)], "#7A4A21"),
         pen.ellipse(0, -300, 230, 55, "#5E9E3A", amp=4)]
    return _g(x, y, scale, "".join(b))


def tree(pen, x, y, scale, ctx):
    b = [pen.rect(-20, -170, 40, 170, "#8B5A2B"),
         pen.circle(0, -250, 110, "#5E9E3A", amp=4)]
    return _g(x, y, scale, "".join(b))


def phone(pen, x, y, scale, ctx):
    # đặt vào tay nhân vật nếu có điểm neo
    hx, hy = ctx.get("hand", (x, y - 300))
    s = scale * ctx.get("char_scale", 1.0)
    b = [pen.rect(-24, -44, 48, 88, INK, width=4, amp=0.8),
         pen.rect(-17, -34, 34, 62, "#5BC0F0", width=2, amp=0.5)]
    return _g(hx, hy - 10 * s, s, "".join(b))


def moon(pen, x, y, scale, ctx):
    bg = ctx.get("bg_color", "#1E2A5A")
    b = [pen.circle(0, 0, 70, "#FFD23F", width=5), pen.circle(34, -18, 62, bg, width=0, amp=0)]
    return _g(x, y, scale, "".join(b))


def cave(pen, x, y, scale, ctx):
    b = [pen.poly([(-300, 0), (-270, -210), (-150, -330), (40, -360), (220, -290), (310, -120), (320, 0)],
                  "#7D7D7D", amp=4),
         pen.poly([(-130, 0), (-120, -150), (-40, -215), (60, -200), (125, -120), (135, 0)], "#2A2A2A", amp=3)]
    return _g(x, y, scale, "".join(b))


def bed(pen, x, y, scale, ctx):
    b = [pen.rect(-230, -70, 460, 55, "#A0683A"),
         pen.rect(-230, -110, 40, 110, "#8B5A2B"), pen.rect(190, -85, 40, 85, "#8B5A2B"),
         pen.rect(-185, -100, 110, 34, "#FFFFFF"),
         pen.rect(-70, -96, 255, 30, "#5BC0F0")]
    return _g(x, y, scale, "".join(b))


def clock(pen, x, y, scale, ctx):
    b = [pen.circle(0, -120, 90, "#FFFFFF", width=7),
         pen.line([(0, -120), (0, -180)], width=7), pen.line([(0, -120), (42, -100)], width=7)]
    return _g(x, y, scale, "".join(b))


def spear(pen, x, y, scale, ctx):
    b = [pen.line([(0, 0), (0, -360)], width=9, stroke="#8B5A2B"),
         pen.poly([(-18, -350), (0, -420), (18, -350)], "#8C8C8C", width=5)]
    return _g(x, y, scale, "".join(b))


PROPS = {
    "campfire": campfire, "boulder": boulder, "acacia": acacia, "tree": tree, "phone": phone,
    "moon": moon, "cave": cave, "bed": bed, "clock": clock, "spear": spear,
}
