---
name: dang-video
description: Đăng video đã dựng (projects/<slug>/publish/) lên YouTube (video dài + Shorts) bằng API, theo dõi trạng thái và lượt xem. Dùng khi người dùng nói "đăng video N", "đăng shorts", "upload lên YouTube", "video đã đăng thế nào".
---

# /dang-video — đăng và quản lý video trên mạng xã hội

Công cụ: `h2dev_pipeline/core/social/youtube.py`, gọi qua CLI. Chạy từ `h2dev_pipeline/`:
`MV = PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -u make_video.py`

Hiện hỗ trợ: **YouTube** (video dài + Shorts). Facebook Page Reels, TikTok: chưa làm (giai đoạn sau).

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
