# scenes.json — tra cứu nhanh

Tên hợp lệ luôn lấy từ `make_video.py vocab`. File này giải thích cấu trúc và các bẫy.

## Khung tổng

```json
{
  "title": "How Did Ancient Humans Survive Winter?",
  "language": "en",
  "voice": "en-US-EmmaNeural",
  "scenes": [ { "chapter": "...", "frame": "...", "...": "...", "lines": [ {"text": "..."} ] } ]
}
```
`voice` tuỳ chọn (mặc định theo ngôn ngữ). Trường chỉ dành cho kịch bản: `lines`, `chapter`, `note`.
`short` (gốc) chọn câu cho bản dọc 9:16 — xem SKILL.md bước 6.

**Phụ đề in trên hình:** `"burn_subtitles": true` ở gốc scenes.json (hoặc `build --subs`, hoặc `burn_subtitles`
trong config.json làm mặc định). Phụ đề = lời thoại; muốn phụ đề khác ngôn ngữ lời đọc (vd lời Việt, phụ đề
Anh) thì thêm `"sub": "English text"` vào từng line — `sub` cũng được ghi vào file `.srt`.

## Các frame

| frame | trường | ghi chú |
|---|---|---|
| `scene` | `bg`, `elements[]` | duy nhất frame hỗ trợ `show`/`change` |
| `concept_text` | `text`, `sub` | chữ đỏ to giữa nền kem; `text` ≤ 4 từ |
| `split` | `left`, `right` (mỗi bên: `bg`, `title`, `elements[]`) | x/y trong mỗi bên tính theo NỬA khung |
| `timeline` | `title`, `events[{label, text, icon}]`, `highlight` | ≤ 6 event; `icon` là tên prop |
| `stats` | `title`, `bars[{label, value, display, color}]` | ≤ 5 bar; số liệu phải có nguồn thật |

### Khung thẻ kiểu báo (tự co giãn cho cả 16:9 và ô dọc 9:16)

Ưu tiên cho nội dung thông tin (luật, hạn nộp, số liệu, danh sách việc) — nhìn tin cậy hơn chữ to trên nền trơn,
và bản dọc vẽ lại đúng ô nên không bị cắt chữ. Chữ `*...*` trong title/quote → màu nhấn của thương hiệu.

| frame | trường | ghi chú |
|---|---|---|
| `headline` | `kicker`, `title`, `deck`, `source` | trang báo: nhãn nhỏ · tiêu đề có từ nhấn · tóm tắt |
| `stat_cards` | `title`, `cards[{label, value, note, color}]` (1–4) | `color`: accent/label/title/gray/green/hex |
| `checklist` | `title`, `items[{text, tag}]` | `step` = số mục đã tick; mục kế tiếp sáng vàng; SFX "ding" |
| `document` | `doc_type`, `number`, `date`, `issuer`, `quote`, `effective`, `source` | mọi căn cứ pháp lý; quote là tóm tắt thì ghi `source: "KTTG tóm tắt"` |
| `ledger` | `title`, `columns[]`, `rows[[ô,...]]`, `widths[]` | ô là `{text, color}` → tag màu; `step` = số dòng đã hiện |
| `deadline` | `title`, `date` "d/m/yyyy", `label`, `note` | tự đếm "Còn N ngày" từ `updated` của video |
| `compare` | `title`, `left`/`right` `{title, items[], color}` | `step` 1 → bên trái sáng, 2 → bên phải, 0 → cả hai |
| `media_card` | `src`, `title`, `caption` | ảnh thực tế trong thẻ bo góc (thay cho ảnh tràn màn hình khi ảnh không sát ý) |
| `map` | `title`, `pins[{lat, lon, label}]`, `zoom {lat, lon, z}` | bản đồ thế giới doodle; `step` = số ghim đã hiện; camera zoom vào vùng |

Dùng như cảnh chính (cảnh riêng, các câu có `step`) hoặc như `cut` của một câu:
```json
{"chapter": "Tóm tắt", "frame": "checklist", "title": "*4 việc* cần nhớ",
 "items": [{"text": "Ghi sổ doanh thu", "tag": "S1a-HKD"}, {"text": "Thông báo doanh thu"}],
 "lines": [{"text": "Tóm lại...", "step": 0}, {"text": "Một, ghi sổ.", "step": 1}, {"text": "Hai, thông báo.", "step": 2}]}
```

## Element

Chung: `id` (để tham chiếu), `x`, `y` (0..1), `scale` (mặc định 1), `flip`.
Bỏ `y` → đứng trên mặt đất của nền. Prop trên trời (`sky_props`: sun, moon, cloud, rain_cloud, clock, lightbulb, heart, question_mark, exclamation, money) mặc định y = 0.2.

| type | trường riêng |
|---|---|
| `character` | `variant`, `pose`, `expression`, `extras[]`, `holding` (prop trong `holdable_props`), `outfit` (`none`/`fur`/`shirt`/`dress`; mặc định theo variant: ancient_human→fur, archaeologist→shirt, elder→dress) |
| `prop` | `name`, `cracked` (boulder nứt = sụp đổ/mong manh) |
| `label` | `text`, `color` (red mặc định; white khi `on` vật tối), `size` (≈110 tiêu đề, 80–90 câu dài), `on` |
| `thought` | `of` (id nhân vật), `text` HOẶC `prop`, `side` |
| `arrow` | `between: [id1, id2]` hoặc `from: [x,y]`, `to: [x,y]` |
| `red_x` | — phủ cả khung/panel |
| `svg` | `markup` — chỉ khi thư viện thật sự thiếu vật; toạ độ cục bộ, gốc ở chân vật, ~cao 200px |

### Neo vị trí (ưu tiên hơn đoán x)
- `"attach": {"to": "rock", "side": "left", "gap": 20}` — đứng sát bên trái vật `rock`; nhân vật tự quay mặt về phía vật (`pushing` chạm đúng mép).
- `"above": "me"` — đặt ngay trên đầu (mây mưa, bóng đèn ý tưởng, dấu hỏi).
- label `"on": "rock"` — chữ nằm trên thân vật (boulder, sign, crate, house, hourglass hợp nhất); vết nứt tự ẩn.

## Hiện dần theo câu (chỉ frame `scene`)

```json
"lines": [
  {"text": "Câu 1 — chỉ thấy các element KHÔNG được nhắc trong show nào."},
  {"text": "Câu 2", "show": ["rock", "label1"]},
  {"text": "Câu 3", "change": {"me": {"expression": "surprise", "extras": ["shock_lines"]}}}
]
```
`change` có thể đổi mọi trường của element (pose, expression, x, holding, text...) và giữ nguyên cho các câu sau.

## Cú máy theo câu: `focus` và `cut` (B-roll)

```json
{"text": "One of his molars had a large cavity.", "focus": "t"},
{"text": "No numbing. No painkiller.", "cut": {"frame": "concept_text", "text": "NO NUMBING"}},
{"text": "Under the microscope…", "cut": {"frame": "scene", "bg": "neutral_default", "elements": [
   {"type": "prop", "name": "tooth", "x": 0.5, "scale": 2.6, "cracked": true},
   {"type": "label", "text": "TINY SCRATCHES", "y": 0.14}]}}
```
- `focus`: id nhân vật/đồ vật (của cảnh, hoặc của `cut` nếu dùng cùng) → camera đẩy vào cận cảnh (zoom ≤ 1.9),
  lướt mượt từ cú máy trước. Chỉ dùng trong frame `scene`.
- `cut`: một cảnh hoàn chỉnh bất kỳ frame (scene, concept_text, split, timeline, stats) chỉ cho câu đó; câu sau
  tự quay lại cảnh chính (giữ nguyên các show/change đã có). Chuyển cảnh nhanh (0,12s).
- Câu có `show`/`change` được một cú zoom nhẹ ("punch") để người xem chú ý thứ vừa hiện.
- Kiểm tra: `MV preview <slug> --scene N` vẽ đúng từng cú máy (có nhãn [focus]/[cut]).

## Nhiều giọng, bảng tiến độ, vẽ tay

- **Hỏi – đáp 2 giọng:** gốc scenes.json `"voices": {"chu_tiem": {"voice": "vi-VN-HoaiMyNeural", "rate": "+6%",
  "name": "Chủ tiệm", "color": "#FFC93C"}, "ke_toan": {...}}`; câu thoại `"speaker": "chu_tiem"`. Nhân vật có
  `id` trùng tên speaker → camera tự đẩy vào người đang nói; phụ đề tô màu `color` của người nói.
- **Bảng tiến độ** (video "N việc"): gốc `"progress_items": ["Ghi sổ", "Thông báo", ...]`, mỗi cảnh của việc thứ n
  ghi `"progress": n` → bảng nhỏ góc trên-trái (ẩn khi đang chèn thẻ/B-roll).
- **Vẽ tay** (bàn tay cầm bút quét qua thành phần mới hiện bằng `show`, có tiếng bút): mặc định bật cho kênh doodle,
  tắt cho thương hiệu (bật bằng `"draw_reveal": true`). Chỉ áp dụng cho element có `id`.
- Phụ đề karaoke tự động (mốc thời gian từng từ của edge-tts); `sub` khác lời đọc thì chia theo độ dài chữ.

## Bố cục đẹp

- Nhân vật chính to, rõ: `scale` 1.1–1.4 khi cảnh chỉ có 1–2 nhân vật; nhỏ hơn (0.8–0.9) chỉ khi đông người.
- 2–4 thành phần mỗi cảnh: 1 tâm điểm (nhân vật + vật tương tác) + 1–2 vật phụ ở mép (cây, đá, lều) để lấp
  khoảng trống; tránh để một nửa khung trống trơn.
- Đặt tâm điểm lệch theo quy tắc 1/3 (x ≈ 0.33 hoặc 0.66), vật phụ ở phía đối diện hoặc sát mép (x 0.08–0.15,
  0.85–0.92, có thể tràn nhẹ ra ngoài khung).
- Nền đã có chi tiết ở đường chân trời và tiền cảnh — không cần thêm quá nhiều vật nhỏ.

## Ảnh thực tế (B-roll có thật)

```
MV photo search "point of sale" --n 12      # Openverse; chỉ CC0 / Public Domain / CC BY (thêm --allow-sa nếu cần)
MV photo get <slug> 6 --name pos_receipt    # → projects/<slug>/photos/pos_receipt.jpg + .json (tác giả, giấy phép)
```
Read `cache/photo_search/last.png` để chọn ảnh (ô có đánh số). Dùng trong kịch bản:
- khung toàn màn hình (hợp làm `cut`): `{"frame": "photo", "src": "pos_receipt", "caption": "Máy tính tiền in hoá đơn tại quầy"}`
- ảnh dán polaroid trong cảnh doodle: `{"type": "photo", "src": "shop_interior", "x": 0.7, "y": 0.45, "w": 0.35, "caption": "..."}`

Ghi nguồn tự động: dòng nhỏ trên hình + mục "Nguồn ảnh" trong mô tả YouTube (publish/youtube/metadata.txt).
Quy tắc: không dùng ảnh lấy người nhận diện được làm chủ thể (giấy phép ảnh không thay cho quyền hình ảnh cá nhân);
ưu tiên ảnh đồ vật, cửa hàng, quang cảnh; tìm từ khoá tiếng Anh (Openverse ít ảnh gắn tiếng Việt); mỗi video 2–5 ảnh là đủ.

## Thương hiệu

`"brand": "<tên>"` ở gốc scenes.json → áp dụng `brands/<tên>/brand.json`: màu, font (vd KTTG dùng font nghiêm chỉnh,
không nghiêng), giọng, phụ đề, logo góc, màn kết tự động, ngưỡng độ dài, bố cục bản dọc (`vertical`: màu nền,
font, logo, dòng CTA), câu kết bản dọc (`short_outro`), mặc định đăng tải (`publish`: danh mục, playlist,
bình luận ghim, hashtag mặc định). Đọc `content_dna` trong brand.json
(giọng văn, hài hước, quy tắc pháp lý) thay cho DNA kênh doodle khi viết kịch bản cho thương hiệu đó.
Label `"color": "red"` = màu nhấn/cảnh báo của thương hiệu; `"width": 0.5` giới hạn bề ngang chữ.

## Bẫy hay gặp

- `attach.to`, `above`, `on`, `thought.of`, `arrow.between` chỉ trỏ tới element **đứng trước** trong danh sách.
- `thought.of` phải là nhân vật; label `on` phải là prop.
- Nhân vật `sleeping` nằm ngang, rộng ~400px: chừa chỗ. Đặt trên giường: `"y": 0.72` với bed scale 1.3 trên `neutral_modern`.
- `split`: mỗi nửa chỉ rộng 960px — dùng scale 0.9–1.1 và ít vật.
- Nền tối (`deep_night`, `calm_night`, `cave_interior`): chữ đỏ tự có viền đen; vật tối (cave) khó nhìn trên nền tối.
- Chữ dài tự thu nhỏ và xuống dòng (≤ 3 dòng) — nhưng chữ nhỏ trên video khó đọc: giữ ngắn.
- Mỗi câu thoại > 45 từ bị cảnh báo; cảnh > 35 giây bị cảnh báo.
- Câu cảm thán của nhân vật ("19°C?!", "3 AM?!") → dùng `thought` với `text`, đừng đặt label tự do cạnh đầu (dễ đè tóc).
- `timeline` tự cân cỡ icon (~200px); chọn icon có hình dáng dễ nhận ra khi nhỏ.
- Thumbnail: dùng 1 nhân vật to (scale 1.4–1.6) một bên, chữ cỡ 140–170 ở bên còn lại (`x` ≈ 0.62–0.68).
