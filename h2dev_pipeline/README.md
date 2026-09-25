# H2Dev Doodle Video — dựng video doodle hoàn toàn bằng code

Từ một chủ đề, **Claude Code** viết kịch bản kèm mô tả hình từng cảnh, còn pipeline này **vẽ doodle bằng code**,
tạo giọng đọc, và dựng thành **video dài 16:9** (YouTube) + **bản dọc 9:16** (YouTube Shorts, TikTok, Reels) có nhạc
nền, hiệu ứng âm thanh, phụ đề, chapters, thumbnail/cover — cùng **gói đăng tải** chứa tiêu đề, mô tả, tags, hashtag,
caption đã kiểm tra giới hạn của từng nền tảng.

Không cần Web UI, Google Flow, Chrome debug hay API key. Phần duy nhất cần Internet là giọng đọc edge-tts.

```
/tao-video "How did ancient humans survive winter?"      ← gõ trong Claude Code
      │
      ▼
Claude: đọc DNA kênh → viết projects/<slug>/scenes.json + seo.json
      │
      ▼
make_video.py validate → preview (Claude tự xem ảnh và sửa) → build
      │
      ▼
projects/<slug>/publish/
  PUBLISH.md          ← mở file này: nội dung copy-dán cho từng nền tảng + checklist
  publish.json        (cùng dữ liệu, dạng máy đọc)
  youtube/  <slug>.mp4 · thumbnail.png · <slug>.srt · metadata.txt
  short/    <slug>_short.mp4 · cover.png · <slug>_short.srt · youtube_shorts.txt · tiktok.txt · reels.txt
```

## Cài đặt

Cần Python 3.10+. Lần chạy đầu, `make_video.bat` (Windows) hoặc `./make_video.sh` (macOS/Linux) tự tạo `.venv`
và cài thư viện trong `requirements.txt` (edge-tts, resvg-py, Pillow, numpy, imageio-ffmpeg — ffmpeg đi kèm, không cần cài riêng).

Tài nguyên âm thanh trong `media/` (tuỳ chọn, bị gitignore nên mỗi máy tự đặt):
- `media/bg_music.mp3` — nhạc nền. Không có thì video không có nhạc nền. Chỉ dùng nhạc bạn có quyền sử dụng trên YouTube.
- `media/sfx_page.wav`, `media/sfx_pop.wav` — tiếng lật trang khi chuyển cảnh và tiếng "pop" khi hiện thành phần mới.
  Không có file thì pipeline tự tổng hợp âm mặc định.

## Cách dùng

### Cách 1 — nhờ Claude làm trọn (khuyến nghị)
Mở thư mục repo trong Claude Code và gõ:
```
/tao-video Cách người tiền sử nuôi con --vi
/tao-video How did ancient humans survive winter? --ngan
/tao-video D:\kich_ban\ban_nhap.txt          (dùng kịch bản có sẵn, giữ nguyên lời thoại)
```
Cờ: `--vi` / `--en` ngôn ngữ, `--ngan` bản thử ~300 từ, `--nhap` chỉ dựng bản nháp.
Quy trình chi tiết của skill: [`.claude/skills/tao-video/SKILL.md`](../.claude/skills/tao-video/SKILL.md).

### Cách 2 — tự chạy từng lệnh
```
make_video.bat init ten_du_an --title "Tiêu đề" --lang vi   # tạo projects/ten_du_an/scenes.json mẫu
make_video.bat validate ten_du_an                          # kiểm tra kịch bản + hình (không vẽ)
make_video.bat preview ten_du_an                           # vẽ nháp → projects/ten_du_an/preview/sheet_*.png
make_video.bat preview ten_du_an --scene 3                 # các bước hiện dần của cảnh 3
make_video.bat thumbnail ten_du_an                         # vẽ thử thumbnail 16:9 + cover 9:16 → preview/
make_video.bat build ten_du_an --draft                     # bản nháp (rất nhanh) → publish/draft/
make_video.bat build ten_du_an                             # video dài 1080p + bản dọc 1080x1920 + publish/
make_video.bat build ten_du_an --no-short                  # chỉ video dài (--short-only: chỉ bản dọc)
make_video.bat publish ten_du_an                           # chỉ ghi lại metadata sau khi sửa seo.json
make_video.bat build ten_du_an --subs                      # in phụ đề lên hình
make_video.bat asset new ten_vat --w 60 --h 120 --desc "..." # đăng ký asset mới (rồi nhờ doodle-illustrator vẽ)
make_video.bat asset check ten_vat                         # kiểm tra asset + xem trong cảnh thật
make_video.bat vocab                                       # danh sách tên hợp lệ (nền, tư thế, đồ vật...)
```
Project mẫu hoàn chỉnh: [`examples/demo_sleep/`](examples/demo_sleep/) — chạy thử bằng
`make_video.bat build examples/demo_sleep --draft`.

## Định dạng kịch bản (`scenes.json`)

Mỗi cảnh là một hình, chứa các câu thoại; mỗi câu có thể làm hình thay đổi:
```json
{
  "title": "How Did Ancient Humans Actually Sleep?",
  "language": "en",
  "scenes": [
    {
      "chapter": "The Night",
      "frame": "scene", "bg": "deep_night",
      "elements": [
        {"type": "prop", "name": "campfire", "id": "fire", "x": 0.5},
        {"type": "character", "id": "me", "variant": "you_main", "pose": "sitting",
         "attach": {"to": "fire", "side": "left", "gap": 60}},
        {"type": "label", "id": "title", "text": "SEGMENTED SLEEP", "y": 0.13}
      ],
      "lines": [
        {"text": "You wake up in the middle of the night."},
        {"text": "No alarm. No phone.", "show": ["title"], "change": {"me": {"expression": "surprise"}}}
      ]
    }
  ]
}
```
- `show`: hiện thêm thành phần từ câu này; `change`: đổi thuộc tính (biểu cảm, tư thế...) từ câu này.
- `sub` (tuỳ chọn): chữ phụ đề khác lời đọc, vd bản dịch tiếng Anh cho video lời Việt.
- Frame: `scene`, `concept_text` (chữ to), `split` (so sánh), `timeline`, `stats`.
- Neo vị trí: `attach` (đứng sát vật khác), `above` (đặt trên đầu), label `on` (chữ trên thân vật).
- Tra cứu đầy đủ: [`.claude/skills/tao-video/reference.md`](../.claude/skills/tao-video/reference.md) và `make_video.bat vocab`.

### Bản dọc 9:16 (`"short"` trong scenes.json)

```json
"short": {"lines": ["1.1-1.4", "3.2-3.4", "4.1"], "hook": "BỎ THUẾ KHOÁN 2026: ANH CHỊ CẦN LÀM GÌ?"}
```
`lines` chọn câu từ video dài (`"S"` cả cảnh, `"S.L"` một câu, `"S.L-M"` dải câu; đánh số từ 1) — mặc định cả cảnh 1.
Bản dọc dùng lại giọng đọc + hình đã cache, tự thêm câu kết (`outro` hoặc `short_outro` của thương hiệu). Bố cục:
chữ hook to ở trên · khung 16:9 + thanh tiến độ ở giữa · phụ đề to · logo + CTA, tránh vùng nút bấm/caption
của TikTok/Reels. Nên 30–60 giây (`validate` báo ước lượng).

### Metadata đăng tải (`seo.json`)

```json
{
  "youtube":        {"titles": [], "description": "... {{chapters}} ...", "tags": [], "hashtags": [],
                     "category": "Education", "playlist": "", "pinned_comment": ""},
  "youtube_shorts": {"title": "", "description": "... {{long_url}}", "hashtags": []},
  "tiktok":         {"caption": "", "hashtags": []},
  "reels":          {"caption": "", "hashtags": []},
  "long_url": "",
  "thumbnail": {"frame": "scene", "...": "..."},
  "cover": {"...": "tuỳ chọn — ảnh giữa cover 9:16"}
}
```
Mục nền tảng nào thiếu thì tự suy ra từ `youtube` (dạng cũ `titles/description/tags/hashtags` ở gốc vẫn dùng được).
`{{chapters}}` → mốc thời gian thật; `{{long_url}}` → link video dài (điền sau khi đăng rồi chạy `publish`).
Build kiểm tra: tiêu đề YouTube ≤ 100 (khuyến nghị ≤ 70), mô tả ≤ 5000, tags ≤ 500 ký tự, ≤ 15 hashtag, ≥ 3 chapters;
TikTok/Reels caption ≤ 2200, Reels ≤ 5 hashtag, dòng đầu Reels ≤ 125 ký tự; bản dọc ≤ 60–90 giây.

## Cấu hình (`config.json`)

| Khoá | Ý nghĩa | Mặc định |
|---|---|---|
| `voice_name` | Giọng edge-tts; không khớp ngôn ngữ kịch bản thì tự chọn giọng mặc định của ngôn ngữ đó | `en-US-EmmaNeural` |
| `voice_rate` | Tốc độ đọc edge-tts, vd `"+5%"` | `"+0%"` |
| `use_omnivoice`, `omnivoice_*` | Dùng OmniVoice cục bộ thay edge-tts (lỗi thì tự quay về edge-tts) | `false` |
| `bg_music_path`, `bg_music_volume` | File và âm lượng nhạc nền (nhân vào biên độ gốc) | `bg_music.mp3` (tìm cả trong `media/`), `0.05` |
| `sfx_enabled`, `sfx_path`, `sfx_volume` | Tiếng lật trang khi chuyển cảnh | `true`, `sfx_page.wav`, `0.25` |
| `sfx_reveal_path`, `sfx_reveal_volume` | Tiếng "pop" khi hiện thành phần mới | `sfx_pop.wav`, `0.15` |
| `burn_subtitles` | In phụ đề lên hình cho mọi video (từng video: `"burn_subtitles"` trong scenes.json, hoặc `build --subs`) | `false` |
| `line_gap`, `scene_gap` | Khoảng nghỉ (giây) giữa các câu / các cảnh | `0.25`, `0.6` |
| `fps`, `crf` | Khung hình/giây và chất lượng x264 của bản chuẩn | `24`, `20` |
| `script_word_count_min/max`, `min_evidence_count` | Ngưỡng cảnh báo của `validate` | `1500`, `2400`, `3` |

Các khoá cũ (`use_web2api`, `web2api_*`, `gemini_api_key`, `delay_*`, `max_wait_image`) không còn được dùng — có thể xoá.

## Cấu trúc thư mục

```
h2dev_pipeline/
├── make_video.py / .bat / .sh   # CLI
├── config.json
├── brands/<tên>/                # hồ sơ thương hiệu: brand.json (màu, font, giọng, logo, màn kết, bản dọc, mặc định đăng tải)
│   ├── h2dev/                   #   kênh người tiền sử: knowledge_base.json (DNA kênh), master_prompt.md (văn phong gốc)
│   └── kttg/                    #   Kế Toán Tinh Gọn: logo, font Be Vietnam Pro (OFL)
├── media/                       # (gitignore) bg_music.mp3, sfx_page.wav, sfx_pop.wav
├── doodle/                      # bộ vẽ: nét tay, nhân vật, đồ vật, nền, khung, font Pangolin (OFL)
├── core/                        # project.py (đọc/kiểm tra), preview.py, tts.py, audio.py, build.py,
│                                # vertical.py (bản dọc 9:16), publish.py (metadata đa nền tảng), brand.py, photos.py
├── examples/demo_sleep/         # project mẫu
└── projects/<slug>/             # (gitignore) scenes.json, seo.json, photos/, preview/, cache/, publish/
```

Cache trong `projects/<slug>/cache/` theo nội dung: sửa vài câu rồi build lại chỉ đọc lại/vẽ lại phần thay đổi.
Xoá thư mục `cache/` nếu muốn dựng lại từ đầu.

## Mở rộng bộ vẽ

- Xem trước toàn bộ thư viện: `.venv\Scripts\python -m doodle.catalog <thư_mục_ra>`.
- Thêm đồ vật / nền **không cần code**: `make_video.bat asset new ...` tạo file metadata `.json`, rồi vẽ file `.svg`
  cùng tên theo [quy chuẩn asset](doodle/assets/README.md) — trong Claude Code, agent `doodle-illustrator`
  (Sonnet, `.claude/agents/`) vẽ và tự kiểm tra; skill `/tao-video` tự gọi agent này khi thiếu hình.
- Kiểm tra: `make_video.bat asset check <tên>` (lỗi kỹ thuật + ảnh asset đặt trong cảnh thật cạnh nhân vật).
- Tên mới tự xuất hiện trong `make_video.py vocab`, nên skill dùng được ngay.
