# H2Dev Flow Pipeline — Quy trình sản xuất Video Doodle Tự động hóa Khép kín

Dự án này là một pipeline tự động hóa khép kín (End-to-End Pipeline) viết bằng Python. Chỉ từ một chủ đề hoặc ý tưởng thô đầu vào, hệ thống sẽ tự động thực hiện **100%** các bước:

1.  **Lên kịch bản & prompt ảnh** bằng Gemini API (hỗ trợ Web2API với model `gemini-3.1-pro`).
2.  **Tạo giọng thuyết minh** bằng công nghệ TTS (mặc định tích hợp `edge-tts` giọng đọc neural miễn phí, hoặc kết nối tới `OmniVoice` cục bộ). Có **cơ chế cache** — bỏ qua tạo lại nếu file audio đã tồn tại.
3.  **Tự động tính toán timestamps** khớp hoàn hảo thời gian nói với từng phân cảnh ảnh.
4.  **Tự động sinh SEO metadata** (tiêu đề, mô tả kèm chapters, tags, hashtags, prompt thumbnail) bằng Gemini (model `gemini-3.5-flash-thinking`).
5.  **Tự động điều khiển trình duyệt** (Playwright) để gửi prompt vẽ doodle & thumbnail vào Google Flow và tải ảnh về.
6.  **Dựng và render video hoàn chỉnh** `.mp4` bằng `MoviePy` và `FFmpeg` — tự động lồng **nhạc nền (BGM)**, **hiệu ứng âm thanh chuyển cảnh (SFX)**, và hiệu ứng Ken Burns zoom-in.
7.  **Xuất file phụ đề `.srt`** tự động từ timestamps.

---

## 🤖 AI Agent Context & Setup Instructions (CRITICAL FOR NEW CLONES)

**Attention AI Agents/Copilots**: If you have just cloned this repository on a new machine, follow these rules strictly to ensure the pipeline operates correctly:

1. **Self-Healing Environment**: You do NOT need to manually run `pip install` or create a `.venv`. The repository is designed for one-click setup. Instruct the user to execute `run_web.bat`. The batch script will automatically detect the missing `.venv`, create it, and install all dependencies from `requirements.txt`.
2. **Missing Files**: `.venv` and `.chrome_profile` are intentionally git-ignored. Do not attempt to recover them. 
3. **Execution Context**: The entire project is orchestrated via `h2dev_pipeline/web_ui.py` (Flask backend) and `pipeline.py`. Never run `pipeline.py` via CLI unless debugging. Always launch via `run_web.bat`.
4. **DNA Configuration**: The channel's writing style, visual rules, and SEO logic are strictly defined in `h2dev_knowledge_base.json`. When tasked with modifying prompts, ALWAYS update the `h2dev_knowledge_base.json` first, and ensure `pipeline.py` correctly reads from it.
5. **Web2API Requirement**: The pipeline relies on a local `gemini-web2api` server running on port 8081. Ensure this service is up before executing video generation tasks.

---

## 🛠 Hướng dẫn Chuẩn bị & Cài đặt (Dành cho User)

### **Bước 1: Mở Chrome Debug Mode**
Trình sinh ảnh tự động yêu cầu Chrome mở sẵn ở chế độ gỡ lỗi:
1.  Đóng hoàn toàn các tab Chrome thông thường.
2.  Mở thư mục `h2dev_flow_local` và chạy file `run_chrome.bat` (hoặc mở Chrome thủ công với tham số `--remote-debugging-port=9222`).
3.  Truy cập trang **[Google Labs Flow](https://labs.google/fx/tools/flow)**, đăng nhập tài khoản Google của bạn và mở sẵn workspace dự án (sao cho thấy ô nhập prompt trên màn hình).

### **Bước 2: Cấu hình `config.json`**
Mở file `config.json` và thiết lập theo nhu cầu. Dưới đây là bảng mô tả **tất cả** các tham số:

| Tham số | Mô tả | Giá trị mặc định |
|---------|-------|-------------------|
| `gemini_api_key` | API Key Gemini (hoặc đặt biến môi trường `GEMINI_API_KEY`) | `""` |
| `language` | Ngôn ngữ kịch bản: `"en"` (Tiếng Anh) hoặc `"vi"` (Tiếng Việt) | `"en"` |
| `voice_name` | Giọng đọc Edge TTS (xem danh sách bên dưới) | `"en-US-EmmaNeural"` |
| **Web2API** | | |
| `use_web2api` | Sử dụng Gemini qua Web2API proxy thay vì gọi trực tiếp | `true` |
| `web2api_url` | URL endpoint Web2API | `"http://localhost:8081/v1"` |
| `web2api_key` | API key cho Web2API | `"sk-gemini"` |
| `web2api_model_script` | Model dùng cho **sinh kịch bản** (sáng tạo) | `"gemini-3.1-pro"` |
| `web2api_model_seo` | Model dùng cho **sinh SEO metadata** (có cấu trúc) | `"gemini-3.5-flash-thinking"` |
| **OmniVoice** | | |
| `use_omnivoice` | Sử dụng OmniVoice cục bộ thay vì Edge TTS | `false` |
| `omnivoice_cli_path` | Đường dẫn CLI của OmniVoice | `"python -m omnivoice"` |
| `omnivoice_ref_audio` | File giọng mẫu cho OmniVoice | `"ref_voice.wav"` |
| `omnivoice_language` | Ngôn ngữ cho OmniVoice | `"English"` |
| `omnivoice_model` | Tên model OmniVoice (để trống = mặc định) | `""` |
| `omnivoice_ref_text` | Văn bản tham chiếu cho OmniVoice | `""` |
| **Nhạc nền (BGM)** | | |
| `bg_music_path` | Đường dẫn file nhạc nền (tự tải mặc định nếu chưa có) | `"bg_music.mp3"` |
| `bg_music_volume` | Âm lượng nhạc nền (0.0 – 1.0) | `0.05` (5%) |
| **Hiệu ứng âm thanh (SFX)** | | |
| `sfx_path` | Đường dẫn file hiệu ứng chuyển cảnh | `"sfx_page.wav"` |
| `sfx_volume` | Âm lượng hiệu ứng (0.0 – 1.0) | `0.25` |
| `sfx_enabled` | Bật/tắt hiệu ứng âm thanh chuyển cảnh | `true` |
| **Điều khiển trình duyệt** | | |
| `delay_min` | Thời gian nghỉ tối thiểu giữa các lần gửi prompt (giây) | `5` |
| `delay_max` | Thời gian nghỉ tối đa giữa các lần gửi prompt (giây) | `15` |
| `max_wait_image` | Thời gian tối đa chờ ảnh sinh xong (giây) | `240` |

**Ví dụ file `config.json` đầy đủ:**
```json
{
  "gemini_api_key": "",
  "use_omnivoice": false,
  "omnivoice_cli_path": "python -m omnivoice",
  "omnivoice_ref_audio": "ref_voice.wav",
  "omnivoice_language": "English",
  "omnivoice_model": "",
  "omnivoice_ref_text": "",
  "voice_name": "en-US-EmmaNeural",
  "language": "en",
  "use_web2api": true,
  "web2api_url": "http://localhost:8081/v1",
  "web2api_key": "sk-gemini",
  "web2api_model_script": "gemini-3.1-pro",
  "web2api_model_seo": "gemini-3.5-flash-thinking",
  "bg_music_path": "bg_music.mp3",
  "bg_music_volume": 0.05,
  "sfx_path": "sfx_page.wav",
  "sfx_volume": 0.25,
  "sfx_enabled": true,
  "delay_min": 5,
  "delay_max": 15,
  "max_wait_image": 240
}
```

### **Bước 3: Khởi chạy Pipeline**
1.  Nhấp đúp chuột vào file **`run_pipeline.bat`**.
2.  Trong lần chạy đầu tiên, script sẽ tự khởi động môi trường ảo `.venv`, cài đặt các thư viện cần thiết từ `requirements.txt`.
3.  Nhập chủ đề video của bạn khi màn hình CMD yêu cầu (ví dụ: *"The shocking truth about woolly mammoths"*).
4.  Ngồi xem hệ thống tự động chạy toàn bộ quy trình:
    - ✍️ Viết kịch bản → 🎙️ Tạo thuyết minh → 📊 Sinh SEO metadata → 🎨 Sinh ảnh doodle & thumbnail → 🎵 Lồng nhạc nền + hiệu ứng → 🎬 Render video hoàn chỉnh

---

## 📂 Cấu trúc Thư mục Dự án

Pipeline tự động tổ chức file theo từng dự án trong thư mục `projects/`:

```
h2dev_pipeline/
├── config.json              # Cấu hình chung
├── pipeline.py              # Script chính
├── run_pipeline.bat         # Khởi chạy pipeline
├── requirements.txt         # Danh sách thư viện Python
├── bg_music.mp3             # File nhạc nền (tự tải nếu chưa có)
├── sfx_page.wav             # Hiệu ứng âm thanh lật trang (tự tạo nếu chưa có)
└── projects/
    └── <tên_dự_án>/
        ├── temp/
        │   ├── script.json          # Kịch bản chi tiết & prompt ảnh
        │   ├── timestamps.json      # Mốc thời gian từng câu thoại
        │   ├── segment_*.wav        # Audio thuyết minh từng phân cảnh
        │   ├── full_narration.wav   # Audio thuyết minh đầy đủ
        │   └── image_*.png          # Ảnh doodle từ Google Flow
        └── outputs/
            ├── doodle_video_<ts>.mp4        # Video thành phẩm
            ├── doodle_video_<ts>.srt        # File phụ đề SRT
            ├── thumbnail.png                # Ảnh thumbnail
            ├── youtube_metadata.json        # SEO metadata (JSON)
            └── youtube_metadata.txt         # SEO metadata (văn bản)
```

---

## 🎵 Nhạc nền & Hiệu ứng Âm thanh

### Nhạc nền (BGM)
- Pipeline tự động **tải nhạc nền mặc định** từ internet nếu chưa có file `bg_music.mp3` trong thư mục gốc.
- Nhạc nền được **loop liên tục** cho khớp thời lượng video và trộn ở **âm lượng 5%** (mặc định).
- Để thay nhạc nền riêng: thay file `bg_music.mp3` bằng file nhạc của bạn.

### Hiệu ứng chuyển cảnh (SFX)
- Mặc định sử dụng tiếng **lật trang sách** (`sfx_page.wav`) — được **tự động tạo offline** bằng thuật toán nhiễu trắng + envelope nếu chưa có.
- Hiệu ứng được chèn tại **mỗi điểm chuyển cảnh** (trừ phân cảnh đầu tiên).
- Tắt hiệu ứng: đặt `"sfx_enabled": false` trong `config.json`.

---

## 🔍 SEO & YouTube Metadata Tự động

Pipeline tự động sinh YouTube metadata bằng AI (model `gemini-3.5-flash-thinking`):
- **3 tiêu đề gợi ý** CTR cao
- **Mô tả video** kèm chapters tự động từ timestamps
- **Tags & Keywords** liên quan
- **Hashtags** phổ biến
- **Prompt thumbnail** để sinh ảnh bìa video

Kết quả được lưu tại `outputs/youtube_metadata.json` và `outputs/youtube_metadata.txt` để bạn copy-paste trực tiếp khi upload video lên YouTube.

---

## ⚡ Cơ chế Cache & Tái sử dụng

Pipeline hỗ trợ **chạy lại nhanh** — khi pipeline bị gián đoạn hoặc bạn muốn chạy lại:
- **Audio cache**: Bỏ qua tạo lại TTS cho các phân cảnh đã có file audio (>1KB), giúp **giảm ~90% thời gian** chạy lại.
- **Image cache**: Bỏ qua sinh ảnh cho các phân cảnh đã có file ảnh (>1KB).

---

## 🌐 Hỗ trợ Đa ngôn ngữ

| `language` | Kịch bản | Giọng đọc mặc định |
|------------|----------|---------------------|
| `"en"` | Tiếng Anh (ngôi thứ 2: "you", "your") | `en-US-EmmaNeural` |
| `"vi"` | Tiếng Việt (ngôi thứ 2: "bạn", "của bạn") | `vi-VN-HoaiMyNeural` |

> **Lưu ý**: Prompt ảnh luôn bằng tiếng Anh bất kể ngôn ngữ kịch bản, vì Google Flow xử lý tiếng Anh tốt nhất.

---

## 🤖 Phân bổ Model AI

Pipeline sử dụng chiến lược **dual-model** để tối ưu chất lượng và chi phí:

| Tác vụ | Model | Lý do |
|--------|-------|-------|
| Sinh kịch bản | `gemini-3.1-pro` | Cần sáng tạo, văn phong tốt, prompt chi tiết |
| Sinh SEO metadata | `gemini-3.5-flash-thinking` | Cần tuân thủ format JSON, tốc độ nhanh, chi phí thấp |

Cấu hình qua `web2api_model_script` và `web2api_model_seo` trong `config.json`.

---

## ❓ Câu hỏi thường gặp & Khắc phục sự cố

#### **1. Làm thế nào để sử dụng giọng đọc mẫu của riêng tôi qua OmniVoice?**
Đổi thông số `"use_omnivoice": true` trong `config.json`, đặt tệp giọng nói mẫu của bạn tên là `ref_voice.wav` trong thư mục dự án này và đảm bảo lệnh `python -m omnivoice` có thể chạy được trên CMD của bạn.

#### **2. Có cần card đồ họa mạnh để chạy không?**
Không cần. Pipeline được thiết kế thông minh: tự tính toán thời lượng mốc thời gian từ độ dài tệp âm thanh của từng câu thay vì phải dùng mô hình AI Whisper (yêu cầu GPU nặng). Do đó, bạn có thể chạy mượt mà trên bất kỳ máy tính văn phòng thông thường nào!

#### **3. Thay đổi giọng nói mặc định của edge-tts như thế nào?**
Bạn có thể tham khảo danh sách giọng của Microsoft Edge và thay đổi trường `"voice_name"` trong `config.json`:
- Giọng nữ Mỹ: `"en-US-EmmaNeural"` (mặc định)
- Giọng nam Mỹ: `"en-US-GuyNeural"`
- Giọng nữ Việt: `"vi-VN-HoaiMyNeural"`
- Giọng nam Việt: `"vi-VN-NamMinhNeural"`

#### **4. Thay đổi nhạc nền hoặc hiệu ứng âm thanh như thế nào?**
- **Nhạc nền**: Thay thế file `bg_music.mp3` bằng bài nhạc bạn muốn. Điều chỉnh âm lượng qua `"bg_music_volume"` (0.0–1.0).
- **Hiệu ứng**: Thay thế file `sfx_page.wav` bằng file hiệu ứng bạn muốn. Điều chỉnh âm lượng qua `"sfx_volume"`.
- **Tắt SFX**: Đặt `"sfx_enabled": false`.

#### **5. Web2API là gì và cấu hình như thế nào?**
Web2API (`gemini-web2api`) là một proxy cho phép gọi Gemini API qua giao diện tương thích OpenAI. Để sử dụng:
1. Chạy server `gemini-web2api` cục bộ (mặc định `http://localhost:8081`).
2. Đảm bảo `"use_web2api": true` trong `config.json`.
3. Nếu không có Web2API, đặt `"use_web2api": false` và điền `"gemini_api_key"` trực tiếp.

#### **6. Pipeline bị gián đoạn giữa chừng, có phải chạy lại từ đầu?**
Không! Nhờ cơ chế cache, pipeline sẽ tự bỏ qua các bước đã hoàn thành (audio đã tạo, ảnh đã tải). Chỉ cần chạy lại `run_pipeline.bat` với cùng chủ đề.
