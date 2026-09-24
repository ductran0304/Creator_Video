"""Nét vẽ tay: biến đường thẳng/hình học thành path SVG hơi rung như vẽ nhanh bằng bút lông.

Mọi độ rung đều sinh từ seed nên cùng một cảnh luôn vẽ ra giống hệt nhau.
"""
import math
import random

INK = "#141414"
STROKE = 6


class Pen:
    def __init__(self, seed, amp=2.4, step=12):
        self.rng = random.Random(seed)
        self.amp = amp
        self.step = step

    # --- noise ---
    def _open_noise(self):
        """Nhiễu mượt theo độ dài cung (px)."""
        comps = [(a, self.rng.uniform(0.7, 1.3) * f, self.rng.uniform(0, 2 * math.pi))
                 for a, f in ((1.0, 0.012), (0.5, 0.029), (0.22, 0.07))]
        return lambda s: sum(a * math.sin(f * s + p) for a, f, p in comps) / 1.72

    def _closed_noise(self, perimeter):
        """Nhiễu tuần hoàn theo chu vi để hình kín không bị gãy ở điểm nối."""
        comps = []
        for a, f in ((1.0, 0.012), (0.5, 0.029), (0.22, 0.07)):
            k = max(2, round(self.rng.uniform(0.7, 1.3) * f * perimeter / (2 * math.pi)))
            comps.append((a, k, self.rng.uniform(0, 2 * math.pi)))
        return lambda s: sum(a * math.sin(k * 2 * math.pi * s / perimeter + p) for a, k, p in comps) / 1.72

    # --- geometry ---
    def _densify(self, pts, closed):
        if closed:
            pts = pts + [pts[0]]
        out = []  # (x, y, nx, ny, s)
        s = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seg = math.hypot(x1 - x0, y1 - y0)
            if seg == 0:
                continue
            nx, ny = -(y1 - y0) / seg, (x1 - x0) / seg
            n = max(1, int(seg / self.step))
            for i in range(n):
                t = i / n
                out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, nx, ny, s + seg * t))
            s += seg
        if not closed:
            x, y = pts[-1]
            nx, ny = (out[-1][2], out[-1][3]) if out else (0.0, 0.0)
            out.append((x, y, nx, ny, s))
        return out, s

    def line_d(self, pts, closed=False, amp=None):
        amp = self.amp if amp is None else amp
        dense, total = self._densify(list(pts), closed)
        noise = self._closed_noise(total) if closed else self._open_noise()
        coords = []
        for x, y, nx, ny, s in dense:
            o = amp * noise(s)
            coords.append(f"{x + nx * o:.1f},{y + ny * o:.1f}")
        return "M" + " L".join(coords) + (" Z" if closed else "")

    def ellipse_d(self, cx, cy, rx, ry, amp=None):
        n = max(28, int(2 * math.pi * max(rx, ry) / self.step))
        pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
        return self.line_d(pts, closed=True, amp=amp)

    # --- SVG elements ---
    def shape(self, d, fill="none", stroke=INK, width=STROKE, extra=""):
        return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" '
                f'stroke-linejoin="round" stroke-linecap="round"{extra}/>')

    def line(self, pts, width=STROKE, stroke=INK, amp=None):
        return self.shape(self.line_d(pts, amp=amp), stroke=stroke, width=width)

    def poly(self, pts, fill, width=STROKE, stroke=INK, amp=None):
        return self.shape(self.line_d(pts, closed=True, amp=amp), fill=fill, stroke=stroke, width=width)

    def ellipse(self, cx, cy, rx, ry, fill, width=STROKE, stroke=INK, amp=None):
        return self.shape(self.ellipse_d(cx, cy, rx, ry, amp=amp), fill=fill, stroke=stroke, width=width)

    def circle(self, cx, cy, r, fill, width=STROKE, stroke=INK, amp=None):
        return self.ellipse(cx, cy, r, r, fill, width, stroke, amp)

    def rect(self, x, y, w, h, fill, width=STROKE, stroke=INK, amp=None):
        return self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], fill, width, stroke, amp)

    def jitter(self, v, spread):
        return v + self.rng.uniform(-spread, spread)
