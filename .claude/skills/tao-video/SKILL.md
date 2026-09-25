---
name: tao-video
description: Tạo trọn một video doodle cho kênh H2Dev (người tiền sử, lịch sử loài người) từ một chủ đề hoặc một file kịch bản có sẵn — Claude viết kịch bản kèm mô tả hình từng cảnh (scenes.json) và SEO (seo.json), tự kiểm tra, tự xem ảnh preview để sửa, rồi dựng MP4 có giọng đọc, nhạc nền, phụ đề, thumbnail bằng make_video.py. Dùng khi người dùng muốn làm/tạo video mới, viết kịch bản video doodle, dựng lại video từ kịch bản, hoặc gõ /tao-video — kể cả khi họ chỉ đưa một chủ đề ("làm video về cách người tiền sử ngủ").
---

# /tao-video — từ chủ đề đến video hoàn chỉnh

Đầu vào (`$ARGUMENTS`): một chủ đề, HOẶC đường dẫn file kịch bản có sẵn. Cờ tuỳ chọn:
- `--vi` / `--en`: ngôn ngữ lời thoại (mặc định: theo ngôn ngữ người dùng đang dùng để yêu cầu; hỏi nếu không rõ).
- `--ngan`: bản thử ngắn ~250–400 từ, 6–10 cảnh (dùng để thử nhanh).
- `--nhap`: chỉ dựng bản nháp 960×540 (`build --draft`).
- `--phude`: in phụ đề lên hình (`"burn_subtitles": true`). Lời Việt mà cần phụ đề tiếng Anh → thêm `sub` (bản dịch)
  cho từng line.

Toàn bộ công cụ nằm trong `h2dev_pipeline/`. Chạy mọi lệnh từ thư mục đó với Python của venv:
- Windows: `.venv\Scripts\python.exe` · macOS/Linux: `.venv/bin/python`
- Chưa có `.venv` → `python -m venv .venv` rồi `<python> -m pip install -r requirements.txt`.

Gọi tắt dưới đây: `MV = <python> make_video.py`.

## Bước 1 — Nạp DNA kênh (bắt buộc, trước khi viết chữ nào)

Video cho **thương hiệu** (vd KTTG — kế toán thuế): dùng `brands/<tên>/brand.json` → `content_dna` làm DNA
(khán giả, giọng văn, hài hước, cấu trúc, quy tắc pháp lý), ghi `"brand": "<tên>"` trong scenes.json, bỏ qua
các quy tắc riêng của kênh người tiền sử (ngôi "you", dẫn chứng khảo cổ). Với nội dung pháp lý: đối chiếu mọi
số hiệu văn bản / mốc ngày / con số bằng WebSearch tại thời điểm làm video và liệt kê căn cứ trong seo.json.

1. Đọc `h2dev_knowledge_base.json`: `content_dna` (hook, nhịp câu, mạch truyện, luật dẫn chứng, luật hài, kết), `viral_topic_angles`, `visual_style_dna`, `seo_dna`.
2. Đọc phần viết kịch bản trong `../ancient_humans_master_prompt.md` (STAGE 1–2) để bắt đúng giọng văn.
3. Chạy `MV vocab` để có danh sách tên hợp lệ (frame, bg, variant, pose, expression, prop...). Chỉ dùng tên có trong danh sách này.
4. Đọc [reference.md](reference.md) (cấu trúc scenes.json + lỗi hay gặp) và `examples/demo_sleep/scenes.json` làm mẫu định dạng.

## Bước 2 — Lên dàn ý

- Chọn góc viral từ `viral_topic_angles` và một tiêu đề làm việc.
- Dàn ý theo `narrative_arc`: Hook (2nd person, giác quan) → Reframe (số liệu hiện đại) → Evidence stack → Reconstruct → Counterintuitive twist → Modern mirror → Echo closing (câu cuối vọng lại câu đầu).
- **Dẫn chứng:** ghi ra ≥3 nhà nghiên cứu / nghiên cứu / di chỉ CÓ THẬT mà bạn chắc chắn (tên, năm, phát hiện chính). Không chắc thì bỏ, tuyệt đối không bịa tên hay con số. Số liệu trong khung `stats` phải có nguồn thật.
- Chia dàn ý thành 4–7 chapter.
- **Cold open (hook 20–30 giây đầu) — bắt buộc**, đứng TRƯỚC phần hook giác quan của `content_dna`:
  1. Mở bằng khoảnh khắc cụ thể, gây sốc nhất trong cả câu chuyện (một người, một nơi, một con số) — câu đầu
     tiên phải có hình ảnh mạnh ("Fourteen thousand years ago… someone pushed a sharp stone into his tooth").
  2. 1–2 câu cực ngắn tăng kịch tính ("No numbing. No painkiller." / "And somehow, it worked.").
  3. Hứa hẹn điều người xem sẽ biết ("This is the story of how…") + một câu "móc" bí ẩn dẫn tới bước ngoặt
     của video ("And why… their teeth were healthier than yours.").
  4. 6 câu đầu = 6 cú máy khác nhau (focus + cut). Sau cold open mới vào hook giác quan ngôi thứ 2.
- Nói với người dùng 2–4 dòng: tiêu đề, góc tiếp cận, các nguồn dẫn chứng chính — rồi làm tiếp, không cần chờ (trừ khi họ yêu cầu duyệt trước).

Nếu đầu vào là **file kịch bản có sẵn**: giữ NGUYÊN lời thoại (chỉ tách câu/cảnh, bỏ timestamp hoặc chú thích), phần việc còn lại là thiết kế hình.

## Bước 2b — Vẽ thêm hình còn thiếu (chỉ khi thật sự cần)

Thư viện lớn dần qua từng video: luôn kiểm tra `MV vocab` trước. Chỉ vẽ mới khi một hình là **trọng tâm
của ý đang kể** mà không vật có sẵn nào thay được (vd video về kim khâu bằng xương cần `bone_needle`;
đừng vẽ mới chỉ để trang trí). Tối đa ~8 asset mỗi video, gộp **một lần gọi** duy nhất.

1. Đăng ký từng asset (tên tiếng Anh, chữ thường, `_`):
   ```
   MV asset new bone_needle --w 40 --h 160 --desc "kim khâu bằng xương có lỗ xỏ chỉ" --grip 0,-60
   MV asset new mammoth_bone_hut --w 200 --h 260 --desc "lều khung xương voi ma mút phủ da thú"
   MV asset new ice_age_camp --bg --ground-top 799 --feet-y 839 --sky "#9DB4C8" --desc "trại mùa đông kỷ băng hà"
   ```
   Kích thước theo khung 1080px, so với nhân vật cao ~450px ở scale 1 (xem bảng kích thước vật có sẵn trong
   `MV vocab` để ước lượng). `--center` cho vật trên trời/biểu tượng; `--grip X,Y` cho vật cầm tay;
   `--label CX,CY,W` nếu sẽ viết chữ lên vật.
2. Gọi **một** subagent `doodle-illustrator` (Agent tool, subagent_type `doodle-illustrator` — chạy bằng
   Sonnet) với danh sách tên + mô tả hình chi tiết cho từng asset (hình dáng, màu chính, chi tiết đặc trưng,
   hướng quay mặt). Có thể chạy nền trong lúc viết kịch bản.
   Nếu báo "Agent type 'doodle-illustrator' not found" (agent mới chỉ được nạp khi mở phiên Claude Code mới):
   gọi `general-purpose` với `model: "sonnet"` và mở đầu prompt bằng "Đọc và làm đúng quy trình trong
   `.claude/agents/doodle-illustrator.md`".
3. Khi agent xong: `MV asset check <tên...>` rồi Read `doodle/assets/_asset_check.png`. Chưa đạt → nhắn tiếp
   cho chính agent đó (SendMessage) nêu cụ thể cần sửa gì; tối đa 1 vòng, sau đó dùng vật có sẵn thay thế.
4. Asset mới tự xuất hiện trong `MV vocab` và dùng được ngay như vật có sẵn. Báo người dùng những asset
   đã thêm (chúng được commit cùng repo để các video sau dùng lại).

## Bước 3 — Viết `projects/<slug>/scenes.json`

`<slug>`: chữ thường không dấu, nối bằng `_` (vd `ancient_humans_winter`). Nếu thư mục đã có `scenes.json` thì hỏi người dùng trước khi ghi đè.

**Lời thoại** (theo `content_dna`):
- 1500–2400 từ (bản `--ngan`: 250–400), ngôi thứ 2 ("you" / "bạn"), không "we/I/chúng ta/tôi".
- Mỗi `line` là 1–2 câu nói tự nhiên (≤ 30 từ); nhịp "câu ngắn. câu ngắn. một câu dài hơn. câu hỏi?".
- Lời đọc thuần: không ngoặc, không chú thích hình, không markdown. Viết số theo cách muốn được đọc khi dễ gây nhầm ("three hundred thousand years" hoặc "300,000 years" đều được; năm dùng số).
- Hài khô kiểu deadpan theo `humor_rule`, không gượng.

**Hình** (theo `visual_style_dna`):
- 25–40 cảnh (bản ngắn: 6–10), mỗi cảnh 2–6 câu, ≈ 10–30 giây; mỗi cảnh MỘT ý hình rõ ràng.
- "Abstract → concrete": ý trừu tượng thành vật cụ thể có chữ trên vật (`label` + `on`), vd "survival" → you_main đẩy boulder chữ "SURVIVAL".
- Con số / thuật ngữ quan trọng → `concept_text`. So sánh xưa–nay → `split`. Mốc thời gian → `timeline`. Số liệu → `stats`. Phủ định → `red_x`. Suy nghĩ/tưởng tượng → `thought`.
- `you_main` (tóc cam) là "bạn"; `ancient_human` là tổ tiên; `archaeologist` khi nói về nhà nghiên cứu/khai quật.
- Nền theo cảm xúc (`backgrounds`). Đừng để cùng frame hoặc cùng bg quá 3 cảnh liền nhau.
- **Nhịp hình (B-roll): cứ 3–5 giây một thay đổi.** Mỗi câu nên là một "cú máy" khác câu trước:
  `focus` (camera đẩy vào vật/nhân vật đang được nhắc), `cut` (chèn một hình minh hoạ riêng cho câu đó — con số,
  vật cận cảnh, so sánh, cảnh tưởng tượng — rồi quay lại), hoặc `show`/`change`. Cảnh chính giữ bối cảnh;
  B-roll minh hoạ đúng từ khoá của câu. `validate` cảnh báo khi hình đứng yên quá 7 giây.
- Câu dài > 10 giây thì tách đôi để đổi hình giữa chừng.
- Dùng neo `attach` / `above` / label `on` thay vì đoán toạ độ `x` cho các vật liên quan nhau.
- Chữ trên hình: IN HOA, ≤ 5 từ, cùng ngôn ngữ với lời thoại.
- Gắn `"chapter": "..."` vào cảnh mở đầu mỗi chapter (cảnh 1 luôn có chapter).

Viết file bằng công cụ Write. JSON gọn: mỗi element một dòng.

## Bước 4 — Kiểm tra và sửa đến khi sạch

```
MV validate <slug>
```
- Sửa hết `[LỖI]` (lỗi báo kèm danh sách tên hợp lệ).
- Xử lý `[⚠]` hợp lý: độ dài kịch bản, ngôi thứ nhất, thiếu dẫn chứng, cảnh quá dài, tràn khung. Cảnh báo độ dài/số cảnh là bình thường với `--ngan`.

## Bước 5 — Tự xem preview và sửa hình

```
MV preview <slug>                # → projects/<slug>/preview/sheet_*.png (20 cảnh/bảng, có số cảnh)
MV preview <slug> --scene N      # các bước hiện dần của cảnh N
```
Đọc (Read) từng `sheet_*.png` và soi từng cảnh:
- vật/nhân vật chồng lên nhau sai, chữ đè lên nhân vật, chữ tràn hoặc quá nhỏ;
- nhân vật quay lưng về phía vật nó đang tương tác; biểu cảm sai cảm xúc lời thoại;
- bố cục trống trải hoặc lệch hẳn một bên; nhiều cảnh liền nhau trông giống hệt nhau.

Sửa `scenes.json` → validate → preview lại. Tối đa 3 vòng; cảnh nào vẫn chưa đẹp thì đơn giản hoá (bớt vật, dùng frame chữ). Kiểm tra `--scene N` cho các cảnh có `show`/`change` phức tạp.

## Bước 6 — Viết `projects/<slug>/seo.json`

```json
{
  "titles": ["3 tiêu đề < 70 ký tự theo seo_dna.title_rules"],
  "description": "Theo seo_dna.description_structure ... \n\nChapters:\n{{chapters}}\n\nSources:\n- tên nguồn thật ...",
  "tags": ["25–40 tag"],
  "hashtags": ["#15–25 hashtag"],
  "thumbnail": {"frame": "scene", "bg": "...", "elements": ["... you_main biểu cảm mạnh + chữ ≤ 4 từ, cỡ 140–170"]}
}
```
`{{chapters}}` được build tự thay bằng mốc thời gian thật. Xem thử thumbnail: `MV thumbnail <slug>` rồi Read ảnh `preview/thumbnail.png`; chữ phải to, đọc được khi thu nhỏ, không đè nhân vật.

## Bước 7 — Dựng video

```
MV build <slug>            # bản chuẩn 1080p (~0.7× thời lượng video trên máy 6 nhân)
MV build <slug> --draft    # bản nháp nhanh (cờ --nhap)
```
Chạy build ở chế độ nền (run_in_background) vì video dài mất vài phút; báo người dùng là đang dựng. Build tự dùng cache: sửa vài câu rồi build lại chỉ làm lại phần thay đổi.
Build lỗi TTS (mạng) → chạy lại; lỗi khác → đọc thông báo, sửa, chạy lại.

## Bước 8 — Báo kết quả

Ngắn gọn cho người dùng:
- đường dẫn `projects/<slug>/output/` (`<slug>.mp4`, `.srt`, `thumbnail.png`, `youtube_metadata.txt`), thời lượng video;
- 3 tiêu đề gợi ý;
- danh sách dẫn chứng/số liệu đã dùng để họ kiểm chứng trước khi đăng;
- cảnh báo còn lại (nếu có) và gợi ý xem lại video trước khi upload.
