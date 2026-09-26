"""Facebook Page: cấp quyền (Facebook Login trên máy), đăng video dài + Reels, theo dõi trạng thái.

  make_video.py fb auth [--brand kttg]                đổi token từ Graph API Explorer (secrets/facebook_user_token.txt) → token Page
  make_video.py fb pages [--brand kttg]               liệt kê Page đã cấp quyền, Page đang dùng
  make_video.py fb use "<tên hoặc id Page>"           chọn Page để đăng (khi tài khoản quản lý nhiều Page)
  make_video.py fb upload <slug> [--target long|reels|<id bản dọc>|all] [--publish] [--dry-run] [--again]
  make_video.py fb status <slug>

Quy tắc an toàn:
- Mặc định KHÔNG công khai: video dài đăng dạng unpublished (chỉ thấy trong Meta Business Suite → Nội dung),
  Reels lưu dạng bản nháp (DRAFT). Công khai (--publish) chỉ khi projects/<slug>/review.json "approved": true.
- Không đăng lại mục đã có trong publish/posted.json (trừ khi --again).
- App id/secret + token lưu ở h2dev_pipeline/secrets/ (đã gitignore). Không in token ra màn hình.
"""
import datetime as _dt
import json
import os
import time

from .youtube import VN_TZ, is_approved, load_posted, save_posted, secrets_dir

GRAPH_VERSION = "v26.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
GRAPH_VIDEO = f"https://graph-video.facebook.com/{GRAPH_VERSION}"
RUPLOAD = f"https://rupload.facebook.com/video-upload/{GRAPH_VERSION}"
SCOPES = ["pages_show_list", "pages_read_engagement", "pages_manage_posts", "read_insights"]


class FBError(Exception):
    pass


# ---------------- tiện ích HTTP ----------------
def _req(method, url, **kw):
    import requests
    kw.setdefault("timeout", 120)
    for attempt in range(4):
        try:
            r = requests.request(method, url, **kw)
        except requests.RequestException as e:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise FBError(f"Lỗi mạng khi gọi Facebook: {e.__class__.__name__}")
        if r.status_code >= 500 and attempt < 3:
            time.sleep(2 ** (attempt + 1))
            continue
        try:
            data = r.json()
        except ValueError:
            data = {"raw": r.text[:300]}
        if r.status_code >= 400 or (isinstance(data, dict) and "error" in data):
            err = data.get("error", {}) if isinstance(data, dict) else {}
            code = err.get("code")
            hint = {190: "Token hết hạn hoặc bị thu hồi — chạy lại: fb auth",
                    200: "Thiếu quyền — chạy lại fb auth và chọn đủ quyền cho Page",
                    10: "App chưa được cấp quyền này — kiểm tra quyền trong App Dashboard",
                    368: "Facebook tạm chặn hành động (spam/giới hạn) — thử lại sau"}.get(code, "")
            raise FBError(f"Facebook API lỗi {r.status_code} (code {code}): {err.get('message', data)} {hint}".strip())
        return data
    raise FBError("Facebook API không phản hồi")


# ---------------- xác thực ----------------
def _paths(base_dir, brand):
    d = secrets_dir(base_dir)
    return os.path.join(d, "facebook_app.json"), os.path.join(d, f"facebook_token_{brand}.json")


def _app(base_dir, brand):
    app_p, _ = _paths(base_dir, brand)
    if not os.path.exists(app_p):
        raise FBError(f"Chưa có {app_p}\n→ Tạo file JSON: {{\"app_id\": \"...\", \"app_secret\": \"...\"}} "
                      "lấy ở Meta for Developers → App → App settings → Basic.")
    app = json.load(open(app_p, encoding="utf-8"))
    if not app.get("app_id") or not app.get("app_secret") or "DAN_" in app["app_id"] + app["app_secret"]:
        raise FBError("facebook_app.json thiếu app_id hoặc app_secret")
    return app


def auth(base_dir, brand, log=print):
    """Đổi token người dùng (lấy từ Graph API Explorer, người dùng tự dán vào secrets/facebook_user_token.txt)
    thành token dài hạn rồi lấy token Page (không hết hạn). File token ngắn hạn bị xoá sau khi đổi."""
    tok_file = os.path.join(secrets_dir(base_dir), "facebook_user_token.txt")
    if not os.path.exists(tok_file) or not open(tok_file, encoding="utf-8-sig").read().strip():
        open(tok_file, "a", encoding="utf-8").close()
        raise FBError(f"Chưa có token trong {tok_file}\n"
                      "→ Graph API Explorer (developers.facebook.com/tools/explorer): chọn app, thêm quyền "
                      + ", ".join(SCOPES) + ", bấm Generate Access Token, chọn Page, rồi dán token vào file trên và lưu.")
    user_tok = open(tok_file, encoding="utf-8-sig").read().strip()
    try:
        app = _app(base_dir, brand)
    except FBError:
        app = None  # không có App Secret: token phải là token dài hạn (đã gia hạn trong Access Token Debugger)
    if app:
        long_user = _req("GET", f"{GRAPH}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": app["app_id"], "client_secret": app["app_secret"],
            "fb_exchange_token": user_tok})["access_token"]
    else:
        info = _req("GET", f"{GRAPH}/me", params={"access_token": user_tok, "fields": "id"})
        if not info.get("id"):
            raise FBError("Token không hợp lệ")
        long_user = user_tok
        log("    (không có App Secret — dùng token đã gia hạn; token Page chỉ vĩnh viễn nếu token này là loại dài hạn)")
    os.remove(tok_file)
    pages = _req("GET", f"{GRAPH}/me/accounts", params={
        "access_token": long_user, "fields": "id,name,access_token,tasks", "limit": 100}).get("data", [])
    if not pages:
        raise FBError("Tài khoản này chưa cấp quyền cho Page nào (ở bước chọn Page, hãy tick Page của thương hiệu)")
    _, token_p = _paths(base_dir, brand)
    old = json.load(open(token_p, encoding="utf-8")) if os.path.exists(token_p) else {}
    data = {"pages": {p["id"]: {"name": p["name"], "token": p["access_token"], "tasks": p.get("tasks", [])}
                      for p in pages},
            "active": old.get("active") if old.get("active") in {p["id"] for p in pages} else
            (pages[0]["id"] if len(pages) == 1 else None),
            "user_token": long_user,
            "saved_at": _dt.datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")}
    with open(token_p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return [{"id": pid, "name": p["name"], "tasks": p["tasks"], "active": pid == data["active"]}
            for pid, p in data["pages"].items()]


def _tokens(base_dir, brand):
    _, token_p = _paths(base_dir, brand)
    if not os.path.exists(token_p):
        raise FBError(f"Chưa cấp quyền Facebook cho brand '{brand}'. Chạy: make_video.py fb auth --brand {brand}")
    return token_p, json.load(open(token_p, encoding="utf-8"))


def pages(base_dir, brand):
    _, data = _tokens(base_dir, brand)
    return [{"id": pid, "name": p["name"], "tasks": p.get("tasks", []), "active": pid == data.get("active")}
            for pid, p in data["pages"].items()]


def use(base_dir, brand, which):
    token_p, data = _tokens(base_dir, brand)
    hit = [pid for pid, p in data["pages"].items() if which in (pid, p["name"]) or which.lower() in p["name"].lower()]
    if len(hit) != 1:
        raise FBError(f"Không xác định được Page '{which}' ({len(hit)} kết quả). Xem: fb pages")
    data["active"] = hit[0]
    with open(token_p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data["pages"][hit[0]]["name"]


def active_page(base_dir, brand):
    _, data = _tokens(base_dir, brand)
    pid = data.get("active")
    if not pid:
        raise FBError("Tài khoản quản lý nhiều Page — chọn Page trước: make_video.py fb use \"<tên Page>\"")
    p = data["pages"][pid]
    return pid, p["name"], p["token"]


# ---------------- đăng ----------------
def _long_text(meta):
    """Mô tả Facebook cho video dài: bỏ khối chương (mốc thời gian chỉ có nghĩa trên YouTube)."""
    desc = meta.get("description") or ""
    out, skip = [], False
    for line in desc.splitlines():
        if line.strip() in ("Chương:", "Chapters:"):
            skip = True
            continue
        if skip:
            if not line.strip():
                skip = False
            continue
        out.append(line)
    text = "\n".join(out).strip()
    tags = " ".join(meta.get("hashtags") or [])
    if tags and tags not in text:
        text += "\n\n" + tags
    return text


def _upload_long(pid, token, files, meta, publish, log):
    """Video dài lên Page (upload một lần qua graph-video; file của pipeline < 1GB)."""
    size = os.path.getsize(files["video"]) / 1e6
    log(f"    tải lên {size:.0f} MB...")
    data = {"access_token": token, "title": (meta.get("title") or "")[:255], "description": _long_text(meta),
            "published": "true" if publish else "false"}
    fh = {"source": (os.path.basename(files["video"]), open(files["video"], "rb"), "video/mp4")}
    if files.get("thumbnail") and os.path.exists(files["thumbnail"]):
        fh["thumb"] = ("thumbnail.png", open(files["thumbnail"], "rb"), "image/png")
    try:
        r = _req("POST", f"{GRAPH_VIDEO}/{pid}/videos", data=data, files=fh, timeout=1800)
    finally:
        for v in fh.values():
            v[1].close()
    return r["id"]


def _upload_reel(pid, token, files, caption, publish, log):
    """Reels API: start → tải file lên rupload → finish (PUBLISHED hoặc DRAFT)."""
    start = _req("POST", f"{GRAPH}/{pid}/video_reels", data={"upload_phase": "start", "access_token": token})
    vid = start["video_id"]
    size = os.path.getsize(files["video"])
    with open(files["video"], "rb") as f:
        _req("POST", start.get("upload_url") or f"{RUPLOAD}/{vid}", data=f, timeout=900, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
    log(f"    tải lên {size / 1e6:.1f} MB xong, đang hoàn tất...")
    _req("POST", f"{GRAPH}/{pid}/video_reels", data={
        "upload_phase": "finish", "access_token": token, "video_id": vid,
        "video_state": "PUBLISHED" if publish else "DRAFT", "description": caption})
    return vid


def upload(base_dir, brand, project_dir, which="all", publish=False, dry_run=False, again=False, log=print):
    pub_path = os.path.join(project_dir, "publish", "publish.json")
    if not os.path.exists(pub_path):
        raise FBError("Chưa có publish/publish.json — dựng video trước (make_video.py build)")
    if publish and not is_approved(project_dir):
        raise FBError("Kịch bản chưa được đánh dấu duyệt pháp lý — chỉ được đăng dạng ẩn/bản nháp.\n"
                      f"→ Khi đã duyệt: make_video.py approve {os.path.basename(project_dir)} --by \"Tên\"")
    pub = json.load(open(pub_path, encoding="utf-8"))
    items = []
    if which in ("long", "all"):
        items.append(("long", pub["long"]["files"], pub["long"]["youtube"]))
    for s in pub.get("shorts", []):
        sid = s["files"]["id"]
        if which in (sid, "all", "reels"):
            items.append((f"reel:{sid}", s["files"], s.get("reels") or {}))
    if not items:
        raise FBError(f"Không có mục '{which}' (long, reels, all hoặc id bản dọc)")
    posted = load_posted(project_dir)
    fb = posted.setdefault("facebook", {})
    pid, pname, token = ("?", "?", None) if dry_run else active_page(base_dir, brand)
    results = []
    for key, files, meta in items:
        if key in fb and not again:
            log(f"  ↷ {key}: đã đăng rồi ({fb[key]['url']}) — bỏ qua (dùng --again để đăng lại)")
            continue
        if files.get("draft"):
            raise FBError(f"{key}: đây là bản nháp (--draft), dựng bản chính trước khi đăng")
        is_reel = key.startswith("reel:")
        state = ("công khai" if publish else ("bản nháp" if is_reel else "ẩn (unpublished)"))
        text = (meta.get("caption") or "") if is_reel else _long_text(meta)
        if is_reel and not text:
            raise FBError(f"{key}: publish.json thiếu caption Reels — kiểm tra seo.json mục reels")
        dur = files.get("duration") or 0
        if is_reel and dur and not 3 <= dur <= 90:
            raise FBError(f"{key}: Reels phải dài 3–90 giây (hiện {dur:.0f}s)")
        log(f"  → {key} [{state}] {os.path.basename(files['video'])}")
        log("    " + (text.splitlines()[0][:100] if text else "") + ("" if is_reel else f"  · tiêu đề: {meta.get('title')}"))
        if dry_run:
            results.append({"key": key, "dry_run": True})
            continue
        vid = _upload_reel(pid, token, files, text, publish, log) if is_reel else \
            _upload_long(pid, token, files, meta, publish, log)
        url = f"https://www.facebook.com/reel/{vid}" if is_reel else f"https://www.facebook.com/{pid}/videos/{vid}"
        log(f"    ✓ {url}")
        rec = {"id": vid, "url": url, "page": pname, "state": "PUBLISHED" if publish else ("DRAFT" if is_reel else "UNPUBLISHED"),
               "uploaded_at": _dt.datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M"), "brand": brand}
        fb[key] = rec
        save_posted(project_dir, posted)
        results.append({"key": key, **rec})
    return results


def status(base_dir, brand, project_dir):
    fb = load_posted(project_dir).get("facebook", {})
    if not fb:
        return []
    _, _, token = active_page(base_dir, brand)
    out = []
    for key, rec in fb.items():
        try:
            d = _req("GET", f"{GRAPH}/{rec['id']}", params={
                "access_token": token, "fields": "status,published,permalink_url,length"})
            st = d.get("status", {})
            out.append({"key": key, "url": ("https://www.facebook.com" + d["permalink_url"])
                        if str(d.get("permalink_url", "")).startswith("/") else d.get("permalink_url", rec["url"]),
                        "published": d.get("published"), "video_status": st.get("video_status"),
                        "publishing": (st.get("publishing_phase") or {}).get("status"),
                        "length": d.get("length")})
        except FBError as e:
            out.append({"key": key, "url": rec["url"], "error": str(e)[:160]})
    return out
