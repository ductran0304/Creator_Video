"""Footage thật cho kịch bản: ảnh, video B-roll, logo, trang văn bản pháp luật.

  footage search "<từ khoá>" --kind photo|video|illustration|logo [--source pexels|pixabay|openverse|wikimedia]
                  [--n 12] [--allow-sa]
      --kind illustration: tranh minh hoạ / vector Pixabay (mặc định nguồn pixabay) — hợp phong cách doodle
      → bảng xem trước có đánh số: cache/footage_search/last.png (video: 3 khung hình/clip + thời lượng)
  footage get <project> <số> --name <tên> [--shared]
      → projects/<slug>/footage/<tên>.(jpg|png|mp4) + <tên>.json (nguồn, tác giả, giấy phép)
        --shared: lưu vào thư viện dùng chung của thương hiệu brands/<brand>/footage/ (video sau dùng lại)
  footage pdf <project> <url|file.pdf> --page N --name <tên> [--find "cụm từ"]
      → ảnh trang văn bản (PNG) + toạ độ khoanh vùng cụm từ (dùng cho khung doc_page)

Giấy phép được nhận (dùng thương mại được): Pexels License, Pixabay Content License, CC0, Public Domain, CC BY
(CC BY-SA khi --allow-sa). Pexels/Pixabay: không bắt buộc ghi nguồn nhưng pipeline vẫn ghi; không bán lại nguyên
bản, không dùng người trong ảnh cho ngữ cảnh tiêu cực/ngụ ý xác nhận sản phẩm.
Không nhận: CC NC (cấm thương mại), CC ND (cấm chỉnh sửa — mình phải cắt khung).
Logo (--kind logo): nhãn hiệu của chủ sở hữu — chỉ dùng để nhắc tên trong nội dung giáo dục, không chỉnh sửa,
không ngụ ý hợp tác; mô tả video tự thêm câu miễn trừ nhãn hiệu.
Văn bản quy phạm pháp luật không thuộc đối tượng bảo hộ quyền tác giả (Luật SHTT, Điều 15).
"""
import html
import io
import json
import math
import os
import re
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont

UA = {"User-Agent": "h2dev-doodle-pipeline/1.0 (educational video tool; contact via ketoantinhgon.com)"}
LIC = {"pexels": "Pexels License", "pixabay": "Pixabay License", "cc0": "CC0", "pdm": "Public Domain", "by": "CC BY", "by-sa": "CC BY-SA",
       "legal-doc": "Văn bản quy phạm pháp luật", "trademark": "Nhãn hiệu của chủ sở hữu"}


# ---------------- tiện ích ----------------
def _env(base_dir, key):
    if os.environ.get(key):
        return os.environ[key]
    p = os.path.join(base_dir, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == key:
                return v.strip()
    return None


def _get(url, headers=None, timeout=60):
    h = dict(UA)
    h.update(headers or {})
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout).read()


def _json(url, headers=None):
    return json.loads(_get(url, headers))


def _strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


# ---------------- nguồn ----------------
def _pexels(base_dir, query, kind, n, orientation):
    key = _env(base_dir, "PEXELS_API_KEY")
    if not key:
        raise SystemExit("[✗] Chưa có PEXELS_API_KEY (đặt trong h2dev_pipeline/.env)")
    q = {"query": query, "per_page": n, "orientation": orientation or "landscape"}
    hdr = {"Authorization": key}
    out = []
    if kind == "video":
        data = _json("https://api.pexels.com/videos/search?" + urllib.parse.urlencode(q), hdr)
        for v in data.get("videos", []):
            files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")]
            if not files:
                continue
            best = min(files, key=lambda f: (abs(f["width"] - 1920), -f["width"]))
            pics = [p["picture"] for p in v.get("video_pictures", [])]
            out.append({"kind": "video", "source": "pexels", "id": v["id"], "title": query, "license": "pexels",
                        "license_url": "https://www.pexels.com/license/",
                        "creator": (v.get("user") or {}).get("name"), "creator_url": (v.get("user") or {}).get("url"),
                        "landing_url": v.get("url"), "url": best["link"], "width": best["width"],
                        "height": best["height"], "duration": v.get("duration"),
                        "thumbs": [pics[i] for i in (0, len(pics) // 2, -1)] if pics else [v.get("image")]})
    else:
        data = _json("https://api.pexels.com/v1/search?" + urllib.parse.urlencode(q), hdr)
        for p in data.get("photos", []):
            out.append({"kind": "photo", "source": "pexels", "id": p["id"], "title": p.get("alt") or query,
                        "license": "pexels", "license_url": "https://www.pexels.com/license/",
                        "creator": p.get("photographer"), "creator_url": p.get("photographer_url"),
                        "landing_url": p.get("url"), "url": p["src"].get("large2x") or p["src"]["original"],
                        "width": p.get("width"), "height": p.get("height"), "thumbs": [p["src"].get("medium")]})
    return out


def _pixabay(base_dir, query, kind, n, orientation):
    key = _env(base_dir, "PIXABAY_API_KEY")
    if not key:
        raise SystemExit("[✗] Chưa có PIXABAY_API_KEY (đặt trong h2dev_pipeline/.env)")
    q = {"key": key, "q": query[:100], "per_page": max(3, min(n, 200)), "safesearch": "true", "lang": "en"}
    lic = {"license": "pixabay", "license_url": "https://pixabay.com/service/license-summary/"}
    out = []

    def user(h):
        return {"creator": h.get("user"), "creator_url": f"https://pixabay.com/users/{h.get('user')}-{h.get('user_id')}/"}

    if kind == "video":
        data = _json("https://pixabay.com/api/videos/?" + urllib.parse.urlencode(q))
        for h in data.get("hits", []):
            vs = h.get("videos") or {}
            files = [f for f in (vs.get(k) for k in ("large", "medium", "small")) if f and f.get("url") and f.get("width")]
            if not files:
                continue
            best = min(files, key=lambda f: (abs(f["width"] - 1920), -f["width"]))
            thumbs = [f.get("thumbnail") for f in (vs.get("medium"), vs.get("small"), vs.get("tiny")) if f and f.get("thumbnail")]
            out.append({"kind": "video", "source": "pixabay", "id": h["id"], "title": h.get("tags") or query, **lic,
                        **user(h), "landing_url": h.get("pageURL"), "url": best["url"], "width": best["width"],
                        "height": best["height"], "duration": h.get("duration"), "thumbs": thumbs[:3] or [h.get("picture_id")]})
    else:
        q["image_type"] = "all" if kind == "illustration" else "photo"  # all + lọc: lấy cả illustration lẫn vector
        q["orientation"] = {"landscape": "horizontal", "portrait": "vertical"}.get(orientation, orientation or "all")
        data = _json("https://pixabay.com/api/?" + urllib.parse.urlencode(q))
        for h in data.get("hits", []):
            if kind == "illustration" and h.get("type") not in ("illustration", "vector/svg", "vector/ai", "vector"):
                continue
            out.append({"kind": "photo", "source": "pixabay", "id": h["id"], "title": h.get("tags") or query, **lic,
                        **user(h), "landing_url": h.get("pageURL"), "url": h.get("largeImageURL") or h.get("webformatURL"),
                        "width": h.get("imageWidth"), "height": h.get("imageHeight"),
                        "subtype": h.get("type"), "thumbs": [h.get("webformatURL") or h.get("previewURL")]})
    return out


def _openverse(query, n, allow_sa):
    lic = "cc0,pdm,by" + (",by-sa" if allow_sa else "")
    q = urllib.parse.urlencode({"q": query, "license": lic, "page_size": n, "mature": "false"})
    data = _json(f"https://api.openverse.org/v1/images/?{q}")
    out = []
    for r in data.get("results", []):
        if not r.get("url"):
            continue
        out.append({"kind": "photo", "source": "openverse:" + (r.get("source") or ""), "id": r.get("id"),
                    "title": r.get("title"), "license": r.get("license"), "license_version": r.get("license_version"),
                    "license_url": r.get("license_url"), "creator": r.get("creator"), "creator_url": r.get("creator_url"),
                    "landing_url": r.get("foreign_landing_url"), "url": r["url"], "width": r.get("width"),
                    "height": r.get("height"), "thumbs": [r.get("thumbnail") or r["url"]]})
    return out


def _wiki_license(meta):
    short = (meta.get("LicenseShortName", {}).get("value") or "").lower()
    if "nc" in short.split("-") or "-nc" in short or "noncommercial" in short:
        return None
    if "-nd" in short or "noderiv" in short:
        return None
    if "cc0" in short:
        return "cc0"
    if "public domain" in short or short.startswith("pd"):
        return "pdm"
    if "by-sa" in short:
        return "by-sa"
    if "cc by" in short or "cc-by" in short:
        return "by"
    return None


def _wikimedia(query, kind, n, allow_sa):
    ftype = {"video": "filetype:video", "logo": "filetype:drawing|bitmap", "photo": "filetype:bitmap"}[kind]
    srch = f"{query} logo" if kind == "logo" and "logo" not in query.lower() else query
    q = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": n * 2,
         "gsrsearch": f"{srch} {ftype}", "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 640}
    data = _json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q))
    pages = sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    out = []
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = _wiki_license(meta)
        if kind == "logo":
            lic = lic or ("pdm" if "trademark" in json.dumps(meta).lower() else None)
        if not lic or (lic == "by-sa" and not allow_sa and kind != "logo"):
            continue
        out.append({"kind": kind, "source": "wikimedia", "id": p.get("pageid"), "title": p.get("title", "").replace("File:", ""),
                    "license": lic, "license_version": _strip(meta.get("LicenseShortName", {}).get("value")),
                    "license_url": _strip(meta.get("LicenseUrl", {}).get("value")),
                    "creator": _strip(meta.get("Artist", {}).get("value"))[:80] or None,
                    "landing_url": info.get("descriptionurl"), "url": info.get("url"), "mime": info.get("mime"),
                    "width": info.get("width"), "height": info.get("height"), "duration": info.get("duration"),
                    "thumbs": [info.get("thumburl") or info.get("url")]})
        if len(out) >= n:
            break
    return out


def search(base_dir, query, kind="photo", source=None, n=12, allow_sa=False, orientation=None):
    source = source or {"logo": "wikimedia", "illustration": "pixabay"}.get(kind, "pexels")
    if kind == "illustration" and source != "pixabay":
        raise SystemExit("[✗] --kind illustration chỉ có ở --source pixabay")
    if source == "pexels":
        results = _pexels(base_dir, query, kind, n, orientation)
    elif source == "pixabay":
        results = _pixabay(base_dir, query, kind, n, orientation)
    elif source == "openverse":
        results = _openverse(query, n, allow_sa)
    elif source == "wikimedia":
        results = _wikimedia(query, kind, n, allow_sa)
    else:
        raise SystemExit(f"[✗] Nguồn '{source}' chưa hỗ trợ (pexels | pixabay | openverse | wikimedia)")
    out_dir = os.path.join(base_dir, "cache", "footage_search")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "last.json"), "w", encoding="utf-8") as f:
        json.dump({"query": query, "kind": kind, "results": results}, f, ensure_ascii=False, indent=1)
    return results, _sheet(results, os.path.join(out_dir, "last.png"))


def _sheet(results, path):
    from doodle.text import FONT_PATH
    font, small = ImageFont.truetype(FONT_PATH, 26), ImageFont.truetype(FONT_PATH, 19)
    video = any(r["kind"] == "video" for r in results)
    cw, ch = (540, 170) if video else (360, 240)
    cols = 2 if video else 4
    rows = max(1, math.ceil(len(results) / cols))
    sheet = Image.new("RGB", (cols * (cw + 8) + 8, rows * (ch + 40) + 8), "white")
    d = ImageDraw.Draw(sheet)
    for i, r in enumerate(results):
        x, y = 8 + (i % cols) * (cw + 8), 8 + (i // cols) * (ch + 40)
        thumbs = r.get("thumbs") or []
        tw = cw // max(1, len(thumbs))
        for j, t in enumerate(thumbs):
            try:
                im = Image.open(io.BytesIO(_get(t, timeout=25))).convert("RGB")
                im.thumbnail((tw - 4, ch))
                sheet.paste(im, (x + j * tw + (tw - im.width) // 2, y + (ch - im.height) // 2))
            except Exception:  # noqa: BLE001 — thumbnail lỗi thì để trống
                pass
        d.rectangle([x, y, x + 44, y + 36], fill="#101A3D")
        d.text((x + 8, y + 2), str(i + 1), font=font, fill="white")
        extra = f" · {r['duration']}s" if r.get("duration") else ""
        d.text((x, y + ch + 6), f"{LIC.get(r['license'], r['license'])} · {r['source']} · {r.get('width')}x{r.get('height')}{extra}",
               font=small, fill="#333")
    sheet.save(path)
    return path


# ---------------- tải về ----------------
def dest_dir(base_dir, project_dir, project, shared):
    if shared and project.get("brand"):
        return os.path.join(base_dir, "brands", project["brand"], "footage")
    return os.path.join(project_dir, "footage")


def get(base_dir, out_dir, idx, name):
    with open(os.path.join(base_dir, "cache", "footage_search", "last.json"), "r", encoding="utf-8") as f:
        last = json.load(f)
    r = last["results"][idx - 1]
    os.makedirs(out_dir, exist_ok=True)
    raw = _get(r["url"], timeout=180)
    if r["kind"] == "video":
        path = os.path.join(out_dir, f"{name}.mp4")
        if r["url"].lower().split("?")[0].endswith((".webm", ".ogv", ".ogg")):  # Wikimedia: đổi sang mp4
            tmp = os.path.join(out_dir, f"{name}.src")
            open(tmp, "wb").write(raw)
            from .audio import FFMPEG
            import subprocess
            subprocess.run([FFMPEG, "-v", "error", "-y", "-i", tmp, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            path], check=True)
            os.remove(tmp)
        else:
            open(path, "wb").write(raw)
    elif r["url"].lower().split("?")[0].endswith(".svg"):
        path = os.path.join(out_dir, f"{name}.svg")
        open(path, "wb").write(raw)
    else:
        im = Image.open(io.BytesIO(raw))
        has_alpha = im.mode in ("RGBA", "LA", "P") and r["kind"] == "logo"
        im = im.convert("RGBA" if has_alpha else "RGB")
        if im.width > 1920:
            im = im.resize((1920, int(im.height * 1920 / im.width)), Image.LANCZOS)
        path = os.path.join(out_dir, f"{name}.png" if has_alpha else f"{name}.jpg")
        im.save(path, **({} if has_alpha else {"quality": 90}))
    meta = {k: v for k, v in r.items() if k != "thumbs"}
    meta.update(query=last["query"])
    if r["kind"] == "logo":
        meta["trademark"] = True
        meta["owner"] = last["query"].replace(" logo", "").strip()
    with open(os.path.join(out_dir, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return path, meta


def pdf_page(out_dir, src, page, name, find=None, title=None):
    """Trang văn bản PDF → PNG (2x) + toạ độ khoanh vùng cụm từ `find` (tỉ lệ 0..1 của trang)."""
    import pypdfium2 as pdfium
    os.makedirs(out_dir, exist_ok=True)
    if re.match(r"https?://", src):
        data = _get(src, timeout=180)
        pdf_path = os.path.join(out_dir, f"{name}.pdf")
        open(pdf_path, "wb").write(data)
    else:
        pdf_path = src
    doc = pdfium.PdfDocument(pdf_path)
    pg = doc[page - 1]
    pw, ph = pg.get_size()
    img = pg.render(scale=2.2).to_pil().convert("RGB")
    png = os.path.join(out_dir, f"{name}.png")
    img.save(png)
    boxes = []
    if find:
        tp = pg.get_textpage()
        searcher = tp.search(find, match_case=False)
        while True:
            m = searcher.get_next()
            if not m:
                break
            start, count = m
            rects = [tp.get_charbox(i) for i in range(start, start + count)]
            l, b = min(r[0] for r in rects), min(r[1] for r in rects)
            r_, t = max(r[2] for r in rects), max(r[3] for r in rects)
            boxes.append([round(l / pw, 4), round(1 - t / ph, 4), round((r_ - l) / pw, 4), round((t - b) / ph, 4)])
    meta = {"kind": "doc", "source": src if re.match(r"https?://", src) else os.path.basename(src), "page": page,
            "license": "legal-doc", "title": title or name, "landing_url": src if re.match(r"https?://", src) else None,
            "found": boxes}
    with open(os.path.join(out_dir, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    if os.path.dirname(pdf_path) == out_dir and pdf_path.endswith(".pdf") and re.match(r"https?://", src):
        os.remove(pdf_path)  # chỉ giữ ảnh trang đã dùng
    return png, meta


# ---------------- ghi nguồn ----------------
def credit_line(meta):
    lic = meta.get("license")
    who = meta.get("creator") or "không rõ tác giả"
    if lic in ("pexels", "pixabay"):
        kind = "Video" if meta.get("kind") == "video" else ("Hình minh hoạ" if "vector" in str(meta.get("subtype"))
                                                             or meta.get("subtype") == "illustration" else "Ảnh")
        return f"{kind}: {who} / {'Pexels' if lic == 'pexels' else 'Pixabay'} ({meta.get('landing_url')})"
    if lic == "legal-doc":
        return f"Trích văn bản: {meta.get('title')} ({meta.get('landing_url') or meta.get('source')})"
    name = LIC.get(lic, lic or "")
    if lic in ("by", "by-sa") and meta.get("license_version"):
        name = meta["license_version"] if "cc" in meta["license_version"].lower() else f"{name} {meta['license_version']}"
    return f"\"{meta.get('title') or 'tư liệu'}\" — {who}, {name}, {meta.get('landing_url') or meta.get('url')}"


def short_credit(meta):
    lic = meta.get("license")
    who = meta.get("creator") or "không rõ"
    if lic in ("pexels", "pixabay"):
        return f"{who} / {'Pexels' if lic == 'pexels' else 'Pixabay'}"
    if lic == "legal-doc":
        return "Nguồn: văn bản gốc"
    return f"{who} ({LIC.get(lic, lic or '')})"


def find_meta(src, dirs):
    base = os.path.splitext(os.path.basename(src))[0]
    for d in dirs:
        mp = os.path.join(d, base + ".json")
        if os.path.exists(mp):
            with open(mp, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def used(project, dirs):
    """(dòng ghi nguồn[], chủ sở hữu nhãn hiệu[]) cho mọi footage dùng trong project + các bản dọc."""
    srcs = []

    def add(s):
        if s and s not in srcs:
            srcs.append(s)

    def walk(o):
        if isinstance(o, dict):
            if o.get("type") in ("photo", "logo") or o.get("frame") in ("photo", "video", "doc_page", "media_card"):
                add(o.get("src"))
            if o.get("frame") == "logo_row":
                for lg in o.get("logos", []):
                    add(lg.get("src"))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(project.get("scenes", []))
    walk(project.get("shorts", []))
    credits, marks = [], []
    for s in srcs:
        m = find_meta(s, dirs)
        if not m:
            continue
        if m.get("trademark") or m.get("kind") == "logo":
            marks.append(m.get("owner") or m.get("title") or s)
        else:
            credits.append(credit_line(m) if m.get("kind") in ("video", "doc") or m.get("license") in ("pexels", "pixabay")
                           or m.get("source", "").startswith(("wikimedia", "openverse")) else _legacy(m))
    return credits, marks


def _legacy(meta):
    from .photos import credit_line as photo_credit
    return photo_credit(meta)
