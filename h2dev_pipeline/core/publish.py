"""Gói đăng tải: projects/<slug>/publish/ — mọi thứ cần để đăng video lên YouTube, YouTube Shorts, TikTok và Reels
(Instagram + Facebook), kèm kiểm tra giới hạn từng nền tảng.

seo.json (mọi mục đều tuỳ chọn; mục nền tảng nào thiếu thì tự suy ra từ mục youtube):
{
  "youtube": {
    "titles": ["tiêu đề chính", "phương án 2", "phương án 3"],
    "description": "... {{chapters}} ... {{long_url}} ...",
    "tags": ["..."], "hashtags": ["#a", "#b", "#c"],
    "category": "Education", "playlist": "...", "pinned_comment": "...", "made_for_kids": false
  },
  "youtube_shorts": {"title": "...", "description": "...", "hashtags": ["..."]},
  "tiktok": {"caption": "...", "hashtags": ["..."]},
  "reels": {"caption": "...", "hashtags": ["..."]},      # dùng chung cho Instagram Reels + Facebook Reels
  "long_url": "https://youtu.be/...",                    # điền sau khi đăng video dài → chạy lại `publish`
  "thumbnail": { ...cảnh doodle... },                    # thumbnail 16:9
  "cover":     { ...cảnh doodle... }                     # ảnh giữa của cover 9:16 (mặc định: cú máy đầu của short)
}
Dạng cũ (titles/description/tags/hashtags ở gốc) vẫn đọc được như mục youtube.
"""
import io
import json
import os
import re

from PIL import Image

LIMITS = {
    "yt_title": 100, "yt_title_good": 70, "yt_desc": 5000, "yt_tags": 500, "yt_hashtags": 15,
    "tiktok_caption": 2200, "reels_caption": 2200, "reels_hashtags": 5, "short_hashtags": 5,
}
TXT = {
    "vi": {"full": "Xem bản đầy đủ", "credits": "Nguồn ảnh", "no_url": "<dán link video YouTube dài>"},
    "en": {"full": "Watch the full video", "credits": "Photo credits", "no_url": "<paste the long YouTube video link>"},
}


def load_seo(project_dir):
    p = os.path.join(project_dir, "seo.json")
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _tags_len(tags):
    """YouTube tính cả dấu phẩy phân cách và cặp ngoặc kép quanh tag có dấu cách."""
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1)


def _hash(tags):
    out = []
    for t in tags or []:
        t = t.strip()
        if t:
            out.append(t if t.startswith("#") else "#" + re.sub(r"\s+", "", t))
    return out


def _first_para(desc):
    desc = re.sub(r"\{\{\w+\}\}", "", desc or "").strip()
    return desc.split("\n\n")[0].strip()


def _clip(text, n):
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") + "…"


def _with_tags(text, hashtags):
    """Nối hashtag vào cuối nếu văn bản chưa chứa chúng."""
    missing = [h for h in hashtags if h.lower() not in text.lower()]
    return (text.rstrip() + "\n\n" + " ".join(missing)).strip() if missing else text.strip()


def resolve(project, seo, chapter_lines, credits):
    """Metadata video dài YouTube → (youtube dict, cảnh báo)."""
    lang = project.get("language", "en")
    tx = TXT.get(lang, TXT["en"])
    brand = project.get("_brand") or {}
    bpub = brand.get("publish") or {}
    warn = []
    fill = _filler(seo, tx)

    yt = dict(seo.get("youtube") or {})
    for k in ("titles", "description", "tags", "hashtags"):
        yt.setdefault(k, seo.get(k))
    titles = [t for t in (yt.get("titles") or [project["title"]]) if t]
    hashtags = _hash(yt.get("hashtags") or bpub.get("default_hashtags"))
    desc = yt.get("description") or ""
    chap = "\n".join(chapter_lines)
    desc = desc.replace("{{chapters}}", chap) if "{{chapters}}" in desc else \
        (desc.rstrip() + ("\n\n" + chap if chap else ""))
    if credits:
        desc = desc.rstrip() + f"\n\n{tx['credits']}:\n" + "\n".join(f"- {c}" for c in credits)
    desc = _with_tags(fill(desc), hashtags[:LIMITS["yt_hashtags"]])
    tags = [t.strip() for t in (yt.get("tags") or []) if t.strip()]
    youtube = {
        "title": titles[0], "alt_titles": titles[1:], "description": desc, "tags": tags, "hashtags": hashtags,
        "category": yt.get("category") or bpub.get("youtube_category") or "Education",
        "playlist": yt.get("playlist") or bpub.get("playlist") or "",
        "pinned_comment": fill(yt.get("pinned_comment") or bpub.get("pinned_comment") or ""),
        "made_for_kids": bool(yt.get("made_for_kids", bpub.get("made_for_kids", False))),
        "language": lang, "_lead": _first_para(yt.get("description") or "") or titles[0],
    }
    for t in titles:
        if len(t) > LIMITS["yt_title"]:
            warn.append(f"YouTube: tiêu đề {len(t)} ký tự > {LIMITS['yt_title']} (bị từ chối): {t}")
        elif len(t) > LIMITS["yt_title_good"]:
            warn.append(f"YouTube: tiêu đề {len(t)} ký tự — trên điện thoại chỉ hiện ~{LIMITS['yt_title_good']}: {t}")
    if len(desc) > LIMITS["yt_desc"]:
        warn.append(f"YouTube: mô tả {len(desc)} ký tự > {LIMITS['yt_desc']}")
    if re.search(r"[<>]", titles[0] + desc.replace(tx["no_url"], "")):
        warn.append("YouTube: tiêu đề/mô tả chứa ký tự < hoặc > (YouTube không cho phép)")
    if _tags_len(tags) > LIMITS["yt_tags"]:
        warn.append(f"YouTube: tags dài {_tags_len(tags)} ký tự > {LIMITS['yt_tags']} — bớt tag cuối danh sách")
    if not tags:
        warn.append("YouTube: chưa có tags")
    if len(hashtags) > LIMITS["yt_hashtags"]:
        warn.append(f"YouTube: {len(hashtags)} hashtag > {LIMITS['yt_hashtags']} — YouTube bỏ qua toàn bộ hashtag")
    if len(chapter_lines) and len(chapter_lines) < 3:
        warn.append("YouTube: cần ≥ 3 chapters (mỗi cái ≥ 10s) thì mới hiện chapter")
    return youtube, warn


def _filler(seo, tx):
    long_url = seo.get("long_url") or tx["no_url"]
    return lambda s: (s or "").replace("{{long_url}}", long_url)


def resolve_short(project, seo, youtube, info):
    """Metadata một bản dọc → ({youtube_shorts, tiktok, reels}, cảnh báo).
    Bản đầu (id main / đầu danh sách) đọc các mục gốc youtube_shorts/tiktok/reels; bản khác đọc seo.shorts[id]."""
    lang = project.get("language", "en")
    tx = TXT.get(lang, TXT["en"])
    fill = _filler(seo, tx)
    first = info.get("folder", "short") == "short"
    src = seo if first else ((seo.get("shorts") or {}).get(info["id"]) or {})
    tag = "" if first else f" [{info['id']}]"
    warn = []
    hook = (info.get("hook") or "").replace("*", "")
    hashtags = youtube["hashtags"]
    lead = youtube["_lead"] if first else hook

    ys = src.get("youtube_shorts") or {}
    s_tags = _hash(ys.get("hashtags")) or (hashtags[:3] + ["#shorts"])
    s_title = ys.get("title") or _clip(hook or youtube["title"], 90)
    s_desc = ys.get("description") or f"{_clip(lead, 300)}\n\n{tx['full']}: {{{{long_url}}}}"
    shorts = {"title": s_title, "description": _with_tags(fill(s_desc), s_tags), "hashtags": s_tags}
    if len(s_title) > LIMITS["yt_title"]:
        warn.append(f"Shorts{tag}: tiêu đề {len(s_title)} ký tự > {LIMITS['yt_title']}")
    if len(s_tags) > LIMITS["short_hashtags"]:
        warn.append(f"Shorts{tag}: {len(s_tags)} hashtag — nên 3–5")

    tk = src.get("tiktok") or {}
    t_tags = _hash(tk.get("hashtags")) or hashtags[:5]
    t_cap = _with_tags(fill(tk.get("caption") or _clip(lead, 150)), t_tags)
    tiktok = {"caption": t_cap, "hashtags": t_tags}
    if len(t_cap) > LIMITS["tiktok_caption"]:
        warn.append(f"TikTok{tag}: caption {len(t_cap)} ký tự > {LIMITS['tiktok_caption']}")
    if not 3 <= len(t_tags) <= 6:
        warn.append(f"TikTok{tag}: {len(t_tags)} hashtag — nên 3–6 (từ khoá chính + ngách)")

    rl = src.get("reels") or src.get("facebook_reels") or src.get("instagram_reels") or {}
    r_tags = _hash(rl.get("hashtags")) or hashtags[:LIMITS["reels_hashtags"]]
    r_cap = _with_tags(fill(rl.get("caption") or _clip(lead, 200)), r_tags)
    reels = {"caption": r_cap, "hashtags": r_tags}
    if len(r_cap) > LIMITS["reels_caption"]:
        warn.append(f"Reels{tag}: caption {len(r_cap)} ký tự > {LIMITS['reels_caption']}")
    if len(r_tags) > LIMITS["reels_hashtags"]:
        warn.append(f"Reels{tag}: {len(r_tags)} hashtag — Instagram giới hạn {LIMITS['reels_hashtags']} hashtag mỗi bài")
    if len(r_cap.split("\n")[0]) > 125:
        warn.append(f"Reels{tag}: dòng đầu caption > 125 ký tự — phần sau bị ẩn sau 'Xem thêm'; đưa ý chính lên đầu")
    d = info.get("duration", 0)
    if d > 180:
        warn.append(f"Bản dọc{tag} {d:.0f}s > 3 phút — quá giới hạn Shorts/Reels")
    elif d > 90:
        warn.append(f"Bản dọc{tag} {d:.0f}s > 90s — Facebook Reels có thể không nhận là Reel; nên ≤ 60s")
    return {"youtube_shorts": shorts, "tiktok": tiktok, "reels": reels}, warn


# ---------------- ảnh ----------------
def render_scene_img(spec):
    from doodle.scene import scene_svg, render_png
    return Image.open(io.BytesIO(render_png(scene_svg(spec)))).convert("RGB")


def write_thumbnail(project, seo, out_path, log=print):
    from doodle.scene import scene_svg, render_png
    from .project import final_state, scene_seed
    spec = (seo.get("youtube") or {}).get("thumbnail") or seo.get("thumbnail")
    img = None
    if spec:
        try:
            img = render_scene_img(spec)
        except Exception as e:  # thumbnail lỗi không được làm hỏng cả bản build
            log(f"  [⚠] seo.json → thumbnail lỗi ({e}) — dùng cảnh đầu tiên thay thế")
    if img is None:
        spec, visible = final_state(project["scenes"][0])
        img = Image.open(io.BytesIO(render_png(scene_svg(spec, None, visible, scene_seed(project["scenes"][0])))))
    img.convert("RGB").resize((1280, 720), Image.LANCZOS).save(out_path)
    return out_path


def write_cover(project, seo, plan, s_shots, segs, out_path, log=print):
    """Cover 9:16 (1080x1920) cho Shorts/TikTok/Reels: cùng bố cục bản dọc; ô nội dung = seo.cover (hoặc
    seo.shorts[id].cover) vẽ theo ô, mặc định là cú máy đầu tiên của bản dọc."""
    from .vertical import Layout, VW, VH
    from .build import FrameMaker
    from doodle.scene import scene_svg, render_png
    from doodle.theme import T
    lay = Layout(project, plan, (VW, VH), None, segs)
    spec = ((seo.get("shorts") or {}).get(plan["id"]) or {}).get("cover") if plan["folder"] != "short" else None
    spec = spec or (seo.get("cover") if plan["folder"] == "short" else None)
    media = None
    if spec:
        try:
            media = Image.open(io.BytesIO(render_png(scene_svg(spec, size=lay.media_native)))).convert("RGB")
        except Exception as e:
            log(f"  [⚠] seo.json → cover lỗi ({e}) — dùng cú máy đầu của bản dọc")
    if media is None:  # toàn cảnh của cú máy đầu (bỏ cận cảnh để thấy đủ nhân vật)
        first = [dict(s_shots[0][0], view=None, reveal=False)] + s_shots[0][1:]
        fm = FrameMaker(segs, [first] + s_shots[1:], lay.frame_size, paper=T["paper"])
        media = fm.frame(0, segs[0]["lines"][0]["start"] + 0.01)
    lay.cover(media, segs[0].get("kicker")).save(out_path)
    return out_path


# ---------------- ghi file ----------------
def _fmt_dur(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


def _yt_txt(y):
    out = ["=== YOUTUBE (video dài 16:9) ===", "", "--- TIÊU ĐỀ ---", y["title"]]
    if y["alt_titles"]:
        out += ["", "(phương án khác — dùng cho A/B test 'Test & compare')"] + [f"- {t}" for t in y["alt_titles"]]
    out += ["", "--- MÔ TẢ ---", y["description"], "", "--- TAGS (dán vào ô Tags) ---", ", ".join(y["tags"]),
            "", "--- HASHTAGS ---", " ".join(y["hashtags"]), "", "--- CÀI ĐẶT ---",
            f"Danh mục: {y['category']}", f"Dành cho trẻ em: {'Có' if y['made_for_kids'] else 'Không'}",
            f"Ngôn ngữ video + phụ đề: {y['language']}"]
    if y["playlist"]:
        out.append(f"Danh sách phát: {y['playlist']}")
    if y["pinned_comment"]:
        out += ["", "--- BÌNH LUẬN GHIM ---", y["pinned_comment"]]
    return "\n".join(out) + "\n"


def write_all(project, project_dir, pub_dir, long_info, shorts_info, chapter_lines, log=print):
    """Ghi metadata các nền tảng + PUBLISH.md + publish.json. long_info: dict đường dẫn + thời lượng (hoặc None);
    shorts_info: list dict cho từng bản dọc (id, folder, video, cover, srt, duration, hook)."""
    from doodle import scene as ds
    from .photos import used_credits
    seo = load_seo(project_dir)
    if not seo:
        log("  [i] chưa có seo.json — metadata chỉ gồm tiêu đề + chapters")
    credits = used_credits(project, ds.PHOTO_DIRS)
    y, warn = resolve(project, seo, chapter_lines, credits)
    os.makedirs(os.path.join(pub_dir, "youtube"), exist_ok=True)
    with open(os.path.join(pub_dir, "youtube", "metadata.txt"), "w", encoding="utf-8") as f:
        f.write(_yt_txt(y))
    shorts_meta = []
    for info in shorts_info or []:
        m, w = resolve_short(project, seo, y, info)
        warn += w
        folder = os.path.join(pub_dir, info.get("folder", "short"))
        os.makedirs(folder, exist_ok=True)
        s_, t, r = m["youtube_shorts"], m["tiktok"], m["reels"]
        with open(os.path.join(folder, "youtube_shorts.txt"), "w", encoding="utf-8") as f:
            f.write(f"=== YOUTUBE SHORTS ===\n\n--- TIÊU ĐỀ ---\n{s_['title']}\n\n--- MÔ TẢ ---\n{s_['description']}\n")
        with open(os.path.join(folder, "tiktok.txt"), "w", encoding="utf-8") as f:
            f.write(f"=== TIKTOK ===\n\n--- CAPTION ---\n{t['caption']}\n")
        with open(os.path.join(folder, "reels.txt"), "w", encoding="utf-8") as f:
            f.write(f"=== REELS (Instagram + Facebook) ===\n\n--- CAPTION ---\n{r['caption']}\n")
        shorts_meta.append((info, m))
    if any(TXT[k]["no_url"] in json.dumps([m for _, m in shorts_meta] + [y], ensure_ascii=False) for k in TXT):
        warn.append("Chưa có long_url trong seo.json — sau khi đăng video dài, điền link rồi chạy `publish` để cập nhật")
    yy = {k: v for k, v in y.items() if not k.startswith("_")}
    with open(os.path.join(pub_dir, "publish.json"), "w", encoding="utf-8") as f:
        json.dump({"title": project["title"], "long": {"files": long_info, "youtube": yy},
                   "shorts": [{"files": i, **m} for i, m in shorts_meta], "warnings": warn}, f,
                  ensure_ascii=False, indent=1)
    with open(os.path.join(pub_dir, "PUBLISH.md"), "w", encoding="utf-8") as f:
        f.write(_publish_md(project, yy, shorts_meta, warn, pub_dir, long_info))
    for w in warn:
        log(f"  [⚠] {w}")
    return seo, y, warn


def _rel(pub_dir, p):
    return os.path.relpath(p, pub_dir).replace("\\", "/") if p else "—"


def _publish_md(project, y, shorts_meta, warn, pub_dir, long_info):
    brand = project.get("_brand") or {}
    legal = (brand.get("content_dna") or {}).get("legal_rules")
    L = [f"# Gói đăng tải — {project['title']}", ""]
    L += ["| | Video | Ảnh bìa | Phụ đề | Thời lượng |", "|---|---|---|---|---|"]
    if long_info:
        L.append(f"| YouTube (16:9) | `{_rel(pub_dir, long_info['video'])}` | `{_rel(pub_dir, long_info['thumbnail'])}` "
                 f"| `{_rel(pub_dir, long_info['srt'])}` | {_fmt_dur(long_info['duration'])} |")
    for info, _ in shorts_meta:
        name = "Bản dọc" + ("" if info.get("folder", "short") == "short" else f" `{info['id']}`")
        L.append(f"| {name} · Shorts/TikTok/Reels (9:16) | `{_rel(pub_dir, info['video'])}` "
                 f"| `{_rel(pub_dir, info['cover'])}` | `{_rel(pub_dir, info['srt'])}` | {_fmt_dur(info['duration'])} |")
    L.append("")
    if warn:
        L += ["## ⚠ Cần xem lại", ""] + [f"- {w}" for w in warn] + [""]

    L += ["## 1. YouTube — video dài", "", "**Tiêu đề**", "", "```text", y["title"], "```"]
    if y["alt_titles"]:
        L += ["", "Phương án khác (A/B test bằng *Test & compare* trong YouTube Studio):", ""]
        L += [f"- {x}" for x in y["alt_titles"]]
    L += ["", "**Mô tả**", "", "```text", y["description"], "```", "",
          f"**Tags** ({len(y['tags'])} tag, {_tags_len(y['tags'])}/500 ký tự)", "", "```text", ", ".join(y["tags"]), "```",
          "", f"- Danh mục: **{y['category']}** · Dành cho trẻ em: **{'Có' if y['made_for_kids'] else 'Không'}** "
          f"· Ngôn ngữ: **{y['language']}**"]
    if y["playlist"]:
        L.append(f"- Danh sách phát: **{y['playlist']}**")
    if y["pinned_comment"]:
        L += ["", "**Bình luận ghim** (đăng ngay sau khi video lên sóng rồi ghim):", "", "```text", y["pinned_comment"],
              "```"]
    for n, (info, m) in enumerate(shorts_meta, 2):
        s_, t, r = m["youtube_shorts"], m["tiktok"], m["reels"]
        name = "" if info.get("folder", "short") == "short" else f" `{info['id']}`"
        L += ["", f"## {n}. Bản dọc{name} — `{info.get('folder', 'short')}/`", "",
              "**YouTube Shorts — tiêu đề**", "", "```text", s_["title"], "```", "", "**YouTube Shorts — mô tả**", "",
              "```text", s_["description"], "```", "", "**TikTok — caption**", "", "```text", t["caption"], "```", "",
              "**Reels (Instagram + Facebook) — caption**", "", "```text", r["caption"], "```"]
    L += ["", "## Checklist trước khi bấm đăng", ""]
    if legal:
        L.append("- [ ] Người có chứng chỉ đã duyệt nội dung (quy tắc thương hiệu: đối chiếu số liệu, văn bản pháp lý)")
    L += ["- [ ] Đã xem hết video dài và các bản dọc: hình, chữ, phụ đề, âm lượng nhạc nền",
          "- [ ] **YouTube:** tải video · dán tiêu đề, mô tả, tags · chọn thumbnail · danh mục · 'Không dành cho trẻ em' "
          "· *Phụ đề → Tải tệp lên* (file .srt, có thời gian) · thêm vào danh sách phát · màn hình kết thúc + thẻ",
          "- [ ] **YouTube:** mục *Nội dung bị thay đổi/tổng hợp*: chọn **Không** (hoạt hình doodle, giọng đọc "
          "tổng hợp không giả danh người thật) — đổi thành Có nếu có cảnh/giọng giống người thật",
          "- [ ] **Shorts:** tải bản dọc · tiêu đề + mô tả · *Video liên quan* → chọn video dài",
          "- [ ] **TikTok:** tải bản dọc · dán caption · *Chỉnh sửa ảnh bìa → Tải lên* `cover.png` của bản đó "
          "· bật nhãn **Nội dung do AI tạo** (giọng đọc AI) · cho phép Duet/Stitch tuỳ ý",
          "- [ ] **Reels:** tải bản dọc lên Instagram (bật *Chia sẻ lên Facebook* hoặc đăng riêng trên Trang) "
          "· ảnh bìa `cover.png` · dán caption · bật nhãn **AI info** nếu nền tảng yêu cầu",
          "- [ ] Nhiều bản dọc: đăng cách nhau 1–2 ngày (không đăng dồn một lúc)",
          "- [ ] Sau khi đăng video dài: điền `long_url` trong seo.json → chạy `make_video.py publish <slug>` → "
          "copy lại mô tả Shorts/TikTok/Reels có link",
          ""]
    L += ["Chép nhanh từng phần: `youtube/metadata.txt`, `<thư mục bản dọc>/youtube_shorts.txt`, `tiktok.txt`, "
          "`reels.txt` · dữ liệu máy đọc: `publish.json`.", ""]
    return "\n".join(L)
