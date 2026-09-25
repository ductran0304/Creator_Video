"""Hồ sơ thương hiệu: brands/<tên>/brand.json. scenes.json ghi "brand": "<tên>" để áp dụng:
bảng màu, font, giọng đọc, phụ đề, ngưỡng độ dài, logo mờ ở góc và màn kết kêu gọi liên hệ (tự thêm cuối video)."""
import datetime
import glob
import json
import os

from doodle import scene as doodle_scene
from doodle.theme import set_theme


def brand_dir(base_dir, name):
    return os.path.join(base_dir, "brands", name)


def load_brand(base_dir, name):
    p = os.path.join(brand_dir(base_dir, name), "brand.json")
    if not os.path.exists(p):
        raise FileNotFoundError(f"Không có hồ sơ thương hiệu {p}")
    with open(p, "r", encoding="utf-8") as f:
        b = json.load(f)
    b["_dir"] = brand_dir(base_dir, name)
    return b


def _fonts(brand):
    out = []
    for pat in brand.get("fonts", []):
        pat = pat if os.path.isabs(pat) or pat.startswith("/") or ":" in pat else os.path.join(brand["_dir"], pat)
        out += [p for p in glob.glob(pat) if os.path.isfile(p)]
    return out


def activate(project, base_dir, cfg):
    """Áp dụng thương hiệu của project (nếu có). Trả về (brand | None, cfg đã ghép)."""
    name = project.get("brand")
    doodle_scene.EXTRA_FONTS[:] = []
    if not name:
        set_theme(None)
        return None, cfg
    brand = load_brand(base_dir, name)
    theme = dict(brand.get("theme") or {})
    for cand in theme.pop("font_file_candidates", []):  # file font để đo chữ: cái đầu tiên có trên máy
        p = cand if os.path.isabs(cand) or ":" in cand else os.path.join(brand["_dir"], cand)
        if os.path.isfile(p):
            theme["font_file"] = p
            break
    set_theme(theme)
    doodle_scene.EXTRA_FONTS[:] = _fonts(brand)
    for k in ("voice", "voice_rate", "burn_subtitles", "language"):
        if k in brand:
            project.setdefault(k, brand[k])
    cfg = dict(cfg)
    for k in ("script_word_count_min", "script_word_count_max", "scene_count_min", "scene_count_max"):
        if k in brand:
            cfg[k] = brand[k]
    outro = brand.get("outro")
    scenes = project.get("scenes")
    if outro and isinstance(scenes, list) and not any(s.get("_auto_outro") for s in scenes if isinstance(s, dict)):
        updated = project.get("updated") or datetime.date.today().strftime("%d/%m/%Y")
        scenes.append({
            "_auto_outro": True, "frame": "brand_card", "chapter": project.get("outro_chapter", "Liên hệ"),
            "logo_path": os.path.join(brand["_dir"], outro["logo"]),
            "headline": outro.get("headline", ""), "card_lines": outro.get("card_lines", []),
            "disclaimer": outro.get("note", "").replace("{updated}", updated),
            "lines": [{"text": outro["voice"]}],
        })
    project["_brand"] = brand
    return brand, cfg


def watermark_png(brand, height):
    """Logo nhỏ ở góc (RGBA bytes PNG) hoặc None."""
    wm = brand.get("watermark") if brand else None
    if not wm:
        return None
    with open(os.path.join(brand["_dir"], wm["logo"]), "r", encoding="utf-8") as f:
        svg = f.read()
    import resvg_py
    from doodle.text import FONT_PATH
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, height=int(height), skip_system_fonts=True,
                                       font_files=[FONT_PATH] + doodle_scene.EXTRA_FONTS))
