"""Bảng màu chuẩn của kênh — khớp visual_style_dna.color_palette_hex trong h2dev_knowledge_base.json."""

C = {
    "orange": "#F58220",
    "sky_blue": "#7FB5D5",
    "cave_light_blue": "#ABD3E5",
    "grass_green": "#4E9A45",
    "sand_tan": "#D2B488",
    "dirt_brown": "#8B5A2B",
    "wood_brown": "#7A4F2A",
    "rock_gray": "#8A8A8A",
    "night_navy": "#283A6E",
    "deep_indigo": "#322B5E",
    "red_text": "#E0302B",
    "yellow": "#F4C430",
    "purple_mauve": "#8B7CB0",
    "cream": "#F5F1E6",
    "white": "#FFFFFF",
    # phụ trợ (không có trong DNA nhưng cần cho chi tiết)
    "ink": "#141414",
    "dark_gray": "#5A5A5E",
    "light_gray": "#BDBDBD",
    "blue": "#4FA9E0",
    "light_wood": "#A0683A",
    "hair_brown": "#6E4220",
    "hair_gray": "#C4C4C4",
    "savanna_orange": "#F7A440",
    "pink": "#F29BB0",
    "leaf_dark": "#3C7A36",
}

# Tên màu Claude được dùng trong JSON (label.color, ...) → mã hex
NAMED = {"red": C["red_text"], "white": C["white"], "black": C["ink"], "orange": C["orange"],
         "yellow": C["yellow"], "blue": C["blue"], "green": C["grass_green"]}
