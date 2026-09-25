"""Bản dọc 9:16 (YouTube Shorts / TikTok / Reels) — bố cục thiết kế riêng cho màn hình dọc.

scenes.json (tuỳ chọn):
  "short": {"lines": ["1.1-1.4", "3.2"], "hook": "Doanh thu *dưới 1 tỷ*: vẫn phải làm *4 việc*", "outro": "..."}
hoặc nhiều bản:
  "shorts": [
    {"id": "hook", "lines": ["1", "4.4-4.6"], "hook": "..."},                 # cắt từ video dài
    {"id": "hoi_dap_1", "hook": "...", "kicker": "HỎI NHANH – ĐÁP GỌN",       # kịch bản viết riêng (20–40s)
     "scenes": [ {cảnh như scenes.json, có thể dùng speaker/step/cut...} ]}
  ]
- lines: "S" cả cảnh · "S.L" một câu · "S.L-M" / "S.L-S.M" dải câu (đánh số từ 1). Mặc định: cả cảnh 1.
- hook: tiêu đề cố định ở trên (giữ ngữ cảnh suốt video); `*từ*` → màu nhấn; không có dấu * thì tự nhấn các số.
- Câu kết tự thêm (outro → brand.short_outro → câu chung); thương hiệu có màn kết thì hiện màn kết đó.

Bố cục 1080x1920 (vùng an toàn, tránh nút bấm/caption của TikTok/Reels ở mép phải và ~1/6 dưới cùng):
  nhãn chuyên mục + logo · tiêu đề có từ nhấn · ô nội dung 1000x750 (khung thẻ vẽ lại theo đúng ô; cảnh doodle
  16:9 được camera cắt vừa ô) · thanh tiến độ · phụ đề karaoke to (vệt dạ quang ở từ đang đọc).
Giọng đọc và ảnh dùng lại cache của video dài.
"""
import io
import os
import re

from PIL import Image, ImageDraw, ImageFont

VW, VH = 1080, 1920
MEDIA = (40, 560, 1000, 750)       # x, y, w, h của ô nội dung
MEDIA_R = 34
KICKER_Y = 138
HEAD_BOX = (60, 212, 960, 320)     # x, y, w, h của tiêu đề
BAR_Y = 1332
SUB_TOP, SUB_MAX_W = 1380, 920
LEAD_IN, TAIL = 0.25, 1.2
DEFAULT_OUTRO = {"en": "Watch the full story on the channel.", "vi": "Xem bản đầy đủ trên kênh nhé."}


class ShortError(Exception):
    pass


# ---------------- chọn câu ----------------
def _parse_ref(ref, scenes):
    """'3' | '3.2' | '3.2-4' | '3.2-3.4' | 3 → list (si, li) 0-based."""
    m = re.fullmatch(r"\s*(\d+)(?:\.(\d+)(?:\s*-\s*(?:(\d+)\.)?(\d+))?)?\s*", str(ref))
    if not m or (m.group(3) and m.group(3) != m.group(1)):
        raise ShortError(f"short.lines: '{ref}' sai cú pháp (dùng 'S', 'S.L' hoặc 'S.L-M', đánh số từ 1; "
                         "dải câu phải trong cùng một cảnh)")
    s = int(m.group(1)) - 1
    if not 0 <= s < len(scenes):
        raise ShortError(f"short.lines: '{ref}' — không có cảnh {s + 1}")
    n = len(scenes[s].get("lines", []))
    a = int(m.group(2)) - 1 if m.group(2) else 0
    b = int(m.group(4)) - 1 if m.group(4) else (a if m.group(2) else n - 1)
    if not (0 <= a <= b < n):
        raise ShortError(f"short.lines: '{ref}' — cảnh {s + 1} chỉ có {n} câu")
    return [(s, i) for i in range(a, b + 1)]


def plans(project):
    """→ list dict(id, folder, hook, kicker, outro_text, items=[(scene, li)], own, outro_scene, chapters)."""
    raw = project.get("shorts")
    if raw is None:
        raw = [dict(project.get("short") or {}, id="main")]
    scenes = project["scenes"]
    brand = project.get("_brand") or {}
    lang = project.get("language", "en")
    outro_scene = next((s for s in scenes if s.get("_auto_outro")), None)
    chapter_of, cur = {}, None  # chương đang diễn ra ở mỗi cảnh (làm nhãn trên cùng)
    for sc in scenes:
        cur = sc.get("chapter") or cur
        chapter_of[id(sc)] = cur
    out, seen = [], set()
    for i, s in enumerate(raw):
        sid = str(s.get("id") or ("main" if i == 0 else f"s{i + 1}"))
        if sid in seen:
            raise ShortError(f"shorts: id '{sid}' bị trùng")
        seen.add(sid)
        own = bool(s.get("scenes"))
        if own:
            items = [(sc, li) for sc in s["scenes"] for li in range(len(sc.get("lines", [])))]
            if not items:
                raise ShortError(f"shorts[{sid}]: 'scenes' cần có lines")
            cur = None
            for sc in s["scenes"]:
                cur = sc.get("chapter") or cur
                chapter_of[id(sc)] = cur
        else:
            items = []
            for r in (s.get("lines") or ["1"]):
                for si, li in _parse_ref(r, scenes):
                    if not any(sc is scenes[si] and l2 == li for sc, l2 in items):
                        items.append((scenes[si], li))
        o_scene = None if any(sc is outro_scene for sc, _ in items) else outro_scene
        out.append({"id": sid, "folder": "short" if i == 0 else f"short_{sid}", "own": own, "items": items,
                    "hook": s.get("hook") or project.get("title", ""), "kicker": s.get("kicker"),
                    "outro_text": s.get("outro") or brand.get("short_outro") or DEFAULT_OUTRO.get(lang, DEFAULT_OUTRO["en"]),
                    "outro_scene": o_scene, "chapters": chapter_of})
    return out


def check(project, wpm):
    """Lỗi/cảnh báo cho các bản dọc (dùng trong validate). Trả (errors, warnings, ước lượng giây của bản đầu)."""
    from .project import words, line_states
    from doodle.scene import scene_svg, SceneError
    try:
        ps = plans(project)
    except ShortError as e:
        return [str(e)], [], 0
    errors, warnings, first = [], [], 0
    for p in ps:
        tag = "Bản dọc" + ("" if p["id"] == "main" else f" '{p['id']}'")
        n_words = sum(words(sc["lines"][li].get("text", "")) for sc, li in p["items"]) + words(p["outro_text"])
        secs = n_words / wpm * 60 * 0.85 + 0.3 * len(p["items"])  # edge-tts đọc nhanh hơn WPM ước lượng ~15%
        first = first or secs
        if secs > 60:
            warnings.append(f"{tag} ước ~{secs:.0f}s > 60s — Shorts/Reels/TikTok giữ chân tốt nhất ở 20–45s; bớt câu")
        if secs < 12:
            warnings.append(f"{tag} chỉ ~{secs:.0f}s — nên 20–45s")
        plain = p["hook"].replace("*", "")
        if len(plain) > 45:
            warnings.append(f"{tag}: chữ hook dài {len(plain)} ký tự — nên ≤ 45 để đọc kịp trên điện thoại")
        from .project import hook_warnings
        texts = [sc["lines"][li].get("text", "") for sc, li in p["items"][:2]]
        if texts:
            warnings += hook_warnings(texts, tag, project.get("language", "en"))
        if p["own"]:
            for si, sc in enumerate({id(sc): sc for sc, _ in p["items"]}.values(), 1):
                try:
                    for st in line_states(sc):
                        scene_svg(st["spec"], [], st["visible"], st["seed"])
                except SceneError as e:
                    errors.append(f"{tag}, cảnh {si}: {e}")
                except (KeyError, TypeError, ValueError, IndexError) as e:
                    errors.append(f"{tag}, cảnh {si}: cấu trúc sai ({type(e).__name__}: {e})")
                for ln in sc.get("lines", []):
                    if not str(ln.get("text", "")).strip():
                        errors.append(f"{tag}, cảnh {si}: câu thiếu 'text'")
                    spk = ln.get("speaker")
                    if spk and spk not in (project.get("voices") or {}):
                        errors.append(f"{tag}: speaker '{spk}' chưa khai báo trong 'voices'")
    return errors, warnings, first


def timeline(plan, durations, bounds, cfg):
    """Dòng thời gian bản dọc. durations/bounds theo thứ tự plan['items'] rồi câu kết.
    → (segments, total, refs) — refs[seg][k] = (scene, li) để vẽ cú máy tương ứng."""
    from .build import word_times, _line_sfx
    from .project import line_states
    line_gap = cfg.get("line_gap", 0.25)
    seg_gap = 0.3
    t = LEAD_IN
    segs, refs = [], []
    states_cache = {}
    for k, (sc, li) in enumerate(plan["items"]):
        prev = refs[-1][-1] if refs else None
        if not prev or prev[0] is not sc or prev[1] + 1 != li:
            if segs:
                t += seg_gap - line_gap
            segs.append({"index": len(segs), "start": t, "lines": [], "chapter": None, "progress": None,
                         "kicker": plan["kicker"] or plan["chapters"].get(id(sc))})
            refs.append([])
        ln = sc["lines"][li]
        if id(sc) not in states_cache:
            states_cache[id(sc)] = line_states(sc)
        d = durations[k]
        sub = ln.get("sub") or ln["text"]
        sfx = _line_sfx(states_cache[id(sc)], li, 1) if segs[-1]["lines"] else []
        segs[-1]["lines"].append({"text": ln["text"], "sub": sub, "start": t, "end": t + d, "audio_index": k,
                                  "reveal": bool(ln.get("show")) and bool(segs[-1]["lines"]),
                                  "speaker": ln.get("speaker"), "nosub": False, "fx": ln.get("fx"),
                                  "sfx": sfx + list(ln.get("sfx") or []),
                                  "wt": word_times(sub, ln["text"], t, d, bounds[k])})
        refs[-1].append((sc, li))
        t += d + line_gap
    k = len(plan["items"])
    d = durations[k]
    ln = {"text": plan["outro_text"], "sub": plan["outro_text"], "audio_index": k, "reveal": False, "sfx": [],
          "speaker": None}
    if plan["outro_scene"] is not None:
        t += seg_gap - line_gap
        segs.append({"index": len(segs), "start": t, "lines": [], "chapter": None, "progress": None,
                     "kicker": segs[-1]["kicker"] if segs else None})
        refs.append([])
        ln["nosub"] = True
        refs[-1].append((plan["outro_scene"], 0))
    else:
        ln["nosub"] = False
        refs[-1].append(refs[-1][-1])
    ln.update(start=t, end=t + d, wt=word_times(ln["sub"], ln["text"], t, d, bounds[k]))
    segs[-1]["lines"].append(ln)
    total = t + d + TAIL
    for i, s in enumerate(segs):
        s["end"] = segs[i + 1]["start"] if i + 1 < len(segs) else total
    return segs, total, refs


def render_shots(plan, refs, cache_dir, layout, draw=False):
    """Cú máy cho từng câu của bản dọc: khung thẻ vẽ lại đúng ô nội dung; cảnh 16:9 dùng lại ảnh của video dài."""
    from .build import render_state
    from .project import line_states
    os.makedirs(cache_dir, exist_ok=True)
    states = {}
    out = []
    for seg in refs:
        shots = []
        for sc, li in seg:
            if id(sc) not in states:
                states[id(sc)] = line_states(sc)
            shots.append(render_state(states[id(sc)][li], cache_dir, size=layout.media_native, draw=draw, scene=sc))
        out.append(shots)
    return out


# ---------------- bố cục ----------------
def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _tokens(text):
    if "*" not in text:  # không đánh dấu: tự nhấn các cụm có chữ số (con số, mốc ngày)
        return [(w, bool(re.search(r"\d", w))) for w in text.split()]
    out, acc = [], False
    prev_part = ""
    for part in re.split(r"(\*)", text):
        if part == "*":
            acc = not acc
            continue
        words = part.split()
        glued = bool(prev_part) and not prev_part[-1:].isspace() and part[:1].strip()
        prev_part = part
        if words and out and glued:  # dấu câu ngay sau từ nhấn → dính vào từ trước
            out[-1] = (out[-1][0] + words.pop(0), out[-1][1])
        out += [(w, acc) for w in words]
    return out


def look_for(project):
    from doodle.theme import T
    from doodle.text import FONT_PATH
    brand = project.get("_brand") or {}
    v = dict(brand.get("vertical") or {})
    look = {"paper": T["paper"], "ink": T["title"], "accent": v.get("accent") or T.get("accent") or T["alert"],
            "label": T["label"]}
    fp = None
    if brand and v.get("font_file"):
        p = os.path.join(brand["_dir"], v["font_file"])
        fp = p if os.path.isfile(p) else None
    look["font"] = fp or T.get("font_file") or FONT_PATH
    logo = v.get("logo_light") or v.get("logo")
    look["logo"] = os.path.join(brand["_dir"], logo) if (brand and logo) else None
    return look


def _logo(svg_path, height):
    try:
        import resvg_py
        from doodle import scene as ds
        from doodle.text import FONT_PATH
        with open(svg_path, "r", encoding="utf-8") as f:
            svg = f.read()
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, height=int(height), skip_system_fonts=True,
                                          font_files=[FONT_PATH] + ds.EXTRA_FONTS))
        return Image.open(io.BytesIO(png)).convert("RGBA")
    except Exception:
        return None


class Layout:
    """Nền tĩnh (giấy kẻ ô, nhãn, tiêu đề, khung ô nội dung) vẽ một lần cho mỗi nhãn chuyên mục;
    mỗi khung hình chỉ dán ô nội dung (bo góc) + thanh tiến độ."""

    def __init__(self, project, plan, size=(VW, VH), total=None, segs=None):
        from doodle.theme import T
        self.size = size
        self.k = k = size[0] / VW
        self.total = total
        self.segs = segs or []
        self.look = look_for(project)
        self.hook = plan["hook"]
        x, y, w, h = MEDIA
        self.frame_size = (int(w * k), int(h * k))
        self.frame_pos = (int(x * k), int(y * k))
        self.media_native = (w, h)  # khung thẻ vẽ theo đúng ô này (ở độ phân giải 1080p)
        mask = Image.new("L", self.frame_size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, self.frame_size[0] - 1, self.frame_size[1] - 1],
                                               radius=int(MEDIA_R * k), fill=255)
        self.mask = mask
        self.grid = T.get("grid", False)
        self._bases = {}
        self._logo = _logo(self.look["logo"], 58 * k) if self.look["logo"] else None

    def _font(self, px):
        return ImageFont.truetype(self.look["font"], max(8, int(px)))

    def _base(self, kicker):
        key = kicker or ""
        if key in self._bases:
            return self._bases[key]
        k, L = self.k, self.look
        W_, H_ = self.size
        img = Image.new("RGB", self.size, _hex(L["paper"]))
        d = ImageDraw.Draw(img)
        if self.grid:  # giấy kẻ ô mờ
            g = max(12, int(48 * k))
            col = tuple(int(p + (i - p) * 0.06) for p, i in zip(_hex(L["paper"]), _hex(L["ink"])))
            for gx in range(0, W_, g):
                d.line([(gx, 0), (gx, H_)], fill=col, width=max(1, int(2 * k)))
            for gy in range(0, H_, g):
                d.line([(0, gy), (W_, gy)], fill=col, width=max(1, int(2 * k)))
        d.rectangle([0, 0, W_, int(12 * k)], fill=_hex(L["label"]))
        x0 = int(60 * k)
        if kicker:  # nhãn chuyên mục
            f = self._font(30 * k)
            txt = kicker.upper()
            tw = d.textlength(txt, font=f)
            h = int(54 * k)
            d.rounded_rectangle([x0, KICKER_Y * k, x0 + tw + 44 * k, KICKER_Y * k + h], radius=h // 2,
                                fill=_hex(L["label"]))
            d.text((x0 + 22 * k, KICKER_Y * k + h / 2), txt, font=f, fill=(255, 255, 255), anchor="lm")
        if self._logo is not None:
            img.paste(self._logo, (int(W_ - 60 * k - self._logo.width), int((KICKER_Y + 27) * k - self._logo.height / 2)),
                      self._logo)
        # tiêu đề có từ nhấn (to nhất có thể, tối đa 3 dòng)
        hx, hy, hw, hh = [v * k for v in HEAD_BOX]
        toks = _tokens(self.hook)
        for px in range(96, 50, -4):
            f = self._font(px * k)
            rows, cur = [], []
            for tok in toks:
                cand = cur + [tok]
                if cur and d.textlength(" ".join(w for w, _ in cand), font=f) > hw:
                    rows.append(cur)
                    cur = [tok]
                else:
                    cur = cand
            if cur:
                rows.append(cur)
            lh = px * 1.12 * k
            if len(rows) <= 3 and lh * len(rows) <= hh:
                break
        y = hy + (hh - lh * len(rows)) / 2
        space = d.textlength(" ", font=f)
        for row in rows:
            x = hx
            for w, acc in row:
                d.text((x, y), w, font=f, fill=_hex(L["accent"] if acc else L["ink"]))
                x += d.textlength(w, font=f) + space
            y += lh
        # bóng + viền ô nội dung, rãnh thanh tiến độ
        mx, my = self.frame_pos
        mw, mh = self.frame_size
        sh = Image.new("RGBA", self.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([mx, my + 10 * k, mx + mw, my + mh + 10 * k], radius=int(MEDIA_R * k),
                                             fill=(16, 26, 61, 30))
        img.paste(sh, (0, 0), sh)
        d.rounded_rectangle([mx - 2, my - 2, mx + mw + 2, my + mh + 2], radius=int(MEDIA_R * k) + 2,
                            outline=(220, 226, 238), width=max(2, int(3 * k)))
        d.rounded_rectangle([mx, BAR_Y * k, mx + mw, BAR_Y * k + 10 * k], radius=int(5 * k), fill=(222, 227, 238))
        self._bases[key] = img
        return img

    def compose(self, frame, t, si=0):
        kicker = self.segs[si].get("kicker") if self.segs else None
        img = self._base(kicker).copy()
        img.paste(frame, self.frame_pos, self.mask)
        if self.total:
            d = ImageDraw.Draw(img)
            mx, _ = self.frame_pos
            mw = self.frame_size[0]
            k = self.k
            d.rounded_rectangle([mx, BAR_Y * k, mx + max(10 * k, mw * min(1.0, t / self.total)), BAR_Y * k + 10 * k],
                                radius=int(5 * k), fill=_hex(self.look["accent"]))
        return img

    def cover(self, media_img, kicker=None):
        img = self._base(kicker).copy()
        img.paste(media_img.resize(self.frame_size, Image.LANCZOS), self.frame_pos, self.mask)
        return img

    def subtitles(self, tl, speakers=None):
        from .build import Subtitles
        k = self.k
        return Subtitles(tl, self.size, font_px=int(64 * k), max_w=SUB_MAX_W * k, rows=2, style="pill",
                         top=int(SUB_TOP * k), line_h=int(84 * k), speakers=speakers, font_file=self.look["font"])
