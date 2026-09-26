"""YouTube: cấp quyền OAuth, tải video + thumbnail + phụ đề + playlist, theo dõi trạng thái.

  make_video.py yt auth [--brand kttg]                 mở trình duyệt để chủ kênh bấm "Cho phép" (một lần)
  make_video.py yt whoami [--brand kttg]               kiểm tra đang kết nối đúng kênh nào
  make_video.py yt upload <slug> [--target long|<short_id>|all] [--privacy private|unlisted|public]
                          [--publish-at "2026-10-01 19:00"] [--dry-run] [--again]
  make_video.py yt status <slug>                       trạng thái xử lý / công khai / lượt xem các video đã đăng
  make_video.py approve <slug> --by "Tên người duyệt"  đánh dấu kịch bản đã được người có chứng chỉ duyệt

Quy tắc an toàn:
- Mặc định tải lên ở chế độ riêng tư (private). Công khai (public/unlisted) hoặc hẹn giờ công khai (--publish-at)
  chỉ được khi projects/<slug>/review.json có "approved": true.
- Không tải lại video đã có trong publish/posted.json (trừ khi --again).
- Token OAuth lưu ở h2dev_pipeline/secrets/ (đã gitignore). Không bao giờ in token ra màn hình.
"""
import datetime as _dt
import json
import os
import time

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
CATEGORY = {"Education": "27", "People & Blogs": "22", "Howto & Style": "26", "Science & Technology": "28"}
VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


class YTError(Exception):
    pass


# ---------------- xác thực ----------------
def secrets_dir(base_dir):
    d = os.path.join(base_dir, "secrets")
    os.makedirs(d, exist_ok=True)
    return d


def _paths(base_dir, brand):
    d = secrets_dir(base_dir)
    return os.path.join(d, "youtube_client_secret.json"), os.path.join(d, f"youtube_token_{brand}.json")


def auth(base_dir, brand):
    """Chạy luồng OAuth trên máy (mở trình duyệt). Chủ kênh tự đăng nhập Google và bấm Cho phép."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    client, token = _paths(base_dir, brand)
    if not os.path.exists(client):
        raise YTError(f"Chưa có file OAuth client: {client}\n"
                      "→ Tải file JSON của OAuth Client (loại Desktop) từ Google Cloud Console, đổi tên thành "
                      "youtube_client_secret.json và đặt vào thư mục secrets/.")
    flow = InstalledAppFlow.from_client_secrets_file(client, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True, prompt="consent",
                                  authorization_prompt_message="Mở trình duyệt để cấp quyền YouTube...",
                                  success_message="Đã cấp quyền. Có thể đóng tab này và quay lại Claude.")
    with open(token, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return token


def _creds(base_dir, brand):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    _, token = _paths(base_dir, brand)
    if not os.path.exists(token):
        raise YTError(f"Chưa cấp quyền cho brand '{brand}'. Chạy: make_video.py yt auth --brand {brand}")
    creds = Credentials.from_authorized_user_file(token, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:  # noqa: BLE001
                raise YTError(f"Token hết hạn hoặc bị thu hồi ({e.__class__.__name__}). Chạy lại: yt auth --brand {brand}")
            with open(token, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        else:
            raise YTError(f"Token không hợp lệ. Chạy lại: yt auth --brand {brand}")
    return creds


def service(base_dir, brand, api="youtube", version="v3"):
    from googleapiclient.discovery import build
    return build(api, version, credentials=_creds(base_dir, brand), cache_discovery=False)


def whoami(base_dir, brand):
    yt = service(base_dir, brand)
    r = yt.channels().list(part="snippet,statistics,status", mine=True).execute()
    out = []
    for c in r.get("items", []):
        out.append({"id": c["id"], "title": c["snippet"]["title"], "custom_url": c["snippet"].get("customUrl"),
                    "subscribers": c["statistics"].get("subscriberCount"), "videos": c["statistics"].get("videoCount"),
                    "long_uploads": c.get("status", {}).get("longUploadsStatus")})
    return out


# ---------------- duyệt & sổ đăng ----------------
def review_path(project_dir):
    return os.path.join(project_dir, "review.json")


def approve(project_dir, by, note=""):
    data = {"approved": True, "by": by, "note": note,
            "date": _dt.datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")}
    with open(review_path(project_dir), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data


def is_approved(project_dir):
    p = review_path(project_dir)
    if not os.path.exists(p):
        return False
    try:
        return bool(json.load(open(p, encoding="utf-8")).get("approved"))
    except (OSError, ValueError):
        return False


def posted_path(project_dir):
    return os.path.join(project_dir, "publish", "posted.json")


def load_posted(project_dir):
    p = posted_path(project_dir)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {"youtube": {}}


def save_posted(project_dir, data):
    with open(posted_path(project_dir), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


# ---------------- chuẩn bị metadata ----------------
def _fit_tags(tags, limit=480):
    out, total = [], 0
    for t in tags or []:
        t = t.replace("<", "").replace(">", "").strip()
        cost = len(t) + (2 if " " in t else 0) + (1 if out else 0)
        if not t or total + cost > limit:
            continue
        out.append(t)
        total += cost
    return out


def parse_publish_at(s):
    """'2026-10-01 19:00' (giờ Việt Nam) hoặc ISO → chuỗi RFC3339 UTC cho API."""
    s = s.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            t = _dt.datetime.strptime(s, fmt).replace(tzinfo=VN_TZ)
            break
        except ValueError:
            continue
    else:
        raise YTError(f"Không đọc được thời gian '{s}' — dùng dạng 2026-10-01 19:00 (giờ Việt Nam)")
    if t <= _dt.datetime.now(VN_TZ) + _dt.timedelta(minutes=15):
        raise YTError("Giờ hẹn phải ở tương lai, cách hiện tại ít nhất 15 phút")
    return t.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def targets(pub, which):
    """Danh sách (key, files, meta) cần đăng từ publish.json."""
    items = []
    if which in ("long", "all"):
        items.append(("long", pub["long"]["files"], pub["long"]["youtube"]))
    for s in pub.get("shorts", []):
        sid = s["files"]["id"]
        if which in (sid, "all", "shorts"):
            items.append((f"short:{sid}", s["files"], s["youtube_shorts"]))
    if not items:
        raise YTError(f"Không có mục '{which}' trong publish.json (long, all, shorts, hoặc id bản dọc)")
    return items


def build_body(meta, privacy, publish_at, is_short):
    title = (meta.get("title") or "").strip()
    if len(title) > 100:
        title = title[:99].rstrip() + "…"
    desc = meta.get("description") or ""
    tags_line = " ".join(meta.get("hashtags") or [])
    if tags_line and tags_line not in desc:
        desc = f"{desc}\n\n{tags_line}"
    if len(desc) > 4900:
        desc = desc[:4890] + "…"
    body = {
        "snippet": {"title": title, "description": desc,
                    "tags": _fit_tags(meta.get("tags") or []),
                    "categoryId": CATEGORY.get(meta.get("category", "Education"), "27"),
                    "defaultLanguage": meta.get("language", "vi"), "defaultAudioLanguage": meta.get("language", "vi")},
        "status": {"privacyStatus": "private" if publish_at else privacy,
                   "selfDeclaredMadeForKids": bool(meta.get("made_for_kids", False)),
                   "embeddable": True},
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at
    return body


# ---------------- tải lên ----------------
def _upload_file(yt, path, body, log):
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    media = MediaFileUpload(path, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media, notifySubscribers=True)
    resp, retries, last = None, 0, -10
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status and status.progress() * 100 - last >= 10:
                last = status.progress() * 100
                log(f"    tải lên {last:.0f}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise YTError(_http_msg(e))
        except (ConnectionError, TimeoutError, OSError) as e:
            if retries < 5:
                retries += 1
                log(f"    mạng lỗi ({e.__class__.__name__}), thử lại {retries}/5...")
                time.sleep(2 ** retries)
                continue
            raise
    return resp["id"]


def _http_msg(e):
    try:
        d = json.loads(e.content.decode("utf-8"))
        err = d["error"]
        reason = (err.get("errors") or [{}])[0].get("reason", "")
        hint = {
            "quotaExceeded": "Hết hạn mức API hôm nay — thử lại sau 14h (giờ VN) hoặc xin tăng hạn mức.",
            "uploadLimitExceeded": "Kênh đã chạm giới hạn tải lên trong ngày.",
            "forbidden": "Tài khoản không có quyền trên kênh này — kiểm tra đăng nhập đúng kênh.",
            "insufficientPermissions": "Token thiếu quyền — chạy lại yt auth.",
        }.get(reason, "")
        return f"YouTube API lỗi {e.resp.status} {reason}: {err.get('message')} {hint}".strip()
    except Exception:  # noqa: BLE001
        return f"YouTube API lỗi {e.resp.status}"


def _set_thumbnail(yt, video_id, path, log):
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    try:
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(path, mimetype="image/png")).execute()
        log("    ✓ thumbnail")
        return True
    except HttpError as e:
        log(f"    ⚠ chưa đặt được thumbnail: {_http_msg(e)} (kênh cần xác minh số điện thoại để dùng thumbnail tuỳ chỉnh)")
        return False


def _add_caption(yt, video_id, srt, lang, log):
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    try:
        yt.captions().insert(part="snippet", body={"snippet": {"videoId": video_id, "language": lang,
                                                               "name": "Tiếng Việt" if lang == "vi" else lang,
                                                               "isDraft": False}},
                             media_body=MediaFileUpload(srt, mimetype="application/octet-stream")).execute()
        log("    ✓ phụ đề")
        return True
    except HttpError as e:
        log(f"    ⚠ chưa thêm được phụ đề: {_http_msg(e)}")
        return False


def _playlist_id(yt, title, create, log):
    page = None
    while True:
        r = yt.playlists().list(part="snippet", mine=True, maxResults=50, pageToken=page).execute()
        for p in r.get("items", []):
            if p["snippet"]["title"].strip().lower() == title.strip().lower():
                return p["id"]
        page = r.get("nextPageToken")
        if not page:
            break
    if not create:
        log(f"    ⚠ chưa có playlist '{title}' trên kênh (chạy lại với --create-playlist để tạo)")
        return None
    p = yt.playlists().insert(part="snippet,status", body={"snippet": {"title": title, "defaultLanguage": "vi"},
                                                            "status": {"privacyStatus": "public"}}).execute()
    log(f"    ✓ tạo playlist '{title}'")
    return p["id"]


def _add_to_playlist(yt, video_id, title, create, log):
    from googleapiclient.errors import HttpError
    try:
        pid = _playlist_id(yt, title, create, log)
        if pid:
            yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid, "resourceId": {
                "kind": "youtube#video", "videoId": video_id}}}).execute()
            log(f"    ✓ thêm vào playlist '{title}'")
        return pid
    except HttpError as e:
        log(f"    ⚠ playlist: {_http_msg(e)}")
        return None


def upload(base_dir, brand, project, project_dir, which="long", privacy="private", publish_at=None,
           dry_run=False, again=False, create_playlist=False, log=print):
    pub_path = os.path.join(project_dir, "publish", "publish.json")
    if not os.path.exists(pub_path):
        raise YTError("Chưa có publish/publish.json — dựng video trước (make_video.py build)")
    if (privacy != "private" or publish_at) and not is_approved(project_dir):
        raise YTError("Kịch bản chưa được đánh dấu duyệt pháp lý. Chỉ được tải lên ở chế độ private.\n"
                      f"→ Khi người có chứng chỉ đã duyệt: make_video.py approve {os.path.basename(project_dir)} --by \"Tên\"")
    publish_rfc = parse_publish_at(publish_at) if publish_at else None
    posted = load_posted(project_dir)
    yt_posted = posted.setdefault("youtube", {})
    results = []
    yt = None if dry_run else service(base_dir, brand)
    keys = [k for k, _, _ in targets(json.load(open(pub_path, encoding="utf-8")), which)]
    for key in keys:
        # đọc lại mỗi vòng: sau khi đăng video dài, mô tả Shorts đã được điền long_url
        files, meta = next((f, m) for k, f, m in targets(json.load(open(pub_path, encoding="utf-8")), which)
                           if k == key)
        if key in yt_posted and not again:
            log(f"  ↷ {key}: đã đăng rồi ({yt_posted[key]['url']}) — bỏ qua (dùng --again để tải lại)")
            continue
        if files.get("draft"):
            raise YTError(f"{key}: đây là bản nháp (--draft), dựng bản chính trước khi đăng")
        is_short = key.startswith("short:")
        # bản dọc: mô tả phải có link video dài
        desc = meta.get("description") or ""
        if is_short and ("{{long_url}}" in desc or "<dán link" in desc):
            if not dry_run:
                raise YTError(f"{key}: mô tả Shorts còn thiếu link video dài — đăng video dài trước")
            log("    ⚠ mô tả còn thiếu link video dài (tự điền khi đăng video dài trước trong cùng lệnh)")
        body = build_body(meta, privacy, publish_rfc, is_short)
        log(f"  → {key}: {body['snippet']['title']}")
        log(f"    {body['status']['privacyStatus']}" + (f", hẹn công khai {publish_at} (giờ VN)" if publish_rfc else "")
            + f", {len(body['snippet']['tags'])} tag, file {os.path.basename(files['video'])}")
        if dry_run:
            results.append({"key": key, "dry_run": True, "body": body})
            continue
        vid = _upload_file(yt, files["video"], body, log)
        url = f"https://youtu.be/{vid}" if not is_short else f"https://youtube.com/shorts/{vid}"
        log(f"    ✓ đã tải lên: {url}")
        rec = {"id": vid, "url": url, "privacy": body["status"]["privacyStatus"], "publish_at": publish_at,
               "title": body["snippet"]["title"],
               "uploaded_at": _dt.datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M"), "brand": brand}
        if not is_short and files.get("thumbnail"):
            rec["thumbnail"] = _set_thumbnail(yt, vid, files["thumbnail"], log)
        if files.get("srt"):
            rec["captions"] = _add_caption(yt, vid, files["srt"], meta.get("language", "vi"), log)
        if not is_short and meta.get("playlist"):
            rec["playlist"] = _add_to_playlist(yt, vid, meta["playlist"], create_playlist, log)
        if not is_short and meta.get("pinned_comment"):
            rec["pinned_comment_todo"] = meta["pinned_comment"]
        yt_posted[key] = rec
        save_posted(project_dir, posted)
        results.append({"key": key, **rec})
        if key == "long":
            _fill_long_url(project, project_dir, url, log)
    return results


def _fill_long_url(project, project_dir, url, log):
    """Ghi long_url vào seo.json rồi dựng lại metadata để mô tả Shorts/TikTok/Reels có link video dài."""
    seo_p = os.path.join(project_dir, "seo.json")
    if not os.path.exists(seo_p):
        return
    seo = json.load(open(seo_p, encoding="utf-8"))
    if seo.get("long_url") == url:
        return
    seo["long_url"] = url
    json.dump(seo, open(seo_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from core.build import republish
    republish(project, project_dir, log=lambda *a, **k: None)
    log(f"    ✓ điền long_url vào seo.json và cập nhật mô tả Shorts/TikTok/Reels")


# ---------------- trạng thái ----------------
def status(base_dir, brand, project_dir):
    posted = load_posted(project_dir).get("youtube", {})
    if not posted:
        return []
    yt = service(base_dir, brand)
    ids = [v["id"] for v in posted.values()]
    r = yt.videos().list(part="status,processingDetails,statistics,snippet", id=",".join(ids)).execute()
    by_id = {it["id"]: it for it in r.get("items", [])}
    out = []
    for key, rec in posted.items():
        it = by_id.get(rec["id"])
        if not it:
            out.append({"key": key, "url": rec["url"], "state": "không tìm thấy (đã xoá?)"})
            continue
        st, stats = it["status"], it.get("statistics", {})
        out.append({"key": key, "url": rec["url"], "privacy": st.get("privacyStatus"),
                    "upload": st.get("uploadStatus"), "publish_at": st.get("publishAt"),
                    "processing": it.get("processingDetails", {}).get("processingStatus"),
                    "rejection": st.get("rejectionReason") or st.get("failureReason"),
                    "views": stats.get("viewCount"), "likes": stats.get("likeCount"),
                    "comments": stats.get("commentCount")})
    return out


# ---------------- công khai ----------------
def publish(base_dir, brand, project_dir, which="all", log=print):
    """Chuyển các video đã tải (posted.json) sang công khai. Video dài trước, Shorts sau. Cần review.json approved."""
    if not is_approved(project_dir):
        raise YTError(f"{os.path.basename(project_dir)}: chưa đánh dấu duyệt — chạy approve trước")
    posted = load_posted(project_dir)
    recs = posted.get("youtube", {})
    keys = sorted(recs, key=lambda k: (k != "long", k))
    keys = [k for k in keys if which == "all" or k == which or (which == "shorts" and k.startswith("short:"))]
    yt = service(base_dir, brand)
    out = []
    for k in keys:
        rec = recs[k]
        if rec.get("privacy") == "public":
            continue
        cur = yt.videos().list(part="status", id=rec["id"]).execute().get("items", [])
        if not cur:
            log(f"  ⚠ {k}: không tìm thấy video {rec['id']} trên kênh")
            continue
        st = cur[0]["status"]
        if st.get("privacyStatus") != "public":
            body = {"id": rec["id"], "status": {"privacyStatus": "public",
                                                "selfDeclaredMadeForKids": st.get("selfDeclaredMadeForKids", False),
                                                "embeddable": st.get("embeddable", True),
                                                "license": st.get("license", "youtube"),
                                                "publicStatsViewable": st.get("publicStatsViewable", True)}}
            from googleapiclient.errors import HttpError
            try:
                yt.videos().update(part="status", body=body).execute()
            except HttpError as e:
                raise YTError(f"{k}: {_http_msg(e)}")
        rec["privacy"] = "public"
        rec["published_at"] = _dt.datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M")
        save_posted(project_dir, posted)
        log(f"  ✓ công khai {k}: {rec['url']}")
        out.append(k)
    return out
