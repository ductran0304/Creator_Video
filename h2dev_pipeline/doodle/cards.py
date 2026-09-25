"""Khung "thẻ kiểu báo" (editorial cards): tiêu đề có từ nhấn, thẻ số liệu, checklist, văn bản pháp lý, bảng sổ cái,
hạn nộp, so sánh giữ ngữ cảnh, ảnh bo góc, bản đồ có ghim.

Mọi khung ở đây tự dàn bố cục theo kích thước khung (W, H) — cùng một spec vẽ được cho video ngang 1920x1080 và
ô nội dung của bản dọc 9:16. Các khung có nhiều mục (stat_cards, checklist, ledger, compare, map) hiện dần theo
trường `step` của câu thoại (project.scene_states đưa vào spec dưới khoá `_step`).

Chữ: `*từ nhấn*` trong title/headline → tô màu nhấn của thương hiệu.
"""
import datetime
import math
import re
from xml.sax.saxutils import escape

from .palette import C
from .text import text_width, _style
from .theme import T

INK = "#141414"
MUTED = "#5B6477"


# ---------------- tiện ích chữ ----------------
def _font_attrs(weight=None):
    family, _, fw, hand = _style()
    w = weight if weight is not None else (fw or "")
    return f'font-family="{family}"' + (f' font-weight="{w}"' if w else "")


def _tokens(text):
    """'Hạn *31/1* năm sau' → [('Hạn', False), ('31/1', True), ('năm', False), ('sau', False)]"""
    out, accent = [], False
    prev_part = ""
    for part in re.split(r"(\*)", text or ""):
        if part == "*":
            accent = not accent
            continue
        words = part.split()
        glued = bool(prev_part) and not prev_part[-1:].isspace() and part[:1].strip()
        prev_part = part
        if words and out and glued:  # dấu câu dính ngay sau từ nhấn ("*1 tỷ*:") → dính vào từ trước
            out[-1] = (out[-1][0] + words.pop(0), out[-1][1])
        out += [(w, accent) for w in words]
    return out


def _wrap_tokens(tokens, size, max_w, slack=1.04):
    lines, cur = [], []
    for tok in tokens:
        cand = cur + [tok]
        if cur and text_width(" ".join(w for w, _ in cand), size) * slack > max_w:
            lines.append(cur)
            cur = [tok]
        else:
            cur = cand
    return lines + ([cur] if cur else [])


def fit_rich(text, max_w, size, max_lines=3, min_size=24):
    tokens = _tokens(text)
    while True:
        lines = _wrap_tokens(tokens, size, max_w)
        if size <= min_size or len(lines) <= max_lines:
            return lines, size
        size -= 4


def rich(text, x, y, max_w, size, color=None, accent=None, anchor="start", max_lines=3, weight=None, lh=1.16,
         valign="top"):
    """Khối chữ nhiều dòng có từ nhấn. valign top: y là mép trên; middle: y là tâm. → (svg, (w, h))."""
    color = color or T["title"]
    accent = accent or T.get("accent") or T["alert"]
    lines, size = fit_rich(text, max_w, size, max_lines)
    step = size * lh
    h = step * len(lines)
    top = y if valign == "top" else y - h / 2
    out = []
    for i, ln in enumerate(lines):
        spans = []
        for j, (w, acc) in enumerate(ln):
            word = escape(w) + (" " if j < len(ln) - 1 else "")
            spans.append(f'<tspan fill="{accent}">{word}</tspan>' if acc else word)
        by = top + step * i + size * 0.82  # baseline
        out.append(f'<text x="{x:.0f}" y="{by:.0f}" text-anchor="{anchor}" {_font_attrs(weight)} '
                   f'font-size="{size}" fill="{color}">{"".join(spans)}</text>')
    w = max((text_width(" ".join(t for t, _ in ln), size) for ln in lines), default=0)
    return "".join(out), (w, h)


def _color(name, default=None):
    if not name:
        return default or T["title"]
    if name.startswith("#"):
        return name
    return {"alert": T["alert"], "red": T["alert"], "label": T["label"], "accent": T.get("accent") or T["alert"],
            "title": T["title"], "highlight": T["highlight"], "green": "#2E9E5B", "orange": C["orange"],
            "blue": "#2F6FDE", "gray": MUTED, "yellow": T["highlight"]}.get(name, default or T["title"])


def _tint(hex_color, a):
    """Trộn màu với trắng (a = độ đậm 0..1) → hex."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    mix = lambda c: int(255 - (255 - c) * a)
    return "#%02X%02X%02X" % (mix(r), mix(g), mix(b))


# ---------------- nền + thẻ ----------------
def background(W, H):
    if (W, H) != (1920, 1080):  # ô nội dung của bản dọc: nền trắng trơn (bố cục dọc đã có giấy kẻ ô bên ngoài)
        return f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>'
    paper = T["paper"]
    out = [f'<rect width="{W}" height="{H}" fill="{paper}"/>']
    if T.get("grid", False):  # giấy kẻ ô mờ (gợi sổ kế toán) — bật theo thương hiệu
        g = max(36, int(min(W, H) / 22))
        lines = [f'M{x} 0V{H}' for x in range(0, W + 1, g)] + [f'M0 {y}H{W}' for y in range(0, H + 1, g)]
        out.append(f'<path d="{" ".join(lines)}" stroke="{T["title"]}" stroke-opacity="0.055" stroke-width="2"/>')
    out.append(f'<rect width="{W}" height="{max(8, int(min(W, H) / 110))}" fill="{T["label"]}"/>')
    return "".join(out)


def card(x, y, w, h, fill="#FFFFFF", r=None, stroke="#DCE2EE", shadow=True, opacity=1.0):
    r = r if r is not None else max(14, min(w, h) * 0.06)
    op = f' opacity="{opacity:.2f}"' if opacity < 1 else ""
    sh = (f'<rect x="{x:.0f}" y="{y + max(6, h * 0.02):.0f}" width="{w:.0f}" height="{h:.0f}" rx="{r:.0f}" '
          f'fill="#101A3D" fill-opacity="0.08"/>') if shadow else ""
    return (f'<g{op}>{sh}<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{r:.0f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="2"/></g>')


def chip(text, x, y, size, fill=None, color="#FFFFFF", anchor="start", pad=None):
    """Nhãn nhỏ nền màu (kicker, tag trạng thái). → (svg, (w, h))."""
    fill = fill or T["label"]
    pad = pad or size * 0.55
    tw = text_width(text, size) * 1.04
    w, h = tw + 2 * pad, size * 1.7
    x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
    return (f'<rect x="{x0:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{h / 2:.0f}" fill="{fill}"/>'
            f'<text x="{x0 + w / 2:.0f}" y="{y + h / 2 + size * 0.35:.0f}" text-anchor="middle" {_font_attrs(700)} '
            f'font-size="{size:.0f}" fill="{color}">{escape(text)}</text>'), (w, h)


def _k(W, H):
    return min(W, H) / 1080


def _portrait(W, H):
    return H > W * 1.05


def _title(spec, W, H, top):
    """Tiêu đề khung (tuỳ chọn) + kicker. → (svg, mép dưới)."""
    k = _k(W, H)
    mx = W * 0.07
    out, y = [], top
    if spec.get("kicker"):
        s, (_, ch) = chip(spec["kicker"].upper(), mx, y, 30 * k)
        out.append(s)
        y += ch + 20 * k
    if spec.get("title"):
        s, (_, th) = rich(spec["title"], mx, y, W - 2 * mx, (78 if _portrait(W, H) else 84) * k, max_lines=2)
        out.append(s)
        y += th + 26 * k
    return "".join(out), y


# ---------------- các khung ----------------
def headline(spec, W, H):
    """Tiêu đề kiểu báo: kicker · tiêu đề có từ nhấn · tóm tắt · nguồn."""
    k = _k(W, H)
    mx = W * 0.08
    parts = [background(W, H)]
    size = (112 if _portrait(W, H) else 128) * k
    title_svg, (_, th) = rich(spec.get("title", ""), mx, 0, W - 2 * mx, size, max_lines=4)
    deck_h = 0
    if spec.get("deck"):
        _, (_, deck_h) = rich(spec["deck"], mx, 0, W - 2 * mx, 44 * k, INK, max_lines=3, weight=400, lh=1.35)
    kick_h = 60 * k if spec.get("kicker") else 0
    total = kick_h + th + (deck_h + 36 * k if deck_h else 0) + (60 * k if spec.get("source") else 0)
    y = (H - total) / 2
    if spec.get("kicker"):
        parts.append(chip(spec["kicker"].upper(), mx, y, 30 * k)[0])
        y += kick_h + 10 * k
    parts.append(rich(spec.get("title", ""), mx, y, W - 2 * mx, size, max_lines=4)[0])
    y += th + 30 * k
    if spec.get("deck"):
        parts.append(f'<rect x="{mx:.0f}" y="{y:.0f}" width="{8 * k:.0f}" height="{deck_h:.0f}" fill="{T["label"]}"/>')
        parts.append(rich(spec["deck"], mx + 30 * k, y, W - 2 * mx - 30 * k, 44 * k, INK, max_lines=3, weight=400,
                          lh=1.35)[0])
        y += deck_h + 36 * k
    if spec.get("source"):
        parts.append(f'<text x="{mx:.0f}" y="{y + 30 * k:.0f}" {_font_attrs(400)} font-size="{28 * k:.0f}" '
                     f'fill="{MUTED}">{escape("Nguồn: " + spec["source"])}</text>')
    return "".join(parts)


def stat_cards(spec, W, H):
    """Thẻ số liệu: cards[{label, value, note, color}] (1–4). Hiện dần theo step."""
    k = _k(W, H)
    cards = spec.get("cards", [])
    n = len(cards)
    shown = spec.get("_step", n)
    parts = [background(W, H)]
    tsvg, top = _title(spec, W, H, H * 0.09)
    parts.append(tsvg)
    mx, gap = W * 0.07, 34 * k
    port = _portrait(W, H)
    boxed = (W, H) != (1920, 1080)  # ô nội dung bản dọc: xếp dọc để chữ số to, dễ đọc trên điện thoại
    cols = 1 if ((port or boxed) and n <= 3) else (2 if (port or boxed or n == 4) else n)
    rows = math.ceil(n / cols)
    area_h = H * 0.92 - top
    cw = (W - 2 * mx - gap * (cols - 1)) / cols
    ch = min((area_h - gap * (rows - 1)) / rows, cw * (0.8 if not (port or boxed) else 0.5), 460 * k)
    y0 = top + (area_h - (ch * rows + gap * (rows - 1))) / 2
    for i, c in enumerate(cards):
        if i >= shown:
            continue
        r, col = divmod(i, cols)
        x, y = mx + col * (cw + gap), y0 + r * (ch + gap)
        colr = _color(c.get("color"), T["title"] if i else T.get("accent") or T["alert"])
        parts.append(card(x, y, cw, ch))
        parts.append(f'<rect x="{x:.0f}" y="{y + ch * 0.18:.0f}" width="{7 * k:.0f}" height="{ch * 0.64:.0f}" '
                     f'rx="{3 * k:.0f}" fill="{colr}"/>')
        px = x + 40 * k
        inner = cw - 70 * k
        parts.append(f'<text x="{px:.0f}" y="{y + ch * 0.25:.0f}" {_font_attrs(700)} font-size="{30 * k:.0f}" '
                     f'fill="{T["label"]}" letter-spacing="{1.5 * k:.1f}">{escape(c.get("label", "").upper())}</text>')
        vsize = min(ch * 0.4, 170 * k)
        parts.append(rich(c.get("value", ""), px, y + ch * 0.32, inner, vsize, colr, max_lines=1, weight=800)[0])
        if c.get("note"):
            parts.append(rich(c["note"], px, y + ch * 0.72, inner, 30 * k, MUTED, max_lines=2, weight=400)[0])
    return "".join(parts)


def _tick(cx, cy, r, done, current, k):
    if done:
        return (f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="{T["label"]}"/>'
                f'<path d="M{cx - r * 0.45:.0f} {cy + r * 0.02:.0f} L{cx - r * 0.1:.0f} {cy + r * 0.38:.0f} '
                f'L{cx + r * 0.5:.0f} {cy - r * 0.35:.0f}" fill="none" stroke="#FFFFFF" stroke-width="{r * 0.28:.1f}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
    col = T.get("accent") or T["alert"] if current else "#B8C0D2"
    return f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="#FFFFFF" stroke="{col}" stroke-width="{5 * k:.0f}"/>'


def checklist(spec, W, H):
    """items[{text, tag}] — step = số mục đã tick; mục kế tiếp được làm nổi."""
    k = _k(W, H)
    items = [it if isinstance(it, dict) else {"text": it} for it in spec.get("items", [])]
    done = spec.get("_step", spec.get("done", 0))
    parts = [background(W, H)]
    tsvg, top = _title(spec, W, H, H * 0.09)
    parts.append(tsvg)
    mx = W * 0.07
    n = max(1, len(items))
    area_h = H * 0.93 - top
    gap = 20 * k
    rh = min((area_h - gap * (n - 1)) / n, 170 * k)
    y = top + (area_h - (rh * n + gap * (n - 1))) / 2
    for i, it in enumerate(items):
        is_done, cur = i < done, i == done
        fill = _tint(T["highlight"], 0.28) if cur else "#FFFFFF"
        parts.append(card(mx, y, W - 2 * mx, rh, fill=fill, stroke=T["highlight"] if cur else "#DCE2EE",
                          shadow=cur, opacity=1.0 if (is_done or cur or done == 0) else 0.72))
        r = rh * 0.24
        parts.append(_tick(mx + 30 * k + r, y + rh / 2, r, is_done, cur, k))
        tx = mx + 60 * k + 2 * r
        tag_w = 0
        if it.get("tag"):
            tsz = 26 * k
            s, (tag_w, _) = chip(it["tag"], W - mx - 30 * k, y + rh / 2 - tsz * 0.85, tsz,
                                 fill=_color(it.get("tag_color"), T["label"]), anchor="end")
            parts.append(s)
        parts.append(rich(it["text"], tx, y + rh / 2, W - mx - tx - tag_w - 60 * k, min(54 * k, rh * 0.36),
                          INK if not is_done else MUTED, max_lines=2, weight=700, valign="middle")[0])
        y += rh + gap
    return "".join(parts)


def document(spec, W, H):
    """Thẻ văn bản pháp lý: doc_type, number, date, issuer, quote, effective, source."""
    k = _k(W, H)
    port = _portrait(W, H)
    parts = [background(W, H)]
    cw = W * (0.86 if port else 0.72)
    ch = H * (0.74 if port else 0.8)
    x, y = (W - cw) / 2, (H - ch) / 2
    parts.append(card(x, y, cw, ch, r=18 * k))
    parts.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{cw:.0f}" height="{16 * k:.0f}" rx="{8 * k:.0f}" '
                 f'fill="{T["title"]}"/>')
    px, inner = x + 60 * k, cw - 120 * k
    cy = y + 80 * k
    if spec.get("doc_type"):
        parts.append(f'<text x="{px:.0f}" y="{cy:.0f}" {_font_attrs(800)} font-size="{34 * k:.0f}" fill="{T["label"]}" '
                     f'letter-spacing="{3 * k:.1f}">{escape(spec["doc_type"].upper())}</text>')
        cy += 30 * k
    s, (_, nh) = rich(spec.get("number", ""), px, cy, inner * 0.78, (92 if not port else 84) * k, T["title"],
                      max_lines=2, weight=800)
    parts.append(s)
    cy += nh + 18 * k
    meta = " · ".join(v for v in (spec.get("date") and "Ngày " + spec["date"], spec.get("issuer")) if v)
    if meta:  # ngày · cơ quan ban hành — tự xuống dòng, không tràn khỏi thẻ
        ms, (_, mh) = rich(meta, px, cy + 6 * k, inner * 0.78, 34 * k, MUTED, max_lines=2, weight=600, lh=1.25)
        parts.append(ms)
        cy += mh + 30 * k
    parts.append(f'<path d="M{px:.0f} {cy:.0f}H{px + inner:.0f}" stroke="#DCE2EE" stroke-width="3"/>')
    cy += 40 * k
    if spec.get("quote"):
        qs, (_, qh) = rich(spec["quote"], px + 36 * k, cy, inner - 36 * k, (48 if not port else 46) * k, INK,
                           max_lines=5, weight=500, lh=1.35)
        parts.append(f'<rect x="{px:.0f}" y="{cy:.0f}" width="{8 * k:.0f}" height="{qh:.0f}" fill="{T.get("accent") or T["alert"]}"/>')
        parts.append(qs)
        cy += qh + 30 * k
    if spec.get("effective"):  # con dấu "hiệu lực"
        sr = 118 * k
        sx, sy = x + cw - sr - 50 * k, y + ch - sr - 50 * k  # góc dưới-phải: không đè số hiệu
        col = T.get("accent") or T["alert"]
        parts.append(f'<g transform="rotate(-12 {sx:.0f} {sy:.0f})" opacity="0.9">'
                     f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{sr:.0f}" fill="none" stroke="{col}" stroke-width="{7 * k:.0f}"/>'
                     f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{sr - 14 * k:.0f}" fill="none" stroke="{col}" stroke-width="{3 * k:.0f}"/>'
                     f'<text x="{sx:.0f}" y="{sy - 10 * k:.0f}" text-anchor="middle" {_font_attrs(800)} font-size="{30 * k:.0f}" '
                     f'fill="{col}">HIỆU LỰC</text>'
                     + rich(spec["effective"], sx, sy + 8 * k, sr * 1.6, 26 * k, col, anchor="middle", max_lines=2,
                            weight=700)[0] + '</g>')
    if spec.get("source"):
        parts.append(f'<text x="{px:.0f}" y="{y + ch - 36 * k:.0f}" {_font_attrs(400)} font-size="{26 * k:.0f}" '
                     f'fill="{MUTED}">{escape("Nguồn: " + spec["source"])}</text>')
    return "".join(parts)


def ledger(spec, W, H):
    """Bảng sổ cái: columns[], rows[[ô, ...]] — ô cuối có thể là {text, color} (tag trạng thái). Hiện dần theo step."""
    k = _k(W, H)
    cols = spec.get("columns", [])
    rows = spec.get("rows", [])
    shown = spec.get("_step", len(rows))
    parts = [background(W, H)]
    tsvg, top = _title(spec, W, H, H * 0.09)
    parts.append(tsvg)
    mx = W * 0.06
    tw = W - 2 * mx
    n = len(rows) + 1
    area_h = H * 0.93 - top
    rh = min(area_h / n, 150 * k)
    parts.append(card(mx, top, tw, rh * n))
    ncol = max(len(cols), max((len(r) for r in rows), default=1))
    widths = spec.get("widths") or ([0.46] + [0.54 / (ncol - 1)] * (ncol - 1) if ncol > 1 else [1.0])
    xs = [mx]
    for w in widths[:-1]:
        xs.append(xs[-1] + tw * w)
    fs = min(40 * k, rh * 0.34)
    parts.append(f'<rect x="{mx:.0f}" y="{top:.0f}" width="{tw:.0f}" height="{rh:.0f}" rx="{max(14, tw * 0.012):.0f}" '
                 f'fill="{T["title"]}"/>')
    for j, c in enumerate(cols):
        parts.append(f'<text x="{xs[j] + 30 * k:.0f}" y="{top + rh / 2 + fs * 0.35:.0f}" {_font_attrs(700)} '
                     f'font-size="{fs * 0.82:.0f}" fill="#FFFFFF">{escape(str(c).upper())}</text>')
    for i, row in enumerate(rows):
        if i >= shown:
            continue
        ry = top + rh * (i + 1)
        if i % 2:
            parts.append(f'<rect x="{mx + 2:.0f}" y="{ry:.0f}" width="{tw - 4:.0f}" height="{rh:.0f}" fill="#F4F6FB"/>')
        for j, cell in enumerate(row):
            cx = xs[j] + 30 * k
            cwid = tw * widths[j] - 50 * k
            if isinstance(cell, dict):
                parts.append(chip(cell.get("text", ""), cx, ry + rh / 2 - fs * 0.62, fs * 0.72,
                                  fill=_color(cell.get("color"), T["label"]))[0])
            else:
                parts.append(rich(str(cell), cx, ry + rh / 2, cwid, fs, INK if j == 0 else T["title"], max_lines=2,
                                  weight=700 if j == 0 else 600, valign="middle")[0])
        parts.append(f'<path d="M{mx:.0f} {ry:.0f}H{mx + tw:.0f}" stroke="#E3E7F2" stroke-width="2"/>')
    return "".join(parts)


def _parse_date(s):
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s or "")
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def deadline(spec, W, H):
    """Hạn nộp: date "31/1/2027", label, note; tự tính "Còn N ngày" từ ngày cập nhật của video."""
    k = _k(W, H)
    port = _portrait(W, H)
    parts = [background(W, H)]
    tsvg, top = _title(spec, W, H, H * 0.08)
    parts.append(tsvg)
    cw = min(W * (0.7 if port else 0.42), 820 * k)
    ch = cw * 0.86
    x = (W - cw) / 2 if port else W * 0.1
    y = top + (H * 0.93 - top - ch) / 2
    col = T.get("accent") or T["alert"]
    parts.append(card(x, y, cw, ch, r=30 * k))
    parts.append(f'<path d="M{x:.0f} {y + 30 * k:.0f}a{30 * k:.0f} {30 * k:.0f} 0 0 1 {30 * k:.0f} {-30 * k:.0f}'
                 f'h{cw - 60 * k:.0f}a{30 * k:.0f} {30 * k:.0f} 0 0 1 {30 * k:.0f} {30 * k:.0f}v{ch * 0.2:.0f}h{-cw:.0f}z" '
                 f'fill="{col}"/>')
    for i in range(4):
        rx = x + cw * (0.2 + 0.2 * i)
        parts.append(f'<rect x="{rx - 9 * k:.0f}" y="{y - 26 * k:.0f}" width="{18 * k:.0f}" height="{56 * k:.0f}" '
                     f'rx="{9 * k:.0f}" fill="{T["title"]}"/>')
    d = _parse_date(spec.get("date"))
    mon = f"THÁNG {d.month}" if d else ""
    parts.append(f'<text x="{x + cw / 2:.0f}" y="{y + ch * 0.14:.0f}" text-anchor="middle" {_font_attrs(800)} '
                 f'font-size="{ch * 0.085:.0f}" fill="#FFFFFF">{escape(mon)}</text>')
    big = str(d.day) if d else spec.get("date", "")
    parts.append(f'<text x="{x + cw / 2:.0f}" y="{y + ch * 0.62:.0f}" text-anchor="middle" {_font_attrs(800)} '
                 f'font-size="{ch * (0.42 if d else 0.2):.0f}" fill="{T["title"]}">{escape(big)}</text>')
    if d:
        parts.append(f'<text x="{x + cw / 2:.0f}" y="{y + ch * 0.8:.0f}" text-anchor="middle" {_font_attrs(700)} '
                     f'font-size="{ch * 0.08:.0f}" fill="{MUTED}">{escape(spec.get("date"))}</text>')
    # bên cạnh (ngang) hoặc bên dưới (dọc): nhãn + đếm ngược + ghi chú
    tx = x + cw + 80 * k if not port else W * 0.08
    ty = y + ch * 0.12 if not port else y + ch + 50 * k
    tw = W - tx - W * 0.07
    if spec.get("label"):
        s, (_, lh) = rich(spec["label"], tx, ty, tw, 64 * k, T["title"], max_lines=3, weight=800)
        parts.append(s)
        ty += lh + 24 * k
    today = _parse_date(T.get("today") or "") or datetime.date.today()
    if d and spec.get("countdown", True):
        days = (d - today).days
        txt = f"Còn {days} ngày" if days > 0 else ("Hôm nay là hạn cuối" if days == 0 else f"Đã quá hạn {-days} ngày")
        s, (_, ch2) = chip(txt, tx, ty, 40 * k, fill=col)
        parts.append(s)
        ty += ch2 + 30 * k
    if spec.get("note"):
        parts.append(rich(spec["note"], tx, ty, tw, 36 * k, MUTED, max_lines=4, weight=500, lh=1.3)[0])
    return "".join(parts)


def compare(spec, W, H):
    """Hai thẻ so sánh cố định: left/right {title, tag, items[]}; step 1 → bên trái sáng, 2 → bên phải, 0 → cả hai."""
    k = _k(W, H)
    port = _portrait(W, H)
    active = spec.get("_step", 0)
    parts = [background(W, H)]
    tsvg, top = _title(spec, W, H, H * 0.08)
    parts.append(tsvg)
    mx, gap = W * 0.06, 36 * k
    cols = [spec.get("left", {}), spec.get("right", {})]
    colors = [_color(cols[0].get("color"), T["label"]), _color(cols[1].get("color"), T.get("accent") or T["alert"])]
    area_h = H * 0.93 - top
    if port:
        cw, ch = W - 2 * mx, (area_h - gap) / 2
    else:
        cw, ch = (W - 2 * mx - gap) / 2, area_h
    for i, side in enumerate(cols):
        x = mx + (0 if port else i * (cw + gap))
        y = top + (i * (ch + gap) if port else 0)
        on = active in (0, i + 1)
        parts.append(f'<g opacity="{1.0 if on else 0.35}">')
        parts.append(card(x, y, cw, ch, fill=_tint(colors[i], 0.1) if (active == i + 1) else "#FFFFFF",
                          stroke=colors[i] if active == i + 1 else "#DCE2EE"))
        parts.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{cw:.0f}" height="{14 * k:.0f}" rx="{7 * k:.0f}" fill="{colors[i]}"/>')
        s, (_, th) = rich(side.get("title", ""), x + cw / 2, y + 40 * k, cw - 60 * k, 64 * k, colors[i], anchor="middle",
                          max_lines=2, weight=800)
        parts.append(s)
        cy = y + 40 * k + th + 24 * k
        items = side.get("items", [])
        fs = min(52 * k, (y + ch - cy - 30 * k) / max(1, len(items)) * 0.5)
        for it in items:
            parts.append(f'<circle cx="{x + 50 * k:.0f}" cy="{cy + fs * 0.62:.0f}" r="{fs * 0.22:.0f}" fill="{colors[i]}"/>')
            s, (_, ih) = rich(it, x + 80 * k, cy, cw - 120 * k, fs, INK, max_lines=2, weight=600)
            parts.append(s)
            cy += ih + fs * 0.6
        parts.append('</g>')
    return "".join(parts)


def media_card(spec, W, H):
    """Ảnh thực tế trong thẻ bo góc + chú thích + nguồn (ít lộ ảnh không sát ý hơn ảnh tràn màn hình)."""
    from .scene import _photo, photo_credit
    k = _k(W, H)
    uri, (iw, ih) = _photo(spec.get("src"))
    parts = [background(W, H)]
    tsvg, top = _title(spec, W, H, H * 0.08)
    parts.append(tsvg)
    mx = W * 0.07
    cap_h = 90 * k if spec.get("caption") else 0
    avail_w, avail_h = W - 2 * mx, H * 0.92 - top - cap_h - 40 * k
    pw = avail_w
    ph = min(avail_h, pw * ih / iw)
    x, y = (W - pw) / 2, top + (avail_h - ph) / 2
    r = 28 * k
    parts.append(card(x - 12 * k, y - 12 * k, pw + 24 * k, ph + 24 * k + cap_h, r=r + 8 * k))
    parts.append(f'<clipPath id="mc{int(x)}{int(y)}"><rect x="{x:.0f}" y="{y:.0f}" width="{pw:.0f}" height="{ph:.0f}" rx="{r:.0f}"/></clipPath>'
                 f'<image href="{uri}" x="{x:.0f}" y="{y:.0f}" width="{pw:.0f}" height="{ph:.0f}" '
                 f'preserveAspectRatio="xMidYMid slice" clip-path="url(#mc{int(x)}{int(y)})"/>')
    if spec.get("caption"):
        parts.append(rich(spec["caption"], x + 10 * k, y + ph + cap_h / 2 + 6 * k, pw * 0.7, 40 * k, T["title"],
                          max_lines=1, weight=700, valign="middle")[0])
    credit = spec.get("credit", photo_credit(spec["src"]))
    if credit:
        parts.append(f'<text x="{x + pw:.0f}" y="{y + ph + cap_h / 2 + 16 * k:.0f}" text-anchor="end" {_font_attrs(400)} '
                     f'font-size="{22 * k:.0f}" fill="{MUTED}">{escape(credit)}</text>')
    return "".join(parts)


def concept(spec, W, H):
    """concept_text vẽ theo khung bất kỳ (dùng cho ô nội dung bản dọc)."""
    k = _k(W, H)
    parts = [background(W, H)]
    main, (_, mh) = rich(spec.get("text", ""), W / 2, 0, W * 0.86, 190 * k, T["title"], anchor="middle", max_lines=3,
                         weight=800, lh=1.08)
    sub_h = 0
    if spec.get("sub"):
        _, (_, sub_h) = rich(spec["sub"], W / 2, 0, W * 0.8, 52 * k, INK, anchor="middle", max_lines=2, weight=600)
    top = (H - mh - sub_h - 30 * k) / 2
    parts.append(rich(spec.get("text", ""), W / 2, top, W * 0.86, 190 * k, T["title"], anchor="middle", max_lines=3,
                      weight=800, lh=1.08)[0])
    if spec.get("sub"):
        parts.append(rich(spec["sub"], W / 2, top + mh + 30 * k, W * 0.8, 52 * k, INK, anchor="middle", max_lines=2,
                          weight=600)[0])
    return "".join(parts)


def photo_full(spec, W, H):
    """Ảnh toàn khung theo tỉ lệ bất kỳ + chú thích + nguồn (bản co giãn của frame photo)."""
    from .scene import _photo, photo_credit
    k = _k(W, H)
    uri, _ = _photo(spec.get("src"))
    parts = [f'<rect width="{W}" height="{H}" fill="#101A3D"/>',
             f'<image href="{uri}" x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="xMidYMid slice"/>']
    if spec.get("caption"):
        s, (tw, th) = rich(spec["caption"], 0, 0, W * 0.8, 44 * k, "#FFFFFF", max_lines=2, weight=700)
        mx, my = W * 0.06, H * 0.06
        parts.append(f'<rect x="{mx:.0f}" y="{my:.0f}" width="{tw + 50 * k:.0f}" height="{th + 30 * k:.0f}" rx="{14 * k:.0f}" '
                     f'fill="#101A3D" fill-opacity="0.82"/>')
        parts.append(rich(spec["caption"], mx + 25 * k, my + 15 * k, W * 0.8, 44 * k, "#FFFFFF", max_lines=2, weight=700)[0])
    credit = spec.get("credit", photo_credit(spec["src"]))
    if credit:
        parts.append(f'<text x="{W - W * 0.05:.0f}" y="{H - H * 0.05:.0f}" text-anchor="end" {_font_attrs(400)} '
                     f'font-size="{22 * k:.0f}" fill="#FFFFFF" stroke="#000000" stroke-opacity="0.5" stroke-width="3" '
                     f'paint-order="stroke">{escape(credit)}</text>')
    return "".join(parts)


# ---------------- bản đồ ----------------
MAP_LAT_TOP, MAP_LAT_BOTTOM = 75.0, -60.0


def map_xy(lat, lon, W=1920, H=1080):
    return (lon + 180) / 360 * W, (MAP_LAT_TOP - lat) / (MAP_LAT_TOP - MAP_LAT_BOTTOM) * H


def world_map(spec, W, H, pen=None):
    """Bản đồ thế giới doodle + ghim pins[{lat, lon, label}] hiện dần theo step. zoom {lat, lon, z} do camera xử lý."""
    from . import assets
    k = _k(W, H)
    parts = []
    inner = assets.get("backgrounds", "world_map")  # nội dung bên trong <svg>
    if inner:
        parts.append(f'<g transform="scale({W / 1920:.4f},{H / 1080:.4f})">{inner}</g>')
    else:
        parts.append(f'<rect width="{W}" height="{H}" fill="#ABD3E5"/>')
    pins = spec.get("pins", [])
    shown = spec.get("_step", len(pins))
    col = T.get("accent") or T["alert"]
    zoom = (spec.get("zoom") or {}).get("z", 1.0)
    ps = k / max(1.0, zoom ** 0.8)  # ghim/nhãn không phình to khi camera zoom
    for i, p in enumerate(pins):
        if i >= shown:
            continue
        x, y = map_xy(p["lat"], p["lon"], W, H)
        r = 20 * ps
        parts.append(f'<path d="M{x:.1f} {y:.1f} C{x - r * 1.6:.1f} {y - r * 1.6:.1f} {x - r * 1.3:.1f} {y - r * 3.2:.1f} '
                     f'{x:.1f} {y - r * 3.2:.1f} C{x + r * 1.3:.1f} {y - r * 3.2:.1f} {x + r * 1.6:.1f} {y - r * 1.6:.1f} '
                     f'{x:.1f} {y:.1f}Z" fill="{col}" stroke="{INK}" stroke-width="{4 * ps:.1f}"/>'
                     f'<circle cx="{x:.1f}" cy="{y - r * 2.1:.1f}" r="{r * 0.5:.1f}" fill="#FFFFFF"/>')
        if p.get("label"):
            left = x > W * 0.8  # sát mép phải: nhãn nằm bên trái ghim
            s, _ = chip(p["label"], x - r * 1.4 if left else x + r * 1.4, y - r * 3.4, 30 * ps, fill=INK,
                        color="#FFFFFF", anchor="end" if left else "start")
            parts.append(s)
    if spec.get("title") and not spec.get("zoom"):  # khi camera zoom, chip góc trên sẽ bị cắt mất
        parts.append(chip(spec["title"].upper(), W * 0.05, H * 0.06, 40 * k, fill=T["title"])[0])
    return "".join(parts)


# ---------------- footage: logo, trang văn bản, màn hình ứng dụng ----------------
def _boxed(W, H):
    return (W, H) != (1920, 1080)


def logo_row(spec, W, H):
    """Hàng logo nhãn hiệu: logos[{src, label}] (2–5), hiện dần theo step; dòng miễn trừ nhãn hiệu nhỏ."""
    from .scene import _photo
    k = _k(W, H)
    logos = spec.get("logos", [])
    shown = spec.get("_step", len(logos))
    parts = [background(W, H)]
    tsvg, top = _title(spec, W, H, H * 0.09)
    parts.append(tsvg)
    n = max(1, len(logos))
    cols = n if (n <= 3 or not _boxed(W, H)) else math.ceil(n / 2)
    rows = math.ceil(n / cols)
    mx, gap = W * 0.07, 30 * k
    cw = (W - 2 * mx - gap * (cols - 1)) / cols
    area_h = H * 0.88 - top
    ch = min((area_h - gap * (rows - 1)) / rows, cw * 0.75)
    y0 = top + (area_h - (ch * rows + gap * (rows - 1))) / 2
    for i, lg in enumerate(logos):
        if i >= shown:
            continue
        r, c = divmod(i, cols)
        x, y = mx + c * (cw + gap), y0 + r * (ch + gap)
        parts.append(card(x, y, cw, ch))
        uri, (iw, ih) = _photo(lg["src"])
        bw, bh = cw * 0.7, ch * 0.5
        s = min(bw / iw, bh / ih)
        lw, lh = iw * s, ih * s
        parts.append(f'<image href="{uri}" x="{x + (cw - lw) / 2:.0f}" y="{y + ch * 0.12 + (bh - lh) / 2:.0f}" '
                     f'width="{lw:.0f}" height="{lh:.0f}" preserveAspectRatio="xMidYMid meet"/>')
        if lg.get("label"):
            parts.append(rich(lg["label"], x + cw / 2, y + ch * 0.72, cw * 0.9, min(40 * k, ch * 0.14), T["title"],
                              anchor="middle", max_lines=2, weight=700)[0])
    parts.append(f'<text x="{W / 2:.0f}" y="{H * 0.96:.0f}" text-anchor="middle" {_font_attrs(400)} '
                 f'font-size="{20 * k:.0f}" fill="{MUTED}">Các nhãn hiệu thuộc về chủ sở hữu; video không có liên kết hay tài trợ.</text>')
    return "".join(parts)


def doc_geom(spec, W, H):
    """Vị trí trang văn bản trên khung + các vùng khoanh (toạ độ khung)."""
    from .scene import _photo
    _, (iw, ih) = _photo(spec["src"])
    side = not _boxed(W, H) and not _portrait(W, H)
    ph = H * 0.9
    pw = ph * iw / ih
    if pw > W * (0.55 if side else 0.9):
        pw = W * (0.55 if side else 0.9)
        ph = pw * ih / iw
    px = W * 0.95 - pw if side else (W - pw) / 2
    py = (H - ph) / 2
    hl = [(px + x * pw, py + y * ph, w * pw, h * ph) for x, y, w, h in spec.get("highlight", [])]
    return (px, py, pw, ph), hl, side


def doc_view(spec, W=1920, H=1080):
    """Cú máy zoom vào vùng khoanh đầu tiên (khi step ≥ 1) → (cx, cy, z) theo tỉ lệ khung, hoặc None."""
    if not spec.get("highlight") or spec.get("_step", 0) < 1:
        return None
    _, hl, _ = doc_geom(spec, W, H)
    x, y, w, h = hl[min(len(hl), spec.get("_step", 1)) - 1]
    z = max(1.3, min(3.2, 0.72 * W / max(w, 1), 0.4 * H / max(h, 1)))
    return ((x + w / 2) / W, (y + h / 2) / H, z)


def doc_page(spec, W, H):
    """Ảnh trang văn bản thật (footage pdf) + khoanh vùng điều khoản; step 1.. → camera zoom vào vùng khoanh."""
    from .scene import _photo
    k = _k(W, H)
    uri, _ = _photo(spec["src"])
    (px, py, pw, ph), hl, side = doc_geom(spec, W, H)
    parts = [background(W, H)]
    parts.append(f'<rect x="{px + 10 * k:.0f}" y="{py + 14 * k:.0f}" width="{pw:.0f}" height="{ph:.0f}" fill="#101A3D" fill-opacity="0.12"/>')
    parts.append(f'<image href="{uri}" x="{px:.0f}" y="{py:.0f}" width="{pw:.0f}" height="{ph:.0f}" preserveAspectRatio="none"/>')
    parts.append(f'<rect x="{px:.0f}" y="{py:.0f}" width="{pw:.0f}" height="{ph:.0f}" fill="none" stroke="#C9CFDD" stroke-width="2"/>')
    for x, y, w, h in hl:
        pad = 4 * k
        parts.append(f'<rect x="{x - pad:.1f}" y="{y - pad:.1f}" width="{w + 2 * pad:.1f}" height="{h + 2 * pad:.1f}" rx="{3 * k:.1f}" '
                     f'fill="{T["highlight"]}" fill-opacity="0.38" stroke="{T.get("accent") or T["alert"]}" stroke-width="{3 * k:.1f}"/>')
    if side:
        tx, tw = W * 0.06, px - W * 0.1
        y = H * 0.24
        if spec.get("kicker"):
            s, (_, chh) = chip(spec["kicker"].upper(), tx, y, 30 * k)
            parts.append(s)
            y += chh + 24 * k
        if spec.get("title"):
            s, (_, th) = rich(spec["title"], tx, y, tw, 76 * k, max_lines=3, weight=800)
            parts.append(s)
            y += th + 24 * k
        if spec.get("caption"):
            parts.append(rich(spec["caption"], tx, y, tw, 38 * k, INK, max_lines=5, weight=500, lh=1.35)[0])
    parts.append(f'<text x="{px + pw:.0f}" y="{py + ph + 26 * k:.0f}" text-anchor="end" {_font_attrs(400)} font-size="{20 * k:.0f}" '
                 f'fill="{MUTED}">{escape(spec.get("credit") or "Ảnh chụp trang văn bản gốc")}</text>')
    return "".join(parts)


def phone_screen(spec, W, H):
    """Màn hình ứng dụng vẽ mô phỏng (không chụp tài khoản thật): app, title, items[], button; step = bước đang làm."""
    k = _k(W, H)
    items = spec.get("items", [])
    cur = spec.get("_step", 0)
    side = not _boxed(W, H) and not _portrait(W, H)
    ph = H * (0.9 if side else 0.94)
    pw = ph * 0.49
    px = W * 0.34 - pw / 2 if side else (W - pw) / 2
    py = (H - ph) / 2
    parts = [background(W, H)]
    r = pw * 0.12
    parts.append(f'<rect x="{px + 10 * k:.0f}" y="{py + 14 * k:.0f}" width="{pw:.0f}" height="{ph:.0f}" rx="{r:.0f}" fill="#101A3D" fill-opacity="0.15"/>')
    parts.append(f'<rect x="{px:.0f}" y="{py:.0f}" width="{pw:.0f}" height="{ph:.0f}" rx="{r:.0f}" fill="#1E2233"/>')
    bz = pw * 0.045
    sx, sy, sw, sh = px + bz, py + bz, pw - 2 * bz, ph - 2 * bz
    parts.append(f'<rect x="{sx:.0f}" y="{sy:.0f}" width="{sw:.0f}" height="{sh:.0f}" rx="{r * 0.8:.0f}" fill="#FFFFFF"/>')
    parts.append(f'<rect x="{px + pw * 0.38:.0f}" y="{sy + 10 * k:.0f}" width="{pw * 0.24:.0f}" height="{14 * k:.0f}" rx="{7 * k:.0f}" fill="#1E2233"/>')
    bar_h = sh * 0.1
    parts.append(f'<path d="M{sx:.0f} {sy + r * 0.8:.0f}a{r * 0.8:.0f} {r * 0.8:.0f} 0 0 1 {r * 0.8:.0f} {-r * 0.8:.0f}h{sw - 1.6 * r * 0.8:.0f}'
                 f'a{r * 0.8:.0f} {r * 0.8:.0f} 0 0 1 {r * 0.8:.0f} {r * 0.8:.0f}v{bar_h + 30 * k - r * 0.8:.0f}h{-sw:.0f}z" fill="{T["label"]}"/>')
    parts.append(rich(spec.get("app", "Ứng dụng"), sx + sw / 2, sy + 30 * k + bar_h / 2, sw * 0.86, min(36 * k, sw * 0.08), "#FFFFFF",
                      anchor="middle", max_lines=1, weight=800, valign="middle")[0])
    y = sy + bar_h + 60 * k
    if spec.get("title"):
        s, (_, th) = rich(spec["title"], sx + sw * 0.07, y, sw * 0.86, min(40 * k, sw * 0.085), T["title"], max_lines=2, weight=800)
        parts.append(s)
        y += th + 24 * k
    n = max(1, len(items))
    rh = min(sh * 0.11, (sy + sh * 0.84 - y) / n - 12 * k)
    for i, it in enumerate(items):
        on = i == cur - 1
        fill = _tint(T["highlight"], 0.45) if on else "#F2F4F9"
        parts.append(f'<rect x="{sx + sw * 0.06:.0f}" y="{y:.0f}" width="{sw * 0.88:.0f}" height="{rh:.0f}" rx="{14 * k:.0f}" fill="{fill}" '
                     f'stroke="{T["highlight"] if on else "#E1E5EE"}" stroke-width="{3 * k:.1f}"/>')
        parts.append(f'<circle cx="{sx + sw * 0.14:.0f}" cy="{y + rh / 2:.0f}" r="{rh * 0.26:.0f}" fill="{T["label"] if i < cur else "#C9CFDD"}"/>')
        parts.append(f'<text x="{sx + sw * 0.14:.0f}" y="{y + rh / 2 + rh * 0.1:.0f}" text-anchor="middle" {_font_attrs(800)} '
                     f'font-size="{rh * 0.28:.0f}" fill="#FFFFFF">{i + 1}</text>')
        parts.append(rich(it, sx + sw * 0.24, y + rh / 2, sw * 0.66, min(30 * k, rh * 0.32), INK, max_lines=2, weight=600,
                          valign="middle")[0])
        if on:  # vòng chạm
            parts.append(f'<circle cx="{sx + sw * 0.86:.0f}" cy="{y + rh / 2:.0f}" r="{rh * 0.32:.0f}" fill="none" '
                         f'stroke="{T.get("accent") or T["alert"]}" stroke-width="{5 * k:.1f}"/>')
        y += rh + 12 * k
    if spec.get("button"):
        bh = sh * 0.07
        by = sy + sh - bh - 30 * k
        parts.append(f'<rect x="{sx + sw * 0.1:.0f}" y="{by:.0f}" width="{sw * 0.8:.0f}" height="{bh:.0f}" rx="{bh / 2:.0f}" '
                     f'fill="{T.get("accent") or T["alert"]}"/>')
        parts.append(rich(spec["button"], sx + sw / 2, by + bh / 2, sw * 0.7, bh * 0.42, "#FFFFFF", anchor="middle", max_lines=1,
                          weight=800, valign="middle")[0])
    if side:
        tx, tw = W * 0.58, W * 0.36
        yy = H * 0.3
        if spec.get("kicker"):
            s, (_, chh) = chip(spec["kicker"].upper(), tx, yy, 30 * k)
            parts.append(s)
            yy += chh + 24 * k
        if spec.get("side_title"):
            s, (_, th) = rich(spec["side_title"], tx, yy, tw, 70 * k, max_lines=3, weight=800)
            parts.append(s)
            yy += th + 24 * k
        if spec.get("note"):
            parts.append(rich(spec["note"], tx, yy, tw, 36 * k, MUTED, max_lines=5, weight=500, lh=1.35)[0])
    parts.append(f'<text x="{W / 2:.0f}" y="{H * 0.985:.0f}" text-anchor="middle" {_font_attrs(400)} font-size="{18 * k:.0f}" '
                 f'fill="{MUTED}">Màn hình minh hoạ</text>')
    return "".join(parts)


# ---------------- meme (vẽ lại định dạng meme bằng nhân vật thương hiệu) ----------------
def _char(pen, c, cx, ground, height):
    from .character import character
    s = max(0.35, min(1.4, height / 470))
    svg, _ = character(pen, cx, ground, c.get("variant", "shop_owner"), c.get("pose", "standing"),
                       c.get("expression", "calm_content"), s, c.get("flip", False), c.get("extras", []), c.get("outfit"))
    return svg


def _pen(spec):
    import json as _json
    import zlib
    from .pen import Pen
    return Pen(zlib.crc32(_json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()))


def meme_expect(spec, W, H):
    """Kỳ vọng vs Thực tế: left/right {title, text, character{variant,pose,expression,extras}}."""
    k = _k(W, H)
    pen = _pen(spec)
    parts = [background(W, H)]
    tsvg, top = _title(spec, W, H, H * 0.06)
    parts.append(tsvg)
    mx, gap = W * 0.05, 30 * k
    cw, ch = (W - 2 * mx - gap) / 2, H * 0.93 - top
    for i, (side, dflt, col) in enumerate((("left", "Kỳ vọng", "#2E9E5B"), ("right", "Thực tế", T.get("accent") or T["alert"]))):
        sd = spec.get(side, {})
        x = mx + i * (cw + gap)
        parts.append(card(x, top, cw, ch, fill=_tint(col, 0.08)))
        parts.append(chip(sd.get("title", dflt).upper(), x + cw / 2, top + 24 * k, 40 * k, fill=col, anchor="middle")[0])
        ground = top + ch * 0.78
        parts.append(_char(pen.child(side), sd.get("character", {}), x + cw / 2, ground, ch * 0.5))
        if sd.get("text"):
            parts.append(rich(sd["text"], x + cw / 2, top + ch * 0.83, cw * 0.88, 42 * k, INK, anchor="middle", max_lines=2,
                              weight=700)[0])
    return "".join(parts)


def meme_choice(spec, W, H):
    """Chọn A hay B (lắc đầu / gật đầu): no, yes (chữ), character{variant} — vẽ lại bằng nhân vật thương hiệu."""
    k = _k(W, H)
    pen = _pen(spec)
    c = dict(spec.get("character") or {"variant": "shop_owner"})
    parts = [background(W, H)]
    tsvg, top = _title(spec, W, H, H * 0.05)
    parts.append(tsvg)
    mx = W * 0.05
    rh = (H * 0.95 - top - 20 * k) / 2
    for i, (key, expr, pose, col) in enumerate((("no", "strain_anger", "standing", T.get("accent") or T["alert"]),
                                                 ("yes", "happy", "pointing", "#2E9E5B"))):
        y = top + i * (rh + 20 * k)
        parts.append(card(mx, y, W - 2 * mx, rh, fill=_tint(col, 0.08)))
        split = W * 0.34
        parts.append(f'<rect x="{mx:.0f}" y="{y:.0f}" width="{split - mx:.0f}" height="{rh:.0f}" rx="{max(14, rh * 0.06):.0f}" fill="{_tint(col, 0.22)}"/>')
        cc = dict(c, expression=expr, pose=pose)
        parts.append(_char(pen.child(key), cc, (mx + split) / 2, y + rh * 0.93, rh * 0.8))
        mark_x, mark_y, mr = split + 60 * k, y + rh / 2, 34 * k
        if key == "no":
            parts.append(f'<g stroke="{col}" stroke-width="{12 * k:.0f}" stroke-linecap="round"><path d="M{mark_x - mr} {mark_y - mr}L{mark_x + mr} {mark_y + mr}M{mark_x + mr} {mark_y - mr}L{mark_x - mr} {mark_y + mr}"/></g>')
        else:
            parts.append(f'<path d="M{mark_x - mr} {mark_y}L{mark_x - mr * 0.25} {mark_y + mr * 0.8}L{mark_x + mr} {mark_y - mr * 0.8}" fill="none" '
                         f'stroke="{col}" stroke-width="{12 * k:.0f}" stroke-linecap="round" stroke-linejoin="round"/>')
        parts.append(rich(spec.get(key, ""), split + 130 * k, y + rh / 2, W - mx - split - 170 * k, 56 * k, INK, max_lines=3,
                          weight=800, valign="middle")[0])
    return "".join(parts)


def meme_pov(spec, W, H):
    """POV: <tình huống> — chữ to + nhân vật phản ứng."""
    k = _k(W, H)
    pen = _pen(spec)
    parts = [background(W, H)]
    mx = W * 0.07
    parts.append(chip("POV", mx, H * 0.1, 44 * k, fill=T["title"])[0])
    text = re.sub(r"^\s*POV\s*:\s*", "", spec.get("text", ""), flags=re.I)
    s, (_, th) = rich(text, mx, H * 0.1 + 100 * k, W - 2 * mx, (80 if not _boxed(W, H) else 64) * k, T["title"],
                      max_lines=3, weight=800)
    parts.append(s)
    top = H * 0.1 + 100 * k + th + 20 * k
    ground = H * 0.97
    parts.append(_char(pen, spec.get("character") or {"variant": "shop_owner", "expression": "surprise", "extras": ["shock_lines"]},
                       W / 2, ground, max(120 * k, ground - top)))
    return "".join(parts)


def meme_twist(spec, W, H):
    """Con dấu PLOT TWIST (hoặc text tuỳ chọn) đóng xuống + dòng giải thích."""
    k = _k(W, H)
    col = T.get("accent") or T["alert"]
    parts = [background(W, H)]
    text = spec.get("text", "PLOT TWIST")
    size = (170 if not _boxed(W, H) else 120) * k
    tw = text_width(text, size) * 1.1
    bw, bh = tw + 80 * k, size * 1.5
    cx, cy = W / 2, H * 0.42
    parts.append(f'<g transform="rotate(-8 {cx:.0f} {cy:.0f})" opacity="0.92">'
                 f'<rect x="{cx - bw / 2:.0f}" y="{cy - bh / 2:.0f}" width="{bw:.0f}" height="{bh:.0f}" rx="{18 * k:.0f}" fill="none" stroke="{col}" stroke-width="{12 * k:.0f}"/>'
                 f'<rect x="{cx - bw / 2 + 18 * k:.0f}" y="{cy - bh / 2 + 18 * k:.0f}" width="{bw - 36 * k:.0f}" height="{bh - 36 * k:.0f}" rx="{10 * k:.0f}" fill="none" stroke="{col}" stroke-width="{4 * k:.0f}"/>'
                 f'<text x="{cx:.0f}" y="{cy + size * 0.36:.0f}" text-anchor="middle" {_font_attrs(800)} font-size="{size:.0f}" fill="{col}" letter-spacing="{4 * k:.1f}">{escape(text)}</text></g>')
    if spec.get("sub"):
        parts.append(rich(spec["sub"], W / 2, H * 0.7, W * 0.8, 54 * k, T["title"], anchor="middle", max_lines=3, weight=700)[0])
    return "".join(parts)


def video_overlay(spec, W=1920, H=1080):
    """Lớp phủ trong suốt của khung video: chú thích + ghi nguồn (đặt trong vùng an toàn để bản dọc cắt không mất)."""
    k = _k(W, H)
    parts = []
    if spec.get("caption"):
        s, (tw, th) = rich(spec["caption"], 0, 0, W * 0.6, 44 * k, "#FFFFFF", max_lines=2, weight=700)
        mx, my = W * 0.15, H * 0.08
        parts.append(f'<rect x="{mx:.0f}" y="{my:.0f}" width="{tw + 50 * k:.0f}" height="{th + 30 * k:.0f}" rx="{14 * k:.0f}" '
                     f'fill="#101A3D" fill-opacity="0.82"/>')
        parts.append(rich(spec["caption"], mx + 25 * k, my + 15 * k, W * 0.6, 44 * k, "#FFFFFF", max_lines=2, weight=700)[0])
    credit = spec.get("credit")
    if credit:
        parts.append(f'<text x="{W * 0.85:.0f}" y="{H * 0.14:.0f}" text-anchor="end" {_font_attrs(400)} font-size="{22 * k:.0f}" '
                     f'fill="#FFFFFF" stroke="#000000" stroke-opacity="0.55" stroke-width="3" paint-order="stroke">{escape(credit)}</text>')
    return "".join(parts)


CARD_FRAMES = {
    "headline": (headline, "Tiêu đề kiểu báo: kicker, title (*từ nhấn*), deck, source"),
    "stat_cards": (stat_cards, "Thẻ số liệu: title, cards[{label, value, note, color}] (1–4), hiện dần theo step"),
    "checklist": (checklist, "Checklist: title, items[{text, tag}] — step = số mục đã tick"),
    "document": (document, "Thẻ văn bản pháp lý: doc_type, number, date, issuer, quote, effective, source"),
    "ledger": (ledger, "Bảng sổ cái: title, columns[], rows[[..., {text,color}]], hiện dần theo step"),
    "deadline": (deadline, "Hạn nộp: date 'd/m/yyyy', label, note — tự đếm 'Còn N ngày'"),
    "compare": (compare, "So sánh giữ ngữ cảnh: left/right {title, items[], color}; step 1/2 làm sáng một bên"),
    "media_card": (media_card, "Ảnh thực tế trong thẻ bo góc: src, caption, title"),
    "map": (world_map, "Bản đồ thế giới: pins[{lat, lon, label}] hiện dần theo step, zoom {lat, lon, z}, title"),
    "logo_row": (logo_row, "Hàng logo nhãn hiệu: title, logos[{src, label}] (2–5), hiện dần theo step"),
    "doc_page": (doc_page, "Trang văn bản thật (footage pdf): src, highlight[[x,y,w,h]], kicker, title, caption; step ≥1 → zoom vùng khoanh"),
    "phone_screen": (phone_screen, "Màn hình ứng dụng mô phỏng: app, title, items[], button, side_title, note; step = bước đang làm"),
    "meme_expect": (meme_expect, "Meme Kỳ vọng vs Thực tế: title, left/right {title, text, character{variant,pose,expression,extras}}"),
    "meme_choice": (meme_choice, "Meme lắc đầu / gật đầu: title, no, yes, character{variant, outfit}"),
    "meme_pov": (meme_pov, "Meme POV: text, character{variant,pose,expression,extras}"),
    "meme_twist": (meme_twist, "Con dấu PLOT TWIST: text (mặc định PLOT TWIST), sub"),
}
# khung vẽ được theo mọi tỉ lệ (bản dọc vẽ lại riêng thay vì thu nhỏ ảnh 16:9)
RESPONSIVE = (set(CARD_FRAMES) - {"map"}) | {"concept_text", "photo"}
