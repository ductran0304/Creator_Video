---
name: tao-video
description: Tạo trọn một video doodle cho kênh H2Dev (người tiền sử, lịch sử loài người) từ một chủ đề hoặc một file kịch bản có sẵn — Claude viết kịch bản kèm mô tả hình từng cảnh (scenes.json) và SEO (seo.json), tự kiểm tra, tự xem ảnh preview để sửa, rồi dựng video dài 16:9 + bản dọc 9:16 có giọng đọc, nhạc nền, phụ đề, thumbnail/cover và gói metadata đăng YouTube, Shorts, TikTok, Reels bằng make_video.py. Dùng khi người dùng muốn làm/tạo video mới, viết kịch bản video doodle, dựng lại video từ kịch bản, hoặc gõ /tao-video — kể cả khi họ chỉ đưa một chủ đề ("làm video về cách người tiền sử ngủ").
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
Nếu thương hiệu có `brands/<tên>/topics.md`: đọc để chọn chủ đề (người dùng nói "video số N"/"video tiếp theo" →
chủ đề `[ ]` đầu tiên trong Hàng đợi), tránh trùng chủ đề đã làm; làm xong thì đánh dấu `[x]` kèm slug và ngày.

1. Đọc `brands/h2dev/knowledge_base.json`: `content_dna` (hook, nhịp câu, mạch truyện, luật dẫn chứng, luật hài, kết), `viral_topic_angles`, `visual_style_dna`, `seo_dna`.
2. Đọc phần viết kịch bản trong `brands/h2dev/master_prompt.md` (STAGE 1–2) để bắt đúng giọng văn.
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
- Con số / thuật ngữ quan trọng → `concept_text`. So sánh xưa–nay → `split`. Mốc thời gian → `timeline`. Số liệu → `stats`. Phủ định → `red_x`. Suy nghĩ/tưởng tượng → `thought`. Địa danh → `map` (ghim theo toạ độ thật).
- **Nội dung thông tin** (văn bản pháp lý, hạn nộp, danh sách việc, bảng so sánh nhiều tiêu chí, số liệu) → khung thẻ
  kiểu báo trong reference.md: `document`, `deadline`, `checklist` (tick dần bằng `step`), `ledger`, `stat_cards`,
  `compare`, `headline`, `media_card`. Thương hiệu: mọi căn cứ pháp lý phải có một thẻ `document`.
- **Ẩn dụ xuyên suốt:** chọn 1 hình ảnh đời thường cho ý chính (vd "gói cước trọn gói → tính theo đồng hồ") và
  nhắc lại ở 2–3 chỗ. Video dạng "N việc": thêm `progress_items` + `progress` để người xem luôn biết đang ở đâu.
- Câu cuối vọng lại câu mở đầu (kết vòng) — người xem Shorts hay xem lại khi đoạn cuối nối vào đoạn đầu.
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

## Bước 3b — Kế hoạch footage (hình ảnh thật, bắt buộc với thương hiệu)

Hình doodle và thẻ lặp lại nhiều thì video nhàm. Trước khi chốt scenes.json, lập danh sách footage cho từng cảnh:
- **Tên riêng → logo** (Shopee, TikTok Shop, Zalo, ngân hàng, eTax Mobile...): phần tử `logo` trong cảnh hoặc khung
  `logo_row`. Logo lưu một lần ở thư viện dùng chung (`--shared`) để các video sau dùng lại.
- **Mỗi văn bản pháp luật → `doc_page`**: ảnh trang thật từ PDF (vanban.chinhphu.vn / datafiles.chinhphu.vn),
  khoanh đúng điều khoản; câu đầu `step: 0` (toàn trang), câu sau `step: 1` (camera zoom vào vùng khoanh).
  PDF có lớp chữ: `--find "cụm từ"` trả sẵn toạ độ; PDF scan: Read ảnh trang rồi tự đặt `highlight [x,y,w,h]` (0..1).
- **Hành động đời thường → `video`** (clip Pexels 3–8 giây, làm `cut`): quét QR, đếm tiền, đóng gói, xưởng may,
  dãy trọ, chợ... Tìm bằng từ khoá tiếng Anh. Hoặc ảnh thật (`photo`, `media_card`).
- **Thao tác trên ứng dụng → `phone_screen`** (màn hình vẽ mô phỏng, KHÔNG chụp tài khoản thật).
- **Câu đùa → meme** (1–2 lần/video, đúng DNA hài nhẹ): `meme_expect` (Kỳ vọng vs Thực tế), `meme_choice`
  (lắc đầu/gật đầu), `meme_pov`, `meme_twist` (con dấu PLOT TWIST); câu thoại thêm `"fx": "shake"` để rung,
  `"sfx": ["ting"|"boom"|"scratch"|"crickets"]` cho âm thanh meme.
- Đổi nền theo bối cảnh (xưởng may, văn phòng công ty, kho online, dãy trọ, chợ, ngân hàng...) và nhân vật
  (`director_male`, `director_female`, `packer`, `shipper`...) — không để một nền lặp 3 cảnh liền.

Lệnh:
```
MV footage search "packing online orders" --kind video        # Pexels (mặc định), bảng xem trước cache/footage_search/last.png
MV footage search "Shopee" --kind logo                        # Wikimedia
MV footage search "vietnam market" --kind photo --source openverse
MV footage get <slug> <số> --name dong_goi [--shared]
MV footage pdf <slug> <url.pdf> --page 4 --name doc_nd117_p4 --title "Nghị định 117/2025/NĐ-CP, trang 4"
```
Read bảng xem trước trước khi chọn — chọn đúng ý câu thoại, không chọn cho có. Giấy phép chỉ nhận: Pexels, CC0,
Public Domain, CC BY (BY-SA với --allow-sa). KHÔNG dùng: meme có người thật/nhân vật có bản quyền, GIF GIPHY/Tenor,
clip cắt từ TV/YouTube/TikTok người khác, ảnh CC-NC/CC-ND, ảnh người nhận diện được trong ngữ cảnh tiêu cực,
quốc huy/con dấu. Mô tả video tự ghi nguồn footage và câu miễn trừ nhãn hiệu. Mục tiêu: ≥ 30% số câu có footage
thật (`validate` báo tỷ lệ).

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

## Bước 6 — Bản dọc 9:16 + `projects/<slug>/seo.json` (đủ cho 4 nền tảng)

**Bản dọc** (Shorts · TikTok · Reels dùng chung một file) — bố cục dọc riêng: nhãn chương + logo · tiêu đề `hook`
cố định ở trên (giữ ngữ cảnh) · ô nội dung (khung thẻ vẽ lại đúng ô, cảnh doodle được cắt vừa) · thanh tiến độ ·
phụ đề karaoke to. Mỗi video dài nên có **2–3 bản dọc**:
```json
"shorts": [
  {"id": "main", "lines": ["1.1-1.4", "3.2-3.4"], "hook": "Doanh thu *dưới 1 tỷ*: vẫn phải làm *4 việc*"},
  {"id": "hoi_dap_1", "kicker": "Hỏi nhanh – đáp gọn", "hook": "Bán *dưới 1 tỷ* là khỏi làm gì?",
   "scenes": [ {cảnh viết riêng 20–40s: chủ tiệm hỏi (speaker), kế toán đáp 2–3 ý, 1–2 thẻ cut} ]}
]
```
(`"short": {...}` một bản vẫn dùng được.) `*từ*` trong hook → màu nhấn; không có `*` thì tự nhấn các con số.
Bản cắt: chọn 25–45 giây (`validate` báo ước lượng) — câu đầu tiên phải là câu gây chú ý nhất, không câu dẫn.
- `lines`: `"S"` cả cảnh · `"S.L"` một câu · `"S.L-M"` / `"S.L-S.M"` dải câu (đánh số từ 1, như `preview --scene`).
  Mặc định: cả cảnh 1 (cold open). Chọn 30–60 giây (`validate` báo ước lượng): cold open + 1–2 ý "đắt" nhất tự
  đứng được một mình (con số, mốc ngày, câu twist) — câu đầu phải gây chú ý ngay, không cần câu dẫn.
- Câu kết tự thêm (`outro` → `short_outro` của thương hiệu → "Xem bản đầy đủ trên kênh nhé"); thương hiệu có màn
  kết thì hiện màn kết đó.

**seo.json** — mỗi nền tảng một mục; mục nào bỏ trống thì tự suy ra từ `youtube`:
```json
{
  "youtube": {
    "titles": ["3 tiêu đề ≤ 70 ký tự theo seo_dna.title_rules — cái đầu là tiêu đề chính"],
    "description": "2 dòng đầu chứa từ khoá chính ... 

Chapters:
{{chapters}}

Sources:
- nguồn thật ...",
    "tags": ["20–35 tag, tổng ≤ 500 ký tự"], "hashtags": ["3–5 hashtag"],
    "category": "Education", "playlist": "...", "pinned_comment": "câu hỏi mời bình luận + CTA"
  },
  "youtube_shorts": {"title": "≤ 100 ký tự, từ khoá đầu câu", "description": "1–2 câu + Xem bản đầy đủ: {{long_url}}", "hashtags": ["#... ", "#shorts"]},
  "tiktok": {"caption": "câu móc + ý chính + câu hỏi mời bình luận, ≤ 300 ký tự", "hashtags": ["3–6 hashtag: rộng + ngách"]},
  "reels":  {"caption": "dòng đầu ≤ 125 ký tự (phần sau bị ẩn) + chi tiết + CTA", "hashtags": ["≤ 5 hashtag"]},
  "long_url": "",
  "thumbnail": {"frame": "scene", "...": "you_main biểu cảm mạnh + chữ ≤ 4 từ, cỡ 140–170"},
  "cover": {"...": "tuỳ chọn — ô giữa của cover 9:16 bản đầu; mặc định là cú máy đầu của bản dọc"},
  "shorts": {"hoi_dap_1": {"youtube_shorts": {...}, "tiktok": {...}, "reels": {...}, "cover": {...}}}
}
```
Bản dọc đầu tiên dùng các mục gốc `youtube_shorts/tiktok/reels`; bản khác đọc `shorts.<id>` (viết caption riêng).
- `{{chapters}}` → mốc thời gian thật; `{{long_url}}` → `long_url` (điền sau khi đăng video dài rồi chạy
  `MV publish <slug>` để cập nhật mô tả Shorts/TikTok/Reels mà không dựng lại video).
- Viết caption riêng cho từng nền tảng (giọng TikTok ngắn, đời hơn; Reels có dòng đầu mạnh), đừng chép y mô tả
  YouTube. Thương hiệu có quy tắc pháp lý: giữ câu "thông tin tham khảo, cập nhật …" trong mọi caption.
- Xem thử: `MV thumbnail <slug>` → Read `preview/thumbnail.png` và `preview/cover.png` (chữ to, đọc được khi thu nhỏ,
  không đè nhân vật).

## Bước 7 — Dựng video + gói đăng tải

```
MV build <slug>               # video dài 1080p + bản dọc 1080x1920 + publish/ (~0.7× thời lượng trên máy 6 nhân)
MV build <slug> --draft       # bản nháp nhanh (cờ --nhap) → publish/draft/
MV build <slug> --no-short    # chỉ video dài · --short-only: chỉ dựng lại bản dọc
MV publish <slug>             # chỉ ghi lại metadata (sau khi sửa seo.json / điền long_url)
```
Chạy build ở chế độ nền (run_in_background) vì video dài mất vài phút; báo người dùng là đang dựng. Build tự dùng
cache: sửa vài câu rồi build lại chỉ làm lại phần thay đổi; bản dọc dùng lại giọng đọc và hình của video dài.
Build lỗi TTS (mạng) → chạy lại; lỗi khác → đọc thông báo, sửa, chạy lại. Đọc các `[⚠]` cuối log (giới hạn
tiêu đề, tags, hashtag, độ dài caption từng nền tảng) và sửa seo.json → `MV publish <slug>`.

Kết quả trong `projects/<slug>/publish/`:
```
PUBLISH.md            # mở file này: nội dung copy-dán cho từng nền tảng + checklist trước khi đăng
publish.json          # cùng dữ liệu, dạng máy đọc
youtube/        <slug>.mp4 · thumbnail.png · <slug>.srt · metadata.txt
short/          <slug>_short.mp4 · cover.png · .srt · youtube_shorts.txt · tiktok.txt · reels.txt   (bản dọc đầu)
short_<id>/     <slug>_<id>.mp4 · cover.png · ...                                                (các bản khác)
```

**Rút kinh nghiệm từ số liệu thật:** trước khi viết video mới, chạy `MV stats show --brand <tên>` (nếu đã có số liệu)
và áp dụng: lặp lại hook/định dạng của video giữ chân tốt nhất, tránh kiểu mở đầu của video kém nhất. Người dùng
nhập số liệu bằng `MV stats import "<Table data.csv>" --brand <tên>` (YouTube Studio → Analytics → Advanced mode → Export).

## Bước 8 — Báo kết quả

Ngắn gọn cho người dùng:
- đường dẫn `projects/<slug>/publish/PUBLISH.md` + video dài / bản dọc và thời lượng từng bản;
- tiêu đề chính YouTube + tiêu đề Shorts, caption TikTok/Reels (tóm tắt);
- danh sách dẫn chứng/số liệu đã dùng để họ kiểm chứng trước khi đăng;
- cảnh báo còn lại (nếu có) và gợi ý xem lại video trước khi upload.
