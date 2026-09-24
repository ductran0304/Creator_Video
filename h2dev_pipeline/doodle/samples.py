"""Vẽ các cảnh mẫu để duyệt style: python -m doodle.samples <thư_mục_ra>"""
import os
import sys

from PIL import Image

from .scene import render_scene

SAMPLES = {
    "01_night_campfire": {
        "frame": "scene", "bg": "deep_night",
        "elements": [
            {"type": "prop", "name": "moon", "x": 0.84, "y": 0.17, "scale": 0.9},
            {"type": "prop", "name": "campfire", "x": 0.55, "scale": 1.1},
            {"type": "character", "variant": "ancient_human", "pose": "sleeping", "x": 0.27, "extras": ["zzz"]},
            {"type": "character", "variant": "you_main", "pose": "sitting", "expression": "surprise", "x": 0.78,
             "flip": True},
            {"type": "label", "text": "SEGMENTED SLEEP", "y": 0.13},
        ],
    },
    "02_concept_text": {
        "frame": "concept_text", "text": "300,000 YEARS", "sub": "of sleeping without an alarm clock",
    },
    "03_split_then_now": {
        "frame": "split",
        "left": {
            "bg": "ancient_savanna", "title": "THEN",
            "elements": [
                {"type": "prop", "name": "acacia", "x": 0.72, "scale": 0.9},
                {"type": "character", "variant": "ancient_human", "pose": "arms_up", "x": 0.35, "scale": 1.15},
            ],
        },
        "right": {
            "bg": "neutral_modern", "title": "NOW",
            "elements": [
                {"type": "prop", "name": "clock", "x": 0.78, "y": 0.42, "scale": 0.9},
                {"type": "character", "variant": "modern_neutral", "pose": "holding", "expression": "worry_sadness",
                 "x": 0.42, "scale": 1.15, "holding": "phone", "extras": ["sweat"]},
            ],
        },
    },
    "04_vi_boulder": {
        "frame": "scene", "bg": "outdoor_daytime",
        "elements": [
            {"type": "prop", "name": "tree", "x": 0.1, "scale": 0.9},
            {"type": "prop", "name": "boulder", "x": 0.62, "scale": 1.5},
            {"type": "label", "text": "SINH TỒN", "color": "white", "x": 0.62, "y": 0.62, "size": 90},
            {"type": "character", "variant": "you_main", "pose": "pushing", "expression": "strain_anger",
             "x": 0.33, "extras": ["sweat"]},
            {"type": "character", "variant": "elder_grandmother", "pose": "pointing", "x": 0.88, "flip": True,
             "scale": 0.9},
            {"type": "label", "text": "Tổ tiên của bạn đã phải vật lộn mỗi ngày", "y": 0.12, "size": 80},
        ],
    },
}


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = [render_scene(spec, os.path.join(out_dir, f"{name}.png")) for name, spec in SAMPLES.items()]
    thumbs = [Image.open(p).resize((960, 540)) for p in paths]
    sheet = Image.new("RGB", (960 * 2 + 30, 540 * 2 + 30), "#FFFFFF")
    for i, t in enumerate(thumbs):
        sheet.paste(t, (10 + (i % 2) * 970, 10 + (i // 2) * 550))
    sheet_path = os.path.join(out_dir, "contact_sheet.png")
    sheet.save(sheet_path)
    print("\n".join(paths + [sheet_path]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "style_samples")
