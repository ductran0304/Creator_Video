"""Asset SVG vẽ sẵn (nền, đồ vật) — ưu tiên hơn hình vẽ bằng code khi có file.

doodle/assets/backgrounds/<bg>.svg : 1920x1080, đường mặt đất đúng hợp đồng trong backgrounds.py
doodle/assets/props/<name>.svg     : viewBox gốc ở chân vật (xem props.py), cùng kích thước metadata
"""
import itertools
import os
import re
from functools import lru_cache

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
_uid = itertools.count()


@lru_cache(maxsize=None)
def _inner(kind, name):
    path = os.path.join(ASSET_DIR, kind, f"{name}.svg")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    m = re.search(r"<svg\b[^>]*>(.*)</svg>", raw, re.S)
    return m.group(1) if m else None


def get(kind, name):
    """Nội dung bên trong thẻ <svg> của asset, id nội bộ được đổi tên duy nhất để dùng nhiều lần
    trong một khung (vd split hai nửa cùng nền) không bị trùng clipPath. None nếu chưa có asset."""
    body = _inner(kind, name)
    if body is None or "id=" not in body:
        return body
    p = f"a{next(_uid)}_"
    body = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{p}{m.group(1)}"', body)
    return re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{p}{m.group(1)})", body).replace('href="#', f'href="#{p}')


def has(kind, name):
    return _inner(kind, name) is not None
