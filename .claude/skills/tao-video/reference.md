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

## Các frame

| frame | trường | ghi chú |
|---|---|---|
| `scene` | `bg`, `elements[]` | duy nhất frame hỗ trợ `show`/`change` |
| `concept_text` | `text`, `sub` | chữ đỏ to giữa nền kem; `text` ≤ 4 từ |
| `split` | `left`, `right` (mỗi bên: `bg`, `title`, `elements[]`) | x/y trong mỗi bên tính theo NỬA khung |
| `timeline` | `title`, `events[{label, text, icon}]`, `highlight` | ≤ 6 event; `icon` là tên prop |
| `stats` | `title`, `bars[{label, value, display, color}]` | ≤ 5 bar; số liệu phải có nguồn thật |

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

## Bố cục đẹp

- Nhân vật chính to, rõ: `scale` 1.1–1.4 khi cảnh chỉ có 1–2 nhân vật; nhỏ hơn (0.8–0.9) chỉ khi đông người.
- 2–4 thành phần mỗi cảnh: 1 tâm điểm (nhân vật + vật tương tác) + 1–2 vật phụ ở mép (cây, đá, lều) để lấp
  khoảng trống; tránh để một nửa khung trống trơn.
- Đặt tâm điểm lệch theo quy tắc 1/3 (x ≈ 0.33 hoặc 0.66), vật phụ ở phía đối diện hoặc sát mép (x 0.08–0.15,
  0.85–0.92, có thể tràn nhẹ ra ngoài khung).
- Nền đã có chi tiết ở đường chân trời và tiền cảnh — không cần thêm quá nhiều vật nhỏ.

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
