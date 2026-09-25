"""Đọc & kiểm tra projects/<slug>/scenes.json.

Cấu trúc:
{
  "title": "How Did Ancient Humans Sleep?",
  "language": "en" | "vi",
  "voice": "en-US-EmmaNeural",            # tuỳ chọn, mặc định theo ngôn ngữ
  "scenes": [
    {
      "frame": "scene", "bg": "deep_night",  # + các trường của doodle (elements, text, left/right, events, bars)
      "elements": [{"id": "fire", ...}, ...],
      "lines": [
        {"text": "Câu thoại 1."},                                   # thành phần không nhắc tới trong `show` hiện từ đầu
        {"text": "Câu thoại 2.", "show": ["fire"]},                 # hiện thêm thành phần (id hoặc chỉ số)
        {"text": "Câu thoại 3.", "change": {"me": {"expression": "surprise"}}}  # đổi thuộc tính từ câu này
      ]
    }
  ]
}
"""
import copy
import json
import os
import re
import zlib

from doodle.scene import scene_svg, SceneError

LANGS = {"en", "vi"}
WPM = {"en": 150, "vi": 190}  # tốc độ đọc ước lượng của edge-tts (từ/phút)
SCENE_DOC_KEYS = {"lines", "id", "note", "chapter", "progress"}


class ProjectError(Exception):
    pass


def resolve_project_dir(arg, base_dir):
    if os.path.isdir(arg):
        return os.path.abspath(arg)
    cand = os.path.join(base_dir, "projects", arg)
    if os.path.isdir(cand):
        return cand
    raise ProjectError(f"Không tìm thấy project '{arg}' (đã thử {arg} và {cand})")


def load_project(project_dir):
    path = os.path.join(project_dir, "scenes.json")
    if not os.path.exists(path):
        raise ProjectError(f"Thiếu file {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        line = raw.splitlines()[e.lineno - 1] if e.lineno <= len(raw.splitlines()) else ""
        raise ProjectError(f"scenes.json lỗi cú pháp JSON ở dòng {e.lineno}, cột {e.colno}: {e.msg}\n    {line.strip()}")


def scene_spec(scene):
    """Phần dành cho bộ vẽ (bỏ các trường kịch bản)."""
    return {k: v for k, v in scene.items() if k not in SCENE_DOC_KEYS}


def _ref_index(scene, ref):
    """id hoặc chỉ số → chỉ số element; None nếu không tồn tại."""
    elements = scene.get("elements", [])
    if isinstance(ref, int):
        return ref if 0 <= ref < len(elements) else None
    for i, el in enumerate(elements):
        if el.get("id") == ref:
            return i
    return None


def scene_seed(scene):
    """Seed nét rung cố định của cả cảnh — giống nhau ở mọi câu thoại để hình không 'giật'."""
    return zlib.crc32(json.dumps(scene_spec(scene), sort_keys=True).encode())


def scene_states(scene):
    """Trạng thái hình cho từng câu thoại: list[(spec, visible_indices | None)].
    visible=None nghĩa là hiện tất cả (frame không phải 'scene')."""
    spec = scene_spec(scene)
    lines = scene.get("lines", [])
    if spec.get("frame", "scene") != "scene":
        # khung thẻ: `step` của câu thoại = số mục đã hiện/đã tick (giữ nguyên cho các câu sau)
        out, step = [], None
        for ln in lines:
            if "step" in ln:
                step = ln["step"]
            out.append((dict(spec, _step=step) if step is not None else spec, None))
        return out
    n = len(spec.get("elements", []))
    shown_later = {_ref_index(scene, r) for ln in lines for r in ln.get("show", [])} - {None}
    visible = set(range(n)) - shown_later
    cur = copy.deepcopy(spec)
    states = []
    for ln in lines:
        for r in ln.get("show", []):
            idx = _ref_index(scene, r)
            if idx is not None:
                visible.add(idx)
        for r, changes in (ln.get("change") or {}).items():
            idx = _ref_index(scene, r)
            if idx is not None:
                cur["elements"][idx].update(changes)
        states.append((copy.deepcopy(cur), set(visible)))
    return states


def line_states(scene):
    """Một "cú máy" cho mỗi câu thoại: list[dict(spec, visible, seed, focus, cut, reveal)].
    - câu có `cut` (một cảnh riêng, B-roll) → hiện cảnh đó rồi quay lại cảnh chính ở câu sau;
    - câu có `focus` (id element) → camera đẩy vào cận cảnh element đó;
    - `reveal` = câu làm hình thay đổi (show/change) → có cú zoom nhẹ."""
    base = scene_states(scene)
    seed = scene_seed(scene)
    ids = {el.get("id") for el in scene.get("elements", []) if el.get("id")}
    out = []
    prev_visible = None
    for i, ln in enumerate(scene.get("lines", [])):
        spec, visible = base[i]
        cut = ln.get("cut")
        # người nói (speaker) là một nhân vật trong cảnh → camera tự đẩy vào người đó
        focus = ln.get("focus") or (ln.get("speaker") if not cut and ln.get("speaker") in ids else None)
        if isinstance(cut, dict):
            cut_spec = {k: v for k, v in cut.items() if k not in SCENE_DOC_KEYS}
            out.append({"spec": cut_spec, "visible": None, "seed": zlib.crc32(json.dumps(cut_spec, sort_keys=True).encode()),
                        "focus": ln.get("focus"), "cut": True, "reveal": False, "new": []})
        else:
            new = sorted(visible - prev_visible) if (visible is not None and prev_visible is not None) else []
            out.append({"spec": spec, "visible": visible, "seed": seed, "focus": focus, "cut": False,
                        "reveal": bool(ln.get("show") or ln.get("change") or "step" in ln), "new": new})
            prev_visible = visible
    return out


def final_state(scene):
    states = scene_states(scene)
    return states[-1] if states else (scene_spec(scene), None)


def words(text):
    return len(re.findall(r"\w+(?:['’]\w+)?", text))


def _still_warn(warnings, tag, secs, a, b, max_still):
    """Nhiều câu liền không đổi hình: ngưỡng max_still. Một câu dài: hình không đổi giữa câu được (camera vẫn
    trôi) nên ngưỡng rộng hơn và gợi ý tách câu."""
    if a == b and secs > max_still + 3:
        warnings.append(f"{tag}, câu {a}: một câu dài ~{secs:.0f}s trên cùng một hình — tách làm 2 câu để đổi hình giữa chừng")
    elif a != b and secs > max_still:
        warnings.append(f"{tag}: hình đứng yên ~{secs:.0f}s (câu {a}–{b}) — thêm show/change/focus/cut để hình đổi mỗi 3–5s")


HOOK_BANNED = ("xin chào", "chào mừng", "hôm nay", "trong video này", "trong vài phút tới", "video này sẽ",
               "kế toán tinh gọn sẽ", "chào anh chị", "hello")


def hook_warnings(texts, tag, lang="vi"):
    """Cảnh báo cho 2 câu đầu (hooks.md mục 2): câu 1 ≤ 16 từ, không chào/báo trước, nên có con số hoặc câu hỏi."""
    out = []
    t1 = (texts[0] or "").strip()
    n = words(t1)
    if n > 16:
        out.append(f"{tag}: câu 1 dài {n} từ — hook nên ≤ 16 từ, nói ngay mâu thuẫn/con số (xem hooks.md)")
    for i, t in enumerate(texts[:2], 1):
        low = (t or "").lower()
        hit = next((b for b in HOOK_BANNED if b in low), None)
        if hit:
            out.append(f"{tag}: câu {i} có '{hit}' — không chào/báo trước ở 2 câu đầu; đưa câu hứa hẹn ra sau giây 15")
    joined = " ".join(texts[:2])
    if lang == "vi" and not re.search(r"\d|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|trăm|triệu|tỷ|\?", joined.lower()):
        out.append(f"{tag}: 2 câu đầu không có con số hay câu hỏi — hook thường mạnh hơn khi có con số/mâu thuẫn cụ thể")
    return out


def validate(project, kb=None, cfg=None):
    """Trả về (errors, warnings, stats). errors ≠ [] nghĩa là không build được."""
    cfg = cfg or {}
    errors, warnings = [], []
    if not isinstance(project, dict):
        return ["scenes.json phải là một object"], [], {}
    if not str(project.get("title", "")).strip():
        errors.append("Thiếu 'title'")
    lang = project.get("language", "en")
    if lang not in LANGS:
        errors.append(f"'language' phải là một trong {sorted(LANGS)}")
        lang = "en"
    scenes = project.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("'scenes' phải là danh sách không rỗng")
        return errors, warnings, {}

    wpm = WPM[lang]
    total_words, all_text = 0, []
    for si, sc in enumerate(scenes, 1):
        tag = f"Cảnh {si}"
        if not isinstance(sc, dict):
            errors.append(f"{tag}: phải là object")
            continue
        lines = sc.get("lines")
        if not isinstance(lines, list) or not lines:
            errors.append(f"{tag}: cần 'lines' là danh sách câu thoại không rỗng")
            lines = []
        scene_words = 0
        for li, ln in enumerate(lines, 1):
            ltag = f"{tag}, câu {li}"
            text = ln.get("text", "") if isinstance(ln, dict) else ""
            if not str(text).strip():
                errors.append(f"{ltag}: thiếu 'text'")
                continue
            if re.search(r"[\[\]\*#_`<>{}]|\(.*?\)", text):
                warnings.append(f"{ltag}: có ký tự lạ/chú thích trong lời thoại (chỉ được là lời đọc thuần): {text[:60]}")
            n = words(text)
            scene_words += n
            if n > 45:
                warnings.append(f"{ltag}: câu dài {n} từ — nên tách để phụ đề dễ đọc")
            if "step" in ln and not isinstance(ln["step"], int):
                errors.append(f"{ltag}: 'step' phải là số nguyên (số mục đã hiện/đã tick)")
            spk = ln.get("speaker")
            if spk and spk not in (project.get("voices") or {}):
                errors.append(f"{ltag}: speaker '{spk}' chưa khai báo trong 'voices' ở gốc scenes.json")
            for r in ln.get("show", []):
                if _ref_index(sc, r) is None:
                    errors.append(f"{ltag}: show '{r}' không khớp id/chỉ số element nào")
            for r, ch in (ln.get("change") or {}).items():
                if _ref_index(sc, r) is None:
                    errors.append(f"{ltag}: change '{r}' không khớp id/chỉ số element nào")
                elif not isinstance(ch, dict):
                    errors.append(f"{ltag}: change '{r}' phải là object thuộc tính")
            all_text.append(text)
        total_words += scene_words
        secs = scene_words / wpm * 60
        if len(lines) > 8:
            warnings.append(f"{tag}: {len(lines)} câu — cảnh quá dài, nên tách thành 2 cảnh")

        # thử vẽ mọi trạng thái (chỉ dựng SVG, không raster) để bắt lỗi tên/bố cục
        try:
            seen, seed = set(), scene_seed(sc)
            for spec, visible in scene_states(sc) or [(scene_spec(sc), None)]:
                w = []
                scene_svg(spec, w, visible, seed)
                for m in w:
                    if m not in seen:
                        seen.add(m)
                        warnings.append(f"{tag}: {m}")
        except SceneError as e:
            errors.append(f"{tag}: {e}")
        except (KeyError, TypeError, ValueError) as e:
            errors.append(f"{tag}: cấu trúc cảnh sai ({type(e).__name__}: {e})")

        for el in sc.get("elements", []):
            if el.get("type") == "label" and len(el.get("text", "")) > 60:
                warnings.append(f"{tag}: chữ trên hình quá dài ({len(el['text'])} ký tự) — nên ngắn gọn, IN HOA")

        # B-roll (cut) và camera (focus): vẽ thử từng cú máy
        for li, ln in enumerate(lines, 1):
            if not (ln.get("cut") or ln.get("focus")):
                continue
            try:
                st = line_states(sc)[li - 1]
                boxes, w = {}, []
                scene_svg(st["spec"], w, st["visible"], st["seed"], boxes)
                if st["cut"]:
                    warnings.extend(f"{tag}, câu {li} (cut): {m}" for m in w)
                if st["focus"] and st["focus"] not in boxes:
                    where = "cảnh cut" if st["cut"] else "cảnh"
                    errors.append(f"{tag}, câu {li}: focus '{st['focus']}' không phải id nhân vật/đồ vật trong {where}")
            except SceneError as e:
                errors.append(f"{tag}, câu {li} (cut): {e}")
            except (KeyError, TypeError, ValueError, IndexError) as e:
                errors.append(f"{tag}, câu {li}: cut/focus sai cấu trúc ({type(e).__name__}: {e})")

        # nhịp hình: cứ vài giây phải có thay đổi (show/change/focus/cut, hoặc thoát khỏi focus/cut)
        max_still = cfg.get("max_still_seconds", 7) if not sc.get("_auto_outro") else 1e9
        still, first = 0.0, 1
        for li, ln in enumerate(lines, 1):
            prev = lines[li - 2] if li > 1 else {}
            changed = li == 1 or any(ln.get(k) for k in ("show", "change", "cut", "focus", "speaker")) or \
                "step" in ln or any(prev.get(k) for k in ("cut", "focus"))
            if changed and li > 1:
                _still_warn(warnings, tag, still, first, li - 1, max_still)
                still, first = 0.0, li
            still += words(ln.get("text", "")) / wpm * 60 if isinstance(ln, dict) else 0
        _still_warn(warnings, tag, still, first, len(lines), max_still)

    # quy tắc nội dung theo DNA kênh
    joined = " ".join(all_text)
    wmin = cfg.get("script_word_count_min", 1500)
    wmax = cfg.get("script_word_count_max", 2400)
    if total_words < wmin:
        warnings.append(f"Kịch bản {total_words} từ < tối thiểu {wmin} (video sẽ ngắn hơn 7 phút)")
    if total_words > wmax:
        warnings.append(f"Kịch bản {total_words} từ > tối đa {wmax}")
    first_person = r"\b(?:[Ww]e|[Oo]ur|[Uu]s|I|[Mm]y|[Mm]e)\b"  # "I" chỉ khớp chữ hoa
    if lang == "en" and re.search(first_person, joined):
        hits = sorted(set(re.findall(first_person, joined)))
        warnings.append(f"Lời thoại dùng ngôi thứ nhất ({', '.join(hits)}) — DNA kênh yêu cầu ngôi thứ 2 'you'")
    if lang == "vi" and re.search(r"\b(chúng ta|chúng tôi|tôi)\b", joined, re.I):
        warnings.append("Lời thoại dùng 'chúng ta/tôi' — DNA kênh yêu cầu ngôi thứ 2 'bạn'")
    if lang == "en":
        names = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", joined))
        if len(names) < cfg.get("min_evidence_count", 3):
            warnings.append(f"Chỉ thấy ~{len(names)} tên riêng — cần ≥3 nhà nghiên cứu/nghiên cứu/di chỉ có thật")
    n = len(scenes)
    smin, smax = cfg.get("scene_count_min", 20), cfg.get("scene_count_max", 45)
    if n < smin or n > smax:
        warnings.append(f"{n} cảnh — khuyến nghị {smin}–{smax} cảnh")

    # độ đa dạng hình ảnh: nền lặp, kiểu thẻ lặp, tỷ lệ footage thật (ảnh, video, văn bản, logo)
    FOOT = {"photo", "video", "doc_page", "logo_row", "media_card"}
    run_bg, last_bg, run_fr, last_fr, n_foot, n_lines = 0, None, 0, None, 0, 0
    for si, sc in enumerate(scenes, 1):
        if not isinstance(sc, dict) or sc.get("_auto_outro"):
            continue
        bg = sc.get("bg") if sc.get("frame", "scene") == "scene" else None
        run_bg = run_bg + 1 if (bg and bg == last_bg) else 1
        last_bg = bg
        if bg and run_bg == 3:
            warnings.append(f"Cảnh {si}: nền '{bg}' lặp 3 cảnh liền — đổi nền hoặc chèn footage thật")
        try:
            states = line_states(sc)
        except Exception:  # noqa: BLE001 — lỗi cấu trúc đã báo ở trên
            continue
        for li, st in enumerate(states, 1):
            fr = st["spec"].get("frame", "scene")
            n_lines += 1
            els = st["spec"].get("elements", []) if fr == "scene" else []
            vis = st["visible"]
            has = fr in FOOT or any(el.get("type") in ("photo", "logo") for i, el in enumerate(els)
                                    if vis is None or i in vis)
            n_foot += bool(has)
            key = fr if (fr != "scene" and st["cut"]) else None  # thẻ hiện dần trong cùng cảnh là chủ ý, không tính lặp
            run_fr = run_fr + 1 if (key and key == last_fr) else (1 if key else 0)
            last_fr = key
            if key and run_fr == 4:
                warnings.append(f"Cảnh {si}, câu {li}: kiểu khung '{fr}' lặp 4 câu liền — xen video/ảnh thật, meme hoặc cảnh doodle")
    target = cfg.get("footage_min_ratio")
    if target and n_lines and n_foot / n_lines < target:
        warnings.append(f"Footage thật chỉ {n_foot}/{n_lines} câu ({n_foot / n_lines:.0%}) < mục tiêu {target:.0%} — "
                        "thêm video/ảnh (footage search), trang văn bản (doc_page), logo khi nhắc tên riêng")

    # hook: câu mở đầu video dài (luật trong .claude/skills/tao-video/hooks.md)
    first_lines = [ln.get("text", "") for sc in scenes[:1] if isinstance(sc, dict) for ln in sc.get("lines", [])[:2]]
    if first_lines:
        warnings += hook_warnings(first_lines, "Video dài", lang)

    # bản dọc 9:16 (mục "short")
    from .vertical import check as check_short
    s_err, s_warn, s_secs = check_short(project, wpm)
    errors += s_err
    warnings += s_warn

    stats = {"scenes": n, "lines": len(all_text), "words": total_words,
             "est_minutes": round(total_words / wpm, 1), "language": lang, "short_seconds": round(s_secs),
             "footage_ratio": round(n_foot / n_lines, 2) if n_lines else 0}
    return errors, warnings, stats
