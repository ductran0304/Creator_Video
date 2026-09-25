"""Màu theo thương hiệu. Mặc định = DNA kênh doodle (chữ đỏ trên nền kem); thương hiệu khác (vd KTTG) gọi
set_theme() trước khi vẽ để đổi màu tiêu đề, chữ trên hình, dấu X và nền giấy."""
from .palette import C

DEFAULT = {
    "title": C["red_text"],    # chữ tiêu đề/khung chữ lớn/timeline/stats
    "label": C["red_text"],    # label mặc định trên hình
    "alert": C["red_text"],    # dấu X đỏ
    "paper": C["cream"],       # nền giấy (neutral_default, khung chữ)
    "highlight": C["yellow"],  # điểm sáng (timeline highlight...)
}
T = dict(DEFAULT)


def set_theme(overrides=None):
    T.clear()
    T.update(DEFAULT)
    T.update(overrides or {})
