# Asset SVG vẽ sẵn — quy chuẩn

Bộ vẽ (`doodle/assets.py`) ưu tiên file ở đây hơn hình vẽ bằng code. Tên file = tên trong `make_video.py vocab`.
Đọc kỹ file này trước khi vẽ asset mới.

## Phong cách (DNA kênh — bắt buộc)
- Doodle hoạt hình 2D vẽ tay: màu phẳng, khối đơn giản mập mạp, viền đen `#141414` dày 5–7px
  (vật ở xa: 3–4px hoặc không viền), nét hơi run như vẽ nhanh bằng bút lông — viền là path vẽ tay có
  chút lệch, không dùng hình học hoàn hảo làm viền.
- Chi tiết bên trong tối thiểu, phẳng (vân gỗ, vết nứt đá, nét lông). Chiều sâu chỉ bằng mảng phẳng
  sáng/tối hơn.
- CẤM: gradient, bóng đổ, filter/blur, mask, pattern, `<image>`, `<text>`, CSS, animation, ảnh thật, 3D.
- Dễ thương, đơn giản như tranh trẻ con nhưng gọn gàng, trau chuốt hơn clip-art cơ bản.
- Renderer: resvg. Dùng được: path, rect, circle, ellipse, polygon, polyline, line, g, transform,
  clipPath, opacity/fill-opacity.

## Bảng màu (color_palette_hex)
orange `#F58220` · sky_blue `#7FB5D5` · cave_light_blue `#ABD3E5` · grass_green `#4E9A45` ·
sand_tan `#D2B488` · dirt_brown `#8B5A2B` · wood_brown `#7A4F2A` · rock_gray `#8A8A8A` ·
night_navy `#283A6E` · deep_indigo `#322B5E` · red_text `#E0302B` · yellow `#F4C430` ·
purple_mauve `#8B7CB0` · cream `#F5F1E6` · white `#FFFFFF` · ink `#141414`
Phụ: light_wood `#A0683A` · dark_gray `#5A5A5E` · light_gray `#BDBDBD` · blue `#4FA9E0` · pink `#F29BB0` ·
leaf_dark `#3C7A36`.

## Đồ vật — `props/<name>.svg`
Hợp đồng toạ độ (bộ vẽ đặt vật theo đúng các số này):
- **Vật đứng đất** (mặc định): gốc (0,0) = điểm giữa đáy nơi vật chạm đất, y âm hướng lên. Vật nằm trong
  x ∈ [-W, W], y ∈ [-H, 0]; đáy vật chạm y = 0.
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-W} {-H} {2W} {H}" width="{2W}" height="{H}">`
- **Vật CENTER** (trên trời / biểu tượng): gốc (0,0) = tâm vật; vật nằm trong x ∈ [-W, W], y ∈ [-H/2, H/2].
  `viewBox="{-W} {-H/2} {2W} {H}"`
- Toàn bộ hình vẽ đặt trong một `<g>`. Vật nên chiếm gần hết khung.
- **grip (x, y)**: điểm bàn tay nhân vật nắm vào (cán đuốc, quai cốc, mép sách...) — phần cầm nắm phải nằm
  đúng toạ độ này.
- **label_area (cx, cy, rộng)**: vùng chữ sẽ được viết đè lên — giữ vùng này trơn, một màu, không chi tiết.
- Động vật / xe: quay mặt sang PHẢI.
- Mỗi file ≤ ~12 KB.

## Tấm nền — `backgrounds/<bg>.svg`
- 1920×1080: `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">`.
- Sân khấu trống: KHÔNG người, KHÔNG động vật, KHÔNG chữ; không vẽ trăng/mặt trời (là prop riêng).
- **Đường mặt đất** (mép trên của nền đi được) phải nằm ở đúng `ground_top` (±10) trên toàn bề ngang;
  chân nhân vật đứng ở `feet_y`. Dải từ ground_top đến ground_top+100 ở 70% giữa khung phải thoáng, trơn.
- Giữ 20% phía trên yên tĩnh (tiêu đề nằm đó — KHÔNG đặt mây/chi tiết ở vùng giữa phía trên) và vùng giữa
  (x 15–85%, y 25% → ground_top) thoáng để nhân vật nổi bật. Chi tiết dồn về đường chân trời, hai mép
  trái/phải và tiền cảnh dưới cùng.
- Khi dùng cho khung `split`, tấm nền bị cắt lấy phần giữa rộng 960px — phần giữa cũng phải đẹp.
- Mỗi file ≤ ~45 KB.

## Tự kiểm tra
Từ `h2dev_pipeline/`:
```
.venv/Scripts/python.exe -m doodle.render_svg --sheet <thư_mục>/_check.png <file1.svg> <file2.svg> ...
```
Xem `_check.png` bằng Read, sửa rồi xoá `_check.png` và các file `.png` sinh ra (chỉ giữ `.svg`).
