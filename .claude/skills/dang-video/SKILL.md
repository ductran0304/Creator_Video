---
name: dang-video
description: Đăng video đã dựng (projects/<slug>/publish/) lên YouTube (video dài + Shorts), Facebook Page (video + Reels) và TikTok (hộp thư nháp) bằng API, theo dõi trạng thái và lượt xem. Dùng khi người dùng nói "đăng video N", "đăng shorts/reels", "upload lên YouTube/Facebook/TikTok", "video đã đăng thế nào".
---

# /dang-video — đăng và quản lý video trên mạng xã hội

Công cụ: `h2dev_pipeline/core/social/youtube.py`, gọi qua CLI. Chạy từ `h2dev_pipeline/`:
`MV = PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -u make_video.py`

Hiện hỗ trợ: **YouTube** (video dài + Shorts), **Facebook Page** (video dài + Reels), **TikTok** (bản dọc, hộp thư nháp).

## Quy tắc an toàn (bắt buộc)

- **Mặc định `--privacy private`.** Chỉ `unlisted`/`public`/`--publish-at` khi người dùng yêu cầu rõ cho đúng video đó
  VÀ `projects/<slug>/review.json` có `"approved": true` (CLI tự chặn). Chỉ người dùng mới được báo "đã duyệt" —
  chạy `MV approve <slug> --by "<tên người duyệt>"` theo lời họ, không tự đánh dấu.
- Nội dung KTTG phải được người có chứng chỉ của KTTG duyệt trước khi công khai.
- Không đăng nhập hay nhập mật khẩu thay người dùng. Cấp quyền chỉ bằng `MV yt auth` (người dùng tự bấm Cho phép).
- `h2dev_pipeline/secrets/` (client secret + token) đã gitignore: không in nội dung, không commit, không gửi đi đâu.
- Không đăng lại video đã có trong `publish/posted.json` trừ khi người dùng yêu cầu (`--again`).
- Bình luận trả lời khán giả: soạn nháp cho người dùng duyệt, không tự đăng.

## Xác định video

"Video số N" → tra `brands/<brand>/topics.md` (phần đã làm, cột slug) → `projects/<slug>/`. Phải có
`publish/publish.json` (đã `build`, không phải bản `--draft`). Brand lấy từ `scenes.json` → `"brand"`.

## Các lệnh

```
MV yt whoami                                   # kiểm tra đúng kênh (lần đầu mỗi phiên)
MV yt upload <slug> --dry-run --target all     # xem trước metadata sẽ gửi
MV yt upload <slug>                            # video dài (private) + thumbnail + phụ đề + playlist
MV yt upload <slug> --target shorts            # tất cả bản dọc · --target <id> một bản · --target all = dài + dọc
MV yt upload <slug> --create-playlist          # tạo playlist trong seo.json nếu kênh chưa có
MV yt upload <slug> --privacy public           # chỉ khi đã approve và người dùng yêu cầu
MV yt upload <slug> --publish-at "2026-10-01 19:00"   # hẹn giờ công khai (giờ VN), cần approve
MV yt status <slug>                            # xử lý / công khai / lượt xem, thích, bình luận
MV approve <slug> --by "Tên"                   # ghi review.json
```

Thứ tự đăng: **video dài trước**. Sau khi đăng video dài, công cụ tự điền `long_url` vào `seo.json` và dựng lại
metadata, nên mô tả Shorts/TikTok/Reels có link bản đầy đủ. Đăng Shorts khi video dài chưa có link → CLI chặn.

## Quy trình "đăng video N"

1. `MV yt whoami` → xác nhận đúng kênh của brand.
2. `MV yt upload <slug> --target all --dry-run` → soát tiêu đề (≤ 100 ký tự), mô tả, tag.
3. `MV yt upload <slug> --target all` (private). Build dài có thể mất vài phút: chạy nền nếu nhiều video.
4. Báo người dùng: link video dài + từng Shorts, playlist, **bình luận cần ghim thủ công** (CLI in ra — API không ghim được),
   nhắc duyệt nội dung rồi tự công khai trong YouTube Studio (video dài trước, Shorts sau).

Đăng hàng loạt: hạn mức mặc định 10.000 đơn vị/ngày, mỗi lần tải video tốn nhiều đơn vị nhất (xem Cloud Console → Quotas),
nên chia vài video mỗi ngày (tính cả Shorts, thumbnail,
phụ đề). Gặp `quotaExceeded` → dừng, báo người dùng, làm tiếp sau 14h giờ VN hôm sau.

## Lỗi hay gặp

- `Chưa cấp quyền` / `Token hết hạn hoặc bị thu hồi` → `MV yt auth --brand <brand>` (người dùng chọn đúng kênh,
  "Advanced → Go to KTTG Video" ở cảnh báo app chưa xác minh).
- Video bị khoá private dù đặt public: app chưa qua **YouTube API Services Audit** → người dùng công khai thủ công
  trong Studio hoặc gửi form audit.
- `⚠ chưa đặt được thumbnail` → kênh cần xác minh số điện thoại (youtube.com/verify).
- `forbidden` → token cấp cho kênh khác; chạy lại `yt auth` và chọn đúng kênh.

## Thiết lập lần đầu (brand mới)

Google Cloud project → bật YouTube Data API v3 + YouTube Analytics API → Google Auth Platform (Branding: tên app,
email, trang chủ/chính sách/điều khoản trên domain của brand, Authorized domain; Audience: External → Publish app
"In production" để token không hết hạn sau 7 ngày) → Clients → Desktop app → Download JSON →
`h2dev_pipeline/secrets/youtube_client_secret.json` → `MV yt auth --brand <brand>` (token lưu
`secrets/youtube_token_<brand>.json`).

## Facebook Page (video dài + Reels)

Công cụ: `core/social/facebook.py` (Graph API v26.0). Dữ liệu lấy từ `publish.json`: video dài dùng tiêu đề + mô tả
YouTube (tự bỏ khối chương), Reels dùng `reels.caption` của từng bản dọc (3–90 giây).

```
MV fb auth                                  # đổi token Graph API Explorer (secrets/facebook_user_token.txt) → token Page không hết hạn
MV fb pages · MV fb use "<tên Page>"        # xem / chọn Page đang đăng
MV fb upload <slug> --dry-run               # xem trước
MV fb upload <slug>                         # video dài ẩn (unpublished) + Reels bản nháp (DRAFT)
MV fb upload <slug> --target reels|long|<id> · --publish (cần approve + người dùng yêu cầu)
MV fb status <slug>
```

Mặc định không công khai: người dùng xem và bấm đăng trong Meta Business Suite → Nội dung.
Thiết lập (đã làm cho KTTG — app "KTTG Video" id 1630499335455445, Page "Kế Toán Tinh Gọn" id 1270665479459006):
Meta for Developers → tạo app (use case "Quản lý mọi thứ trên Trang", bật pages_manage_posts, pages_read_engagement,
read_insights) → Graph API Explorer: chọn app + 4 quyền → **người dùng tự bấm** Generate Access Token (popup bị chặn
nếu Claude bấm), tick đúng Page → nút ⓘ → "Mở trong Công cụ tạo mã truy cập" → "Mã truy cập mở rộng" → **người dùng tự
chép** token dài hạn vào `secrets/facebook_user_token.txt` (Claude không được đọc giá trị token) → `MV fb auth`
(không cần App Secret; token Page lấy từ token dài hạn không hết hạn; file tạm tự xoá) → `MV fb use <id Page>`.
Facebook Login không nhận redirect `http://localhost` (bắt buộc HTTPS), nên không dùng luồng đăng nhập trên máy.
App để chế độ Live (cần URL chính sách bảo mật) để bài đăng hiển thị với mọi người; quyền Standard access đủ cho
quản trị viên của chính app, không cần App Review.

## TikTok (bản dọc)

Công cụ: `core/social/tiktok.py` (Content Posting API v2, Login Kit for Desktop + PKCE, redirect
`http://localhost:8767/callback/`). Caption lấy từ `tiktok.caption` + hashtag của từng bản dọc.

```
MV tt auth · MV tt whoami                  # cấp quyền (người dùng bấm Cho phép), token tự làm mới, hạn 1 năm
MV tt upload <slug> --dry-run
MV tt upload <slug>                        # đẩy vào HỘP THƯ NHÁP TikTok — CLI in caption để người dùng dán rồi tự đăng
MV tt upload <slug> --direct               # đăng thẳng, riêng tư (SELF_ONLY) khi app chưa được TikTok duyệt
MV tt upload <slug> --direct --public      # chỉ khi approve + app đã qua kiểm duyệt của TikTok
MV tt status <slug>                        # SEND_TO_USER_INBOX / PUBLISH_COMPLETE / FAILED
```

Thiết lập (đã làm cho KTTG — app "KTTG Video" id 7689672283481360391, dùng Sandbox "KTTG test", target user
ketoantinhgon): tài khoản nhà phát triển là email + mật khẩu riêng (không đăng nhập bằng Google) → tạo app Individual
→ Sandbox: icon 1024×1024 (`secrets/tiktok_app_icon_1024.png`), hạng mục, mô tả, link điều khoản/chính sách,
Platform Desktop + **Web/Desktop URL** (bỏ trống thì Apply changes không lưu → lỗi `client_key`), Login Kit
(Desktop redirect), Content Posting API (+ Direct Post) → Apply changes → Target Users thêm tài khoản kênh →
người dùng tự dán Client key (18 ký tự, `sb…`) + Client secret vào `secrets/tiktok_app.json` → `MV tt auth`.
Bản Production cần gửi kiểm duyệt kèm video demo luồng đăng; trước đó dùng Sandbox + hộp thư nháp.

## Đăng hàng loạt + công khai + báo cáo

```
MV social report                                   # bảng V1…Vn: cần / đã lên / công khai trên 3 nền tảng
MV social upload --platforms yt,fb --from 25 --to 28   # tải phần còn thiếu (bỏ qua mục có trong posted.json)
MV social publish --platforms yt,fb --pace 150     # công khai mục đã tải (cần approve), Facebook cách 150 giây
MV yt publish <slug> · MV fb publish <slug>        # công khai từng video
```

- Trước khi đăng hàng loạt: đối chiếu tiêu đề với video đã có trên kênh (người dùng có thể đã đăng tay) và ghi vào
  posted.json với `"external": true` để không đăng trùng.
- Giới hạn đã gặp (26/09/2026): YouTube hết lượt tải sau ~80 video/ngày (429 "Video Uploads", reset 14h VN) — đổi
  công khai hàng loạt nhanh nhất bằng YouTube Studio (lọc Visibility: Private → chọn tất cả → Edit → Visibility →
  Public) thay vì API. Facebook: ~200 lệnh gọi/giờ (code 4) và **chặn chống spam code 368** khi đăng dày → dừng hẳn,
  làm tiếp hôm sau với --pace. TikTok: hộp thư nháp tối đa 5 video chờ/24 giờ; video vào hộp thư KHÔNG có caption —
  gửi người dùng danh sách caption đánh số theo thời lượng/nội dung. Đăng TikTok qua web cần Claude in Chrome
  (trình duyệt trong app không chọn được file). Nên giới hạn ~3–5 video TikTok/ngày.
- Không xoá video trên kênh thay người dùng (không hoàn tác được) — báo để họ tự xoá.
