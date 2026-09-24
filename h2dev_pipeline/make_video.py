"""H2Dev Doodle Video — CLI.

  python make_video.py init <slug> --title "..." [--lang en|vi]   tạo projects/<slug>/scenes.json mẫu
  python make_video.py validate <slug|thư_mục> [--json]           kiểm tra kịch bản + hình (không vẽ PNG)
  python make_video.py preview <slug|thư_mục> [--scene N]         vẽ nháp → projects/<slug>/preview/
  python make_video.py vocab                                       in danh mục từ vựng bộ vẽ (JSON)
"""
import argparse
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.project import ProjectError, load_project, resolve_project_dir, validate  # noqa: E402

TEMPLATE_SCENES = [
    {"frame": "scene", "bg": "deep_night",
     "elements": [
         {"type": "prop", "name": "campfire", "id": "fire", "x": 0.5},
         {"type": "character", "id": "me", "variant": "you_main", "pose": "sitting",
          "attach": {"to": "fire", "side": "left", "gap": 60}},
         {"type": "label", "id": "title", "text": "YOUR TITLE HERE", "y": 0.13}],
     "lines": [
         {"text": "First line of narration."},
         {"text": "Second line reveals the title.", "show": ["title"],
          "change": {"me": {"expression": "surprise"}}}]},
    {"frame": "concept_text", "text": "300,000 YEARS", "lines": [{"text": "A key number gets its own frame."}]},
]


def load_config():
    p = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def cmd_init(a):
    d = os.path.join(BASE_DIR, "projects", a.slug)
    path = os.path.join(d, "scenes.json")
    if os.path.exists(path):
        print(f"[!] Đã có {path} — không ghi đè.")
        return 1
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"title": a.title, "language": a.lang, "scenes": TEMPLATE_SCENES}, f, ensure_ascii=False, indent=2)
    print(f"[✓] Đã tạo {path}")
    return 0


def cmd_validate(a):
    d = resolve_project_dir(a.project, BASE_DIR)
    project = load_project(d)
    errors, warnings, stats = validate(project, cfg=load_config())
    if a.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats},
                         ensure_ascii=False, indent=1))
        return 1 if errors else 0
    if stats:
        print(f"[i] {stats['scenes']} cảnh · {stats['lines']} câu · {stats['words']} từ · "
              f"~{stats['est_minutes']} phút ({stats['language']})")
    for e in errors:
        print(f"[LỖI] {e}")
    for w in warnings:
        print(f"[⚠] {w}")
    print("[✓] Hợp lệ — có thể preview/build." if not errors else f"[✗] {len(errors)} lỗi cần sửa.")
    return 1 if errors else 0


def cmd_preview(a):
    from core.preview import preview_all, preview_scene_steps
    d = resolve_project_dir(a.project, BASE_DIR)
    project = load_project(d)
    errors, _, _ = validate(project, cfg=load_config())
    if errors:
        for e in errors:
            print(f"[LỖI] {e}")
        print("[✗] Sửa lỗi trước khi preview (chạy validate để xem chi tiết).")
        return 1
    if a.scene:
        print(preview_scene_steps(project, d, a.scene))
    else:
        for p in preview_all(project, d):
            print(p)
    return 0


def cmd_vocab(a):
    from doodle.catalog import vocabulary
    print(json.dumps(vocabulary(), ensure_ascii=False, indent=1))
    return 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="H2Dev Doodle Video")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("slug")
    p.add_argument("--title", required=True)
    p.add_argument("--lang", default="en", choices=["en", "vi"])
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("validate")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_validate)
    p = sub.add_parser("preview")
    p.add_argument("project")
    p.add_argument("--scene", type=int, help="chỉ vẽ các bước hiện dần của cảnh N")
    p.set_defaults(fn=cmd_preview)
    p = sub.add_parser("vocab")
    p.set_defaults(fn=cmd_vocab)
    a = ap.parse_args()
    try:
        return a.fn(a)
    except ProjectError as e:
        print(f"[LỖI] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
