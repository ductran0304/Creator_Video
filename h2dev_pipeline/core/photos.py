"""Ảnh thực tế có giấy phép tự do (Openverse — gồm Flickr, Wikimedia Commons...).

  photo search "<từ khoá>" [--n 12] [--allow-sa]   → bảng xem trước có đánh số: cache/photo_search/last.png
  photo get <project> <số> --name <tên>             → projects/<slug>/photos/<tên>.jpg + <tên>.json (tác giả, giấy phép)

Chỉ lấy giấy phép cho phép dùng thương mại: CC0, public domain (pdm), CC BY — (CC BY-SA nếu --allow-sa).
Nguồn ảnh được ghi trên hình (dòng nhỏ) và tự thêm vào mô tả YouTube khi build.
"""
import io
import json
import math
import os
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont

API = "https://api.openverse.org/v1/images/"
UA = {"User-Agent": "h2dev-doodle-pipeline/1.0 (educational video tool)"}
LICENSE_NAMES = {"cc0": "CC0", "pdm": "Public Domain", "by": "CC BY", "by-sa": "CC BY-SA"}


def _get(url, timeout=40):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def search(base_dir, query, n=12, allow_sa=False):
    lic = "cc0,pdm,by" + (",by-sa" if allow_sa else "")
    q = urllib.parse.urlencode({"q": query, "license": lic, "page_size": n, "mature": "false"})
    data = json.loads(_get(f"{API}?{q}"))
    results = [r for r in data.get("results", []) if r.get("url")]
    out_dir = os.path.join(base_dir, "cache", "photo_search")
    os.makedirs(out_dir, exist_ok=True)
    keep = ["id", "title", "creator", "creator_url", "license", "license_version", "license_url", "source",
            "foreign_landing_url", "url", "thumbnail", "width", "height"]
    results = [{k: r.get(k) for k in keep} for r in results]
    with open(os.path.join(out_dir, "last.json"), "w", encoding="utf-8") as f:
        json.dump({"query": query, "results": results}, f, ensure_ascii=False, indent=1)
    # bảng xem trước: tải thumbnail nhỏ, đánh số
    from doodle.text import FONT_PATH
    font = ImageFont.truetype(FONT_PATH, 26)
    cell = (360, 240)
    cols = 4
    rows = max(1, math.ceil(len(results) / cols))
    sheet = Image.new("RGB", (cols * (cell[0] + 8) + 8, rows * (cell[1] + 44) + 8), "white")
    for i, r in enumerate(results):
        x, y = 8 + (i % cols) * (cell[0] + 8), 8 + (i // cols) * (cell[1] + 44)
        try:
            im = Image.open(io.BytesIO(_get(r.get("thumbnail") or r["url"], 20))).convert("RGB")
            im.thumbnail(cell)
            sheet.paste(im, (x + (cell[0] - im.width) // 2, y + (cell[1] - im.height) // 2))
        except Exception:  # noqa: BLE001 — thumbnail lỗi thì để ô trống
            pass
        d = ImageDraw.Draw(sheet)
        d.rectangle([x, y, x + 44, y + 36], fill="#101A3D")
        d.text((x + 8, y + 2), str(i + 1), font=font, fill="white")
        d.text((x, y + cell[1] + 6), f"{LICENSE_NAMES.get(r['license'], r['license'])} · {r.get('source', '')}"
               f" · {r.get('width')}x{r.get('height')}", font=ImageFont.truetype(FONT_PATH, 20), fill="#333")
    p = os.path.join(out_dir, "last.png")
    sheet.save(p)
    return results, p


def get(base_dir, project_dir, idx, name, max_w=1920):
    with open(os.path.join(base_dir, "cache", "photo_search", "last.json"), "r", encoding="utf-8") as f:
        last = json.load(f)
    r = last["results"][idx - 1]
    im = Image.open(io.BytesIO(_get(r["url"], 60))).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)), Image.LANCZOS)
    out_dir = os.path.join(project_dir, "photos")
    os.makedirs(out_dir, exist_ok=True)
    jpg = os.path.join(out_dir, f"{name}.jpg")
    im.save(jpg, quality=90)
    meta = {**r, "query": last["query"], "saved_size": [im.width, im.height]}
    with open(os.path.join(out_dir, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return jpg, meta


def credit_line(meta, short=False):
    lic = LICENSE_NAMES.get(meta.get("license"), meta.get("license", ""))
    ver = meta.get("license_version") or ""
    lic_full = f"{lic} {ver}".strip() if meta.get("license") in ("by", "by-sa") else lic
    who = meta.get("creator") or "không rõ tác giả"
    if short:
        return f"Ảnh: {who} ({lic_full})"
    return f"\"{meta.get('title') or 'ảnh'}\" — {who}, {lic_full}, {meta.get('foreign_landing_url') or meta.get('url')}"


def used_credits(project, photo_dirs):
    """Danh sách ghi nguồn cho mọi ảnh dùng trong project (theo thứ tự xuất hiện, không trùng)."""
    srcs = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "photo" or o.get("frame") == "photo":
                if o.get("src") and o["src"] not in srcs:
                    srcs.append(o["src"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(project.get("scenes", []))
    lines = []
    for s in srcs:
        base = os.path.splitext(os.path.basename(s))[0]
        for d in photo_dirs:
            mp = os.path.join(d, base + ".json")
            if os.path.exists(mp):
                with open(mp, "r", encoding="utf-8") as f:
                    lines.append(credit_line(json.load(f)))
                break
    return lines
