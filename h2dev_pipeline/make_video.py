"""H2Dev Doodle Video — CLI.

  python make_video.py init <slug> --title "..." [--lang en|vi]   tạo projects/<slug>/scenes.json mẫu
  python make_video.py validate <slug|thư_mục> [--json]           kiểm tra kịch bản + hình (không vẽ PNG)
  python make_video.py preview <slug|thư_mục> [--scene N]         vẽ nháp → projects/<slug>/preview/
  python make_video.py build <slug|thư_mục> [--draft] [--no-short|--short-only]
                                                                 dựng video dài 16:9 + bản dọc 9:16 + gói đăng tải
                                                                 → projects/<slug>/publish/ (mở PUBLISH.md)
  python make_video.py publish <slug|thư_mục>                     chỉ ghi lại metadata YouTube/Shorts/TikTok/Reels
  python make_video.py thumbnail <slug|thư_mục>                   vẽ thử thumbnail + cover 9:16 các bản dọc → preview/
  python make_video.py stats import <file.csv> [--brand b]        nhập số liệu YouTube Studio (giữ chân, CTR...)
  python make_video.py stats show [--brand b]                     tóm tắt video tốt/kém để rút kinh nghiệm
  python make_video.py asset new|check ...                        thêm asset mới cho thư viện (xem core/assets_cli.py)
  python make_video.py vocab                                     in danh mục từ vựng bộ vẽ (JSON)
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


def load(project_arg):
    """Đọc project + áp dụng thương hiệu (màu, font, giọng, màn kết) nếu scenes.json có "brand"."""
    from core.brand import activate
    d = resolve_project_dir(project_arg, BASE_DIR)
    project = load_project(d)
    brand, cfg = activate(project, BASE_DIR, load_config())
    from doodle.theme import T
    T["today"] = project.get("updated")  # khung deadline đếm "Còn N ngày" từ ngày cập nhật của video
    from doodle import scene as ds
    ds.PHOTO_DIRS[:] = [os.path.join(d, "photos")] + ([os.path.join(brand["_dir"], "photos")] if brand else [])
    return d, project, cfg


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
    d, project, cfg = load(a.project)
    errors, warnings, stats = validate(project, cfg=cfg)
    if a.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats},
                         ensure_ascii=False, indent=1))
        return 1 if errors else 0
    if stats:
        print(f"[i] {stats['scenes']} cảnh · {stats['lines']} câu · {stats['words']} từ · "
              f"~{stats['est_minutes']} phút ({stats['language']}) · bản dọc ~{stats['short_seconds']}s")
    for e in errors:
        print(f"[LỖI] {e}")
    for w in warnings:
        print(f"[⚠] {w}")
    print("[✓] Hợp lệ — có thể preview/build." if not errors else f"[✗] {len(errors)} lỗi cần sửa.")
    return 1 if errors else 0


def cmd_preview(a):
    from core.preview import preview_all, preview_scene_steps
    d, project, cfg = load(a.project)
    errors, _, _ = validate(project, cfg=cfg)
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


def cmd_build(a):
    from core.build import build
    d, project, cfg = load(a.project)
    build(project, d, cfg, BASE_DIR, draft=a.draft, subs=True if a.subs else None,
          long=not a.short_only, short=not a.no_short)
    return 0


def cmd_publish(a):
    from core.build import republish
    d, project, cfg = load(a.project)
    print(f"[✓] {republish(project, d)}")
    return 0


def cmd_thumbnail(a):
    """Thumbnail 16:9 + cover 9:16 của từng bản dọc (thời lượng ước lượng, không cần đọc giọng)."""
    from core import publish, vertical
    d, project, cfg = load(a.project)
    seo = publish.load_seo(d)
    out = os.path.join(d, "preview")
    os.makedirs(out, exist_ok=True)
    print(publish.write_thumbnail(project, seo, os.path.join(out, "thumbnail.png")))
    for p in vertical.plans(project):
        n = len(p["items"]) + 1
        segs, total, refs = vertical.timeline(p, [3.0] * n, [None] * n, cfg)
        lay = vertical.Layout(project, p, (vertical.VW, vertical.VH), total, segs)
        shots = vertical.render_shots(p, refs, os.path.join(d, "cache", "frames_v"), lay)
        name = "cover.png" if p["folder"] == "short" else f"cover_{p['id']}.png"
        print(publish.write_cover(project, seo, p, shots, segs, os.path.join(out, name)))
    return 0


def cmd_stats(a):
    from core import stats
    if a.stats_cmd == "import":
        print(stats.import_csv(BASE_DIR, a.csv, a.brand))
    else:
        print(stats.show(BASE_DIR, a.brand))
    return 0


def cmd_photo(a):
    from core import photos
    if a.photo_cmd == "search":
        results, sheet = photos.search(BASE_DIR, a.query, a.n, a.allow_sa)
        for i, r in enumerate(results, 1):
            print(f"{i:2d}. [{photos.LICENSE_NAMES.get(r['license'], r['license'])}] {r.get('title') or ''} — "
                  f"{r.get('creator') or '?'} ({r.get('source')}, {r.get('width')}x{r.get('height')})")
        print(f"[i] Bảng xem trước: {sheet}")
        return 0
    d = resolve_project_dir(a.project, BASE_DIR)
    jpg, meta = photos.get(BASE_DIR, d, a.idx, a.name)
    print(f"[✓] {jpg}")
    print(f"    {photos.credit_line(meta)}")
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
    p = sub.add_parser("build")
    p.add_argument("project")
    p.add_argument("--draft", action="store_true", help="bản nháp 960x540, 12fps — dựng rất nhanh để kiểm tra")
    p.add_argument("--subs", action="store_true", help="in phụ đề lên hình (ghi đè burn_subtitles)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--no-short", action="store_true", help="không dựng bản dọc 9:16")
    g.add_argument("--short-only", action="store_true", help="chỉ dựng bản dọc 9:16 (giữ video dài đã có)")
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser("publish", help="ghi lại gói metadata đăng tải từ seo.json (không dựng video)")
    p.add_argument("project")
    p.set_defaults(fn=cmd_publish)
    p = sub.add_parser("thumbnail")
    p.add_argument("project")
    p.set_defaults(fn=cmd_thumbnail)
    p = sub.add_parser("stats", help="số liệu YouTube Studio → rút kinh nghiệm cho video sau")
    ps = p.add_subparsers(dest="stats_cmd", required=True)
    q = ps.add_parser("import")
    q.add_argument("csv", help="file 'Table data.csv' xuất từ YouTube Studio → Analytics → Advanced mode")
    q.add_argument("--brand", default="h2dev")
    q.set_defaults(fn=cmd_stats)
    q = ps.add_parser("show")
    q.add_argument("--brand", default="h2dev")
    q.set_defaults(fn=cmd_stats)
    p = sub.add_parser("photo", help="tìm/tải ảnh thực tế có giấy phép tự do (Openverse)")
    ps = p.add_subparsers(dest="photo_cmd", required=True)
    q = ps.add_parser("search")
    q.add_argument("query")
    q.add_argument("--n", type=int, default=12)
    q.add_argument("--allow-sa", action="store_true", help="cho phép cả CC BY-SA")
    q.set_defaults(fn=cmd_photo)
    g = ps.add_parser("get")
    g.add_argument("project")
    g.add_argument("idx", type=int, help="số thứ tự trong lần search gần nhất")
    g.add_argument("--name", required=True)
    g.set_defaults(fn=cmd_photo)
    from core.assets_cli import add_parser as add_asset_parser
    add_asset_parser(sub, BASE_DIR)
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
