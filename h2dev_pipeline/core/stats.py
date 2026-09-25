"""Vòng phản hồi: nhập số liệu YouTube Studio → brands/<tên>/stats.json, tóm tắt video tốt/kém cho skill đọc
trước khi viết video mới.

Xuất số liệu: YouTube Studio → Analytics → Advanced mode → chọn khoảng thời gian → Export → CSV
(file "Table data.csv" trong file zip). Đọc được cả giao diện tiếng Anh lẫn tiếng Việt.
"""
import csv
import datetime
import glob
import json
import os
import re

COLS = {  # khoá chuẩn → các cụm chữ nhận diện tên cột (chữ thường)
    "id": ["content", "nội dung"],
    "title": ["video title", "tiêu đề video"],
    "published": ["publish time", "thời gian xuất bản", "ngày xuất bản"],
    "duration": ["duration", "thời lượng"],
    "views": ["views", "số lượt xem", "lượt xem"],
    "watch_hours": ["watch time", "thời gian xem"],
    "subs": ["subscribers", "người đăng ký"],
    "impressions": ["impressions", "số lượt hiển thị"],
    "ctr": ["click-through rate", "tỷ lệ nhấp"],
    "avd": ["average view duration", "thời lượng xem trung bình"],
    "apv": ["average percentage viewed", "tỷ lệ xem trung bình", "phần trăm"],
}


def _match(header):
    h = header.strip().lower()
    order = ["ctr", "apv", "avd", "watch_hours", "published", "title", "impressions", "subs", "views", "duration", "id"]
    for key in order:  # cụm dài/đặc thù trước để "thời lượng xem trung bình" không bị nhận là "thời lượng"
        if any(p in h for p in COLS[key]):
            return key
    return None


def _num(v):
    v = (v or "").strip().replace(",", "")
    if re.fullmatch(r"\d+:\d{2}(:\d{2})?", v):  # 0:01:23 → giây
        parts = [int(x) for x in v.split(":")]
        return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))
    try:
        return float(v)
    except ValueError:
        return v or None


def _stats_path(base_dir, brand):
    return os.path.join(base_dir, "brands", brand, "stats.json")


def _project_titles(base_dir):
    """tiêu đề (YouTube/Shorts) → slug project, để nối số liệu với kịch bản."""
    out = {}
    for seo_path in glob.glob(os.path.join(base_dir, "projects", "*", "seo.json")):
        slug = os.path.basename(os.path.dirname(seo_path))
        try:
            with open(seo_path, "r", encoding="utf-8") as f:
                seo = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        titles = list((seo.get("youtube") or {}).get("titles") or seo.get("titles") or [])
        titles.append((seo.get("youtube_shorts") or {}).get("title"))
        for sid, sv in (seo.get("shorts") or {}).items():
            titles.append((sv.get("youtube_shorts") or {}).get("title"))
        for t in filter(None, titles):
            out[_norm(t)] = slug
    return out


def _norm(t):
    return re.sub(r"[\W_]+", " ", (t or "").lower().replace("#shorts", "")).strip()


def import_csv(base_dir, path, brand):
    with open(path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return "[✗] File trống"
    keys = [_match(h) for h in rows[0]]
    if "title" not in keys:
        return f"[✗] Không nhận ra cột tiêu đề video — cột có trong file: {rows[0]}"
    titles = _project_titles(base_dir)
    videos = []
    for r in rows[1:]:
        rec = {k: _num(v) if k not in ("title", "id", "published") else v.strip() for k, v in zip(keys, r) if k}
        if not rec.get("title") or str(rec.get("id", "")).lower() in ("total", "tổng"):
            continue
        dur = rec.get("duration")
        rec["format"] = "short" if isinstance(dur, (int, float)) and dur <= 180 else "long"
        rec["slug"] = titles.get(_norm(rec["title"]))
        videos.append(rec)
    p = _stats_path(base_dir, brand)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"imported": datetime.date.today().isoformat(), "source": os.path.basename(path), "videos": videos},
                  f, ensure_ascii=False, indent=1)
    linked = sum(1 for v in videos if v["slug"])
    return f"[✓] {len(videos)} video ({linked} nối được với project) → {p}\n\n" + show(base_dir, brand)


def show(base_dir, brand):
    p = _stats_path(base_dir, brand)
    if not os.path.exists(p):
        return f"[i] Chưa có số liệu cho '{brand}' — xuất CSV từ YouTube Studio rồi chạy `stats import <file.csv> --brand {brand}`"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    vids = data["videos"]
    lines = [f"Số liệu '{brand}' (nhập {data['imported']}, {len(vids)} video)"]
    for fmt, label in (("long", "Video dài"), ("short", "Bản dọc (Shorts)")):
        vs = [v for v in vids if v.get("format") == fmt and isinstance(v.get("apv"), (int, float))]
        if not vs:
            continue
        vs.sort(key=lambda v: v["apv"], reverse=True)
        avg = sum(v["apv"] for v in vs) / len(vs)
        ctrs = [v["ctr"] for v in vs if isinstance(v.get("ctr"), (int, float))]
        lines += ["", f"## {label}: xem trung bình {avg:.0f}% thời lượng"
                  + (f", CTR trung bình {sum(ctrs) / len(ctrs):.1f}%" if ctrs else "")]
        lines.append("| Video | Lượt xem | % xem TB | Xem TB (s) | CTR % | Project |")
        lines.append("|---|---|---|---|---|---|")
        for v in vs:
            views = v.get("views")
            views = f"{views:,.0f}".replace(",", ".") if isinstance(views, (int, float)) else (views or "")
            lines.append(f"| {v['title'][:60]} | {views} | {v['apv']:.0f} | {v.get('avd', '')} | "
                         f"{v.get('ctr', '')} | {v.get('slug') or '—'} |")
        if len(vs) >= 2:
            best, worst = vs[0], vs[-1]
            lines += ["", f"- Giữ chân tốt nhất: **{best['title'][:60]}** ({best['apv']:.0f}%) — xem lại hook, nhịp cắt "
                      f"và định dạng của video này để lặp lại",
                      f"- Giữ chân kém nhất: **{worst['title'][:60]}** ({worst['apv']:.0f}%) — kiểm tra 5 giây đầu và "
                      "đoạn người xem bỏ đi (YouTube Studio → Giữ chân người xem)"]
    lines += ["", "Mục tiêu tham khảo: Shorts ≥ 70% qua 3 giây đầu, xem TB ≥ 60%; video dài giữ chân ≥ 40%, CTR 4–6%."]
    return "\n".join(lines)
