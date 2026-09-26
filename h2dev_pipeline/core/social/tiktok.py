"""TikTok: cấp quyền (Login Kit for Desktop, PKCE), đẩy bản dọc vào hộp thư nháp hoặc đăng thẳng, theo dõi trạng thái.

  make_video.py tt auth [--brand kttg]                 mở trình duyệt để chủ tài khoản TikTok bấm "Cho phép" (một lần)
  make_video.py tt whoami [--brand kttg]
  make_video.py tt upload <slug> [--target all|<id bản dọc>] [--direct [--public]] [--dry-run] [--again]
  make_video.py tt status <slug>

Chế độ:
- Mặc định: đẩy video vào HỘP THƯ NHÁP (inbox) của TikTok — chủ tài khoản nhận thông báo trong app, dán caption
  (CLI in sẵn) rồi tự bấm đăng. Không cần app qua kiểm duyệt.
- --direct: đăng thẳng (Direct Post). App chưa qua kiểm duyệt của TikTok chỉ được đăng ở chế độ riêng tư (SELF_ONLY).
  --public chỉ khi projects/<slug>/review.json "approved": true và app đã được TikTok duyệt.
- Client key/secret + token lưu ở h2dev_pipeline/secrets/ (đã gitignore). Không in token ra màn hình.
"""
import base64
import datetime as _dt
import hashlib
import http.server
import json
import math
import os
import secrets as _secrets
import threading
import time
import urllib.parse
import webbrowser

from .youtube import VN_TZ, is_approved, load_posted, save_posted, secrets_dir

API = "https://open.tiktokapis.com/v2"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = ["user.info.basic", "video.upload", "video.publish"]
REDIRECT_PORT = 8767
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback/"
CHUNK = 10 * 1024 * 1024


class TTError(Exception):
    pass


def _req(method, url, token=None, **kw):
    import requests
    kw.setdefault("timeout", 120)
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(4):
        try:
            r = requests.request(method, url, headers=headers, **kw)
        except requests.RequestException as e:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise TTError(f"Lỗi mạng khi gọi TikTok: {e.__class__.__name__}")
        if r.status_code >= 500 and attempt < 3:
            time.sleep(2 ** (attempt + 1))
            continue
        try:
            data = r.json()
        except ValueError:
            data = {}
        err = data.get("error") if isinstance(data, dict) else None
        if r.status_code >= 400 or (isinstance(err, dict) and err.get("code") not in (None, "ok")) or \
                (isinstance(err, str) and err):
            code = err.get("code") if isinstance(err, dict) else err
            msg = (err.get("message") if isinstance(err, dict) else data.get("error_description")) or r.text[:200]
            hint = {"access_token_invalid": "Token hết hạn — chạy lại: tt auth",
                    "scope_not_authorized": "Thiếu quyền — chạy lại tt auth và cho phép đủ quyền",
                    "unaudited_client_can_only_post_to_private_accounts":
                        "App chưa qua kiểm duyệt: chỉ đăng thẳng được ở chế độ riêng tư (bỏ --public) hoặc dùng hộp thư nháp",
                    "spam_risk_too_many_posts": "Đăng quá nhiều trong ngày — thử lại sau",
                    "spam_risk_too_many_pending_share":
                        "Hộp thư nháp TikTok đã đầy (tối đa 5 video chờ trong 24 giờ) — đăng hoặc xoá bớt video "
                        "trong hộp thư của app TikTok rồi chạy lại",
                    "url_ownership_unverified": "Cần xác minh quyền sở hữu domain"}.get(code, "")
            raise TTError(f"TikTok API lỗi {r.status_code} ({code}): {msg} {hint}".strip())
        return data
    raise TTError("TikTok API không phản hồi")


# ---------------- xác thực ----------------
def _paths(base_dir, brand):
    d = secrets_dir(base_dir)
    return os.path.join(d, "tiktok_app.json"), os.path.join(d, f"tiktok_token_{brand}.json")


def _app(base_dir, brand):
    app_p, _ = _paths(base_dir, brand)
    if not os.path.exists(app_p):
        with open(app_p, "w", encoding="utf-8") as f:
            json.dump({"client_key": "DAN_CLIENT_KEY_VAO_DAY", "client_secret": "DAN_CLIENT_SECRET_VAO_DAY"}, f, indent=1)
    app = json.load(open(app_p, encoding="utf-8-sig"))
    if not app.get("client_key") or not app.get("client_secret") or "DAN_" in app["client_key"] + app["client_secret"]:
        raise TTError(f"Chưa điền {app_p}\n→ TikTok for Developers → app → Client key + Client secret: "
                      "chủ app tự dán vào file này (không gửi qua chat).")
    if app["client_key"].startswith("EAA") or len(app["client_key"]) > 40:
        raise TTError("client_key trong tiktok_app.json không phải Client key của TikTok (có vẻ là token Facebook "
                      "còn trong clipboard) — copy lại Client key ở mục Credentials của Sandbox.")
    return app


def _pkce():
    verifier = base64.urlsafe_b64encode(_secrets.token_bytes(48)).decode().rstrip("=")[:64]
    # TikTok Login Kit for Desktop dùng SHA256 dạng hex cho code_challenge
    return verifier, hashlib.sha256(verifier.encode()).hexdigest()


def _wait_for_code(state, timeout=300):
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q or "error" in q:
                got.update({k: v[0] for k, v in q.items()})
            msg = "Đã cấp quyền TikTok. Có thể đóng tab này và quay lại Claude." if "code" in q else \
                ("Đã huỷ cấp quyền." if "error" in q else "Đang chờ TikTok...")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body style='font-family:sans-serif'><h2>{msg}</h2></body></html>".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("localhost", REDIRECT_PORT), H)
    srv.timeout = 1
    end = time.time() + timeout
    while not got and time.time() < end:
        srv.handle_request()
    srv.server_close()
    if not got:
        raise TTError("Hết thời gian chờ cấp quyền (5 phút)")
    if "error" in got:
        raise TTError(f"TikTok trả về lỗi: {got.get('error_description') or got['error']}")
    if got.get("state") != state:
        raise TTError("Sai tham số state — huỷ để an toàn, chạy lại tt auth")
    return got["code"]


def _save_token(base_dir, brand, data):
    _, token_p = _paths(base_dir, brand)
    now = time.time()
    tok = {"access_token": data["access_token"], "refresh_token": data["refresh_token"],
           "open_id": data.get("open_id"), "scope": data.get("scope"),
           "expires_at": now + int(data.get("expires_in", 86400)) - 120,
           "refresh_expires_at": now + int(data.get("refresh_expires_in", 31536000)) - 120,
           "saved_at": _dt.datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")}
    with open(token_p, "w", encoding="utf-8") as f:
        json.dump(tok, f, indent=1)
    return tok


def auth(base_dir, brand, log=print):
    app = _app(base_dir, brand)
    state = _secrets.token_urlsafe(16)
    verifier, challenge = _pkce()
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_key": app["client_key"], "scope": ",".join(SCOPES), "response_type": "code",
        "redirect_uri": REDIRECT_URI, "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256"})
    log("Mở trình duyệt để cấp quyền TikTok...")
    log(f"(Nếu trình duyệt không tự mở, dán link này vào trình duyệt: {url})")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    code = _wait_for_code(state)
    data = _req("POST", f"{API}/oauth/token/", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={
        "client_key": app["client_key"], "client_secret": app["client_secret"], "code": code,
        "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI, "code_verifier": verifier})
    tok = _save_token(base_dir, brand, data)
    missing = [s for s in SCOPES if s not in (tok.get("scope") or "")]
    if missing:
        log(f"    ⚠ chưa được cấp quyền: {', '.join(missing)} (bật sản phẩm tương ứng trong app TikTok)")
    return whoami(base_dir, brand)


def _token(base_dir, brand):
    _, token_p = _paths(base_dir, brand)
    if not os.path.exists(token_p):
        raise TTError(f"Chưa cấp quyền TikTok cho brand '{brand}'. Chạy: make_video.py tt auth --brand {brand}")
    tok = json.load(open(token_p, encoding="utf-8"))
    if time.time() < tok["expires_at"]:
        return tok["access_token"]
    if time.time() > tok["refresh_expires_at"]:
        raise TTError("Token làm mới đã hết hạn (1 năm) — chạy lại: tt auth")
    app = _app(base_dir, brand)
    data = _req("POST", f"{API}/oauth/token/", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={
        "client_key": app["client_key"], "client_secret": app["client_secret"],
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    return _save_token(base_dir, brand, data)["access_token"]


def whoami(base_dir, brand):
    d = _req("GET", f"{API}/user/info/", token=_token(base_dir, brand),
             params={"fields": "open_id,display_name,avatar_url"})
    return d.get("data", {}).get("user", {})


# ---------------- đăng ----------------
def _caption(meta):
    cap = (meta.get("caption") or "").strip()
    tags = " ".join(meta.get("hashtags") or [])
    if tags and tags not in cap:
        cap = f"{cap}\n\n{tags}".strip()
    return cap[:2200]


def _upload_file(upload_url, path, log):
    import requests
    size = os.path.getsize(path)
    chunk, n = _chunk_plan(size)
    with open(path, "rb") as f:
        for i in range(n):
            start = i * chunk
            end = size - 1 if i == n - 1 else start + chunk - 1
            f.seek(start)
            body = f.read(end - start + 1)
            r = requests.put(upload_url, data=body, timeout=600, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(body)),
                "Content-Range": f"bytes {start}-{end}/{size}"})
            if r.status_code not in (200, 201, 206):
                raise TTError(f"Tải file lên TikTok lỗi {r.status_code}: {r.text[:200]}")
    log(f"    tải lên {size / 1e6:.1f} MB xong")
    return size


def _chunk_plan(size):
    chunk = size if size <= CHUNK * 1.5 else CHUNK
    count = 1 if size <= chunk else size // chunk
    return chunk, count


def upload(base_dir, brand, project_dir, which="all", direct=False, public=False, dry_run=False, again=False, log=print):
    pub_path = os.path.join(project_dir, "publish", "publish.json")
    if not os.path.exists(pub_path):
        raise TTError("Chưa có publish/publish.json — dựng video trước (make_video.py build)")
    if public and not direct:
        raise TTError("--public chỉ dùng cùng --direct")
    if public and not is_approved(project_dir):
        raise TTError("Kịch bản chưa được đánh dấu duyệt pháp lý — không đăng công khai.\n"
                      f"→ Khi đã duyệt: make_video.py approve {os.path.basename(project_dir)} --by \"Tên\"")
    pub = json.load(open(pub_path, encoding="utf-8"))
    items = [(f"tiktok:{s['files']['id']}", s["files"], s.get("tiktok") or {})
             for s in pub.get("shorts", []) if which in ("all", s["files"]["id"])]
    if not items:
        raise TTError(f"Không có bản dọc '{which}' trong publish.json")
    posted = load_posted(project_dir)
    tt = posted.setdefault("tiktok", {})
    token = None if dry_run else _token(base_dir, brand)
    privacy = None
    if direct and not dry_run:
        info = _req("POST", f"{API}/post/publish/creator_info/query/", token=token,
                    headers={"Content-Type": "application/json; charset=UTF-8"}, json={}).get("data", {})
        opts = info.get("privacy_level_options") or []
        privacy = "PUBLIC_TO_EVERYONE" if public else "SELF_ONLY"
        if privacy not in opts:
            raise TTError(f"Tài khoản không cho chế độ {privacy} (được: {', '.join(opts)})")
    results = []
    for key, files, meta in items:
        if key in tt and not again:
            log(f"  ↷ {key}: đã đẩy lên rồi ({tt[key].get('state')}) — bỏ qua (dùng --again)")
            continue
        if files.get("draft"):
            raise TTError(f"{key}: đây là bản nháp (--draft), dựng bản chính trước khi đăng")
        cap = _caption(meta)
        mode = ("đăng thẳng " + ("công khai" if public else "riêng tư")) if direct else "hộp thư nháp"
        log(f"  → {key} [{mode}] {os.path.basename(files['video'])} ({files.get('duration', 0):.0f}s)")
        log("    caption: " + cap.splitlines()[0][:100] if cap else "    (chưa có caption TikTok trong seo.json)")
        if dry_run:
            results.append({"key": key, "dry_run": True})
            continue
        size = os.path.getsize(files["video"])
        chunk, count = _chunk_plan(size)
        src = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}
        if direct:
            body = {"post_info": {"title": cap, "privacy_level": privacy, "disable_duet": False,
                                  "disable_comment": False, "disable_stitch": False,
                                  "video_cover_timestamp_ms": 1000}, "source_info": src}
            init = _req("POST", f"{API}/post/publish/video/init/", token=token,
                        headers={"Content-Type": "application/json; charset=UTF-8"}, json=body)["data"]
        else:
            init = _req("POST", f"{API}/post/publish/inbox/video/init/", token=token,
                        headers={"Content-Type": "application/json; charset=UTF-8"}, json={"source_info": src})["data"]
        _upload_file(init["upload_url"], files["video"], log)
        rec = {"publish_id": init["publish_id"], "mode": "direct" if direct else "inbox",
               "privacy": privacy, "state": "PROCESSING", "caption": cap,
               "uploaded_at": _dt.datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M"), "brand": brand}
        tt[key] = rec
        save_posted(project_dir, posted)
        results.append({"key": key, **rec})
    return results


def status(base_dir, brand, project_dir):
    tt = load_posted(project_dir).get("tiktok", {})
    if not tt:
        return []
    token = _token(base_dir, brand)
    posted = load_posted(project_dir)
    out = []
    for key, rec in tt.items():
        try:
            d = _req("POST", f"{API}/post/publish/status/fetch/", token=token,
                     headers={"Content-Type": "application/json; charset=UTF-8"},
                     json={"publish_id": rec["publish_id"]}).get("data", {})
            st = d.get("status")
            posted["tiktok"][key]["state"] = st
            ids = d.get("publicaly_available_post_id") or d.get("publicly_available_post_id") or []
            if ids:
                posted["tiktok"][key]["post_ids"] = ids
            out.append({"key": key, "mode": rec["mode"], "status": st, "fail_reason": d.get("fail_reason"),
                        "post_ids": ids})
        except TTError as e:
            out.append({"key": key, "error": str(e)[:160]})
    save_posted(project_dir, posted)
    return out
