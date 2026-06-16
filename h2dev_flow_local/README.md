# H2Dev Flow — Công cụ sinh ảnh tự động cục bộ (Local Tool)

Công cụ này tự động kết nối vào một tab Google Flow đang mở trên trình duyệt Chrome thực tế của bạn qua cổng gỡ lỗi (`9222`), tự động hóa việc nhập prompt từ file `prompts.txt`, chờ ảnh được sinh ra và tự động tải về ổ đĩa cứng của bạn.

---

## 🛠 Hướng dẫn chuẩn bị và khởi chạy (Chỉ cần 3 bước)

### **Bước 1: Khởi động Chrome ở chế độ Debug**
1. Đóng hoàn toàn các cửa sổ Chrome thông thường đang chạy (nếu có).
2. Chạy file **`run_chrome.bat`** (Click đúp chuột).
3. Một trình duyệt Chrome mới sẽ mở ra với thư mục dữ liệu sạch (`.chrome_profile`).
4. Trên trình duyệt này, bạn truy cập địa chỉ: **[Google Labs Flow](https://labs.google/fx/tools/flow)**.
5. Đăng nhập tài khoản Google của bạn có quyền truy cập vào Flow.

### **Bước 2: Cập nhật danh sách Prompt**
1. Mở file **`prompts.txt`**.
2. Dán danh sách prompt của bạn vào đây (mỗi dòng một prompt). Bạn có thể copy-paste trực tiếp danh sách prompt có kèm mốc thời gian (timestamp) tạo từ file `ancient_humans_master_prompt.md`.
3. Lưu file lại.

### **Bước 3: Chạy Tool tự động hóa**
1. Chạy file **`run_tool.bat`** (Click đúp chuột).
2. Trong lần đầu tiên chạy, script sẽ tự động tải và tạo môi trường ảo Python (`.venv`), cài đặt thư viện cần thiết (`playwright`, `requests`). Quá trình này diễn ra tự động khoảng 1-2 phút.
3. Sau khi cài đặt hoàn tất, script sẽ tự kết nối tới tab Chrome đã mở ở Bước 1 và lần lượt xử lý các prompt trong hàng đợi.

*Ảnh tạo xong sẽ tự động được lưu vào thư mục **`outputs/`** bên trong thư mục này.*

---

## 📂 Giải thích cấu trúc thư mục

*   `run_chrome.bat`: File bật trình duyệt Chrome Debug.
*   `run_tool.bat`: File cài đặt và chạy tool chính.
*   `main.py`: Mã nguồn tự động hóa bằng Python + Playwright.
*   `prompts.txt`: Danh sách các câu lệnh vẽ hình đầu vào.
*   `requirements.txt`: Các thư viện Python cần dùng.
*   `outputs/`: Thư mục chứa các ảnh thành phẩm (tự tạo ra sau khi chạy).
*   `.chrome_profile/`: Profile chứa lịch sử đăng nhập Chrome của bạn (tự tạo ra sau khi chạy Chrome Debug).

---

## ⚙ Tùy chỉnh các thông số trong `main.py`

Bạn có thể chỉnh sửa các thông số sau bằng cách mở file `main.py` bằng notepad hoặc bất kỳ công cụ soạn thảo nào:

*   `DELAY_MIN` & `DELAY_MAX`: Thời gian chờ ngẫu nhiên giữa 2 ảnh liên tiếp để tránh bị Google phát hiện sử dụng bot (Mặc định: nghỉ ngẫu nhiên từ 5 đến 15 giây).
*   `MAX_WAIT_IMAGE`: Thời gian chờ tối đa cho một bức ảnh sinh xong (Mặc định: 240 giây / 4 phút).
*   `OUTPUT_DIR`: Thư mục lưu trữ ảnh (Mặc định: `"outputs"`).

---

## ❓ Câu hỏi thường gặp & Khắc phục lỗi

#### **1. Lỗi: "Khong the ket noi den Chrome. Vui long chay file 'run_chrome.bat'..."**
*   **Nguyên nhân:** Cổng gỡ lỗi `9222` của Chrome chưa được mở hoặc bị chặn.
*   **Giải pháp:** Hãy đảm bảo rằng cửa sổ Chrome được mở bằng file `run_chrome.bat` đang hoạt động. Nếu bạn đã có cửa sổ Chrome thường đang mở, hãy tắt hết các tab đó đi trước rồi chạy lại `run_chrome.bat`.

#### **2. Lỗi: "Khong tim thay o nhap prompt tren giao dien"**
*   **Nguyên nhân:** Giao diện Google Flow bị thay đổi cấu trúc thiết kế, hoặc trang chưa tải xong.
*   **Giải pháp:** Đảm bảo tab Google Flow của bạn đã mở sẵn dự án (project) hoặc đã xuất hiện ô viết prompt trên màn hình trước khi chạy `run_tool.bat`.

#### **3. Có thể mở F12 (DevTools) khi tool đang chạy không?**
*   **Không.** Nếu bạn mở cửa sổ F12, Chrome sẽ ngắt kết nối gỡ lỗi của tool (`CDP`) và tool sẽ dừng hoạt động. Vui lòng tắt DevTools trước khi khởi chạy tool.
