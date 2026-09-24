"""Vẽ các cảnh mẫu để duyệt style: python -m doodle.samples <thư_mục_ra>"""
import os
import sys

from PIL import Image

from .scene import render_scene

SAMPLES = {
    "01_night_campfire": {
        "frame": "scene", "bg": "deep_night",
        "elements": [
            {"type": "prop", "name": "moon", "x": 0.86, "y": 0.17, "scale": 0.9},
            {"type": "prop", "name": "campfire", "id": "fire", "x": 0.52, "scale": 1.1},
            {"type": "character", "variant": "ancient_human", "pose": "sleeping", "x": 0.2, "extras": ["zzz"]},
            {"type": "character", "variant": "you_main", "pose": "sitting", "expression": "surprise",
             "attach": {"to": "fire", "side": "right", "gap": 60}},
            {"type": "label", "text": "SEGMENTED SLEEP", "y": 0.13},
        ],
    },
    "02_label_on_boulder_vi": {
        "frame": "scene", "bg": "outdoor_daytime",
        "elements": [
            {"type": "prop", "name": "tree", "x": 0.08, "scale": 0.9},
            {"type": "prop", "name": "boulder", "id": "rock", "x": 0.62, "scale": 1.6},
            {"type": "label", "text": "SINH TỒN", "on": "rock", "size": 110},
            {"type": "character", "variant": "you_main", "pose": "pushing", "expression": "strain_anger",
             "extras": ["sweat"], "attach": {"to": "rock", "side": "left"}},
            {"type": "label", "text": "Tổ tiên của bạn phải vật lộn mỗi ngày", "y": 0.12, "size": 90},
        ],
    },
    "03_thought_bubble": {
        "frame": "scene", "bg": "ancient_savanna",
        "elements": [
            {"type": "prop", "name": "acacia", "x": 0.8},
            {"type": "character", "id": "me", "variant": "ancient_human", "pose": "thinking",
             "expression": "thinking", "x": 0.32},
            {"type": "thought", "of": "me", "prop": "mammoth"},
            {"type": "prop", "name": "spear", "x": 0.18, "scale": 0.9},
        ],
    },
    "04_red_x": {
        "frame": "scene", "bg": "neutral_modern",
        "elements": [
            {"type": "prop", "name": "bed", "id": "bed", "x": 0.5, "scale": 1.3},
            {"type": "character", "variant": "modern_neutral", "pose": "sleeping", "x": 0.5, "y": 0.72,
             "extras": ["zzz"]},
            {"type": "label", "text": "8 HOURS STRAIGHT", "y": 0.15},
            {"type": "red_x"},
        ],
    },
    "05_evolution": {
        "frame": "scene", "bg": "ancient_savanna",
        "elements": [
            {"type": "character", "id": "a", "variant": "ancient_human", "pose": "hunched", "x": 0.14, "scale": 0.9},
            {"type": "character", "id": "b", "variant": "ancient_human", "pose": "walking", "x": 0.5, "scale": 0.95},
            {"type": "character", "id": "c", "variant": "you_main", "pose": "holding", "holding": "phone",
             "x": 0.86},
            {"type": "arrow", "between": ["a", "b"]},
            {"type": "arrow", "between": ["b", "c"]},
            {"type": "label", "text": "300,000 YEARS OF EVOLUTION", "y": 0.12, "size": 100},
        ],
    },
    "06_sad_rain_archaeologist": {
        "frame": "split",
        "left": {"bg": "neutral_default", "title": "HARDSHIP", "elements": [
            {"type": "character", "id": "sad", "variant": "you_main", "pose": "hugging_knees",
             "expression": "worry_sadness", "extras": ["tears"], "x": 0.5, "scale": 1.3},
            {"type": "prop", "name": "rain_cloud", "above": "sad"},
        ]},
        "right": {"bg": "outdoor_daytime", "title": "DISCOVERY", "elements": [
            {"type": "prop", "name": "cave", "id": "cave", "x": 0.72, "scale": 0.95},
            {"type": "character", "variant": "archaeologist", "pose": "holding", "holding": "lantern",
             "expression": "surprise", "attach": {"to": "cave", "side": "left", "gap": 10}, "scale": 1.05},
            {"type": "prop", "name": "skull", "x": 0.9, "scale": 0.8},
        ]},
    },
    "07_timeline": {
        "frame": "timeline", "title": "HOW LONG HAVE YOU BEEN HUMAN?", "highlight": 3,
        "events": [
            {"label": "300,000 BC", "text": "Homo sapiens appears", "icon": "skull"},
            {"label": "40,000 BC", "text": "Cave paintings", "icon": "cave"},
            {"label": "10,000 BC", "text": "Farming begins", "icon": "basket"},
            {"label": "1879", "text": "The light bulb", "icon": "lightbulb"},
            {"label": "TODAY", "text": "You, on your phone", "icon": "phone"},
        ],
    },
    "08_stats_vi": {
        "frame": "stats", "title": "BẠN NGỦ BAO NHIÊU TIẾNG?",
        "bars": [
            {"label": "Người săn bắt hái lượm", "value": 7.5, "display": "7,5 giờ"},
            {"label": "Năm 1910", "value": 9, "display": "9 giờ"},
            {"label": "Ngày nay", "value": 6.8, "display": "6,8 giờ", "color": "red"},
        ],
    },
}


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name, spec in SAMPLES.items():
        warnings = []
        paths.append(render_scene(spec, os.path.join(out_dir, f"{name}.png"), warnings))
        for w in warnings:
            print(f"[{name}] ⚠ {w}")
    cols = 2
    thumbs = [Image.open(p).resize((960, 540)) for p in paths]
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (960 * cols + 10 * (cols + 1), 540 * rows + 10 * (rows + 1)), "#FFFFFF")
    for i, t in enumerate(thumbs):
        sheet.paste(t, (10 + (i % cols) * 970, 10 + (i // cols) * 550))
    sheet_path = os.path.join(out_dir, "contact_sheet.png")
    sheet.save(sheet_path)
    print("\n".join(paths + [sheet_path]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1] if len(sys.argv) > 1 else "style_samples")
