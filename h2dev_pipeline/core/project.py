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
SCENE_DOC_KEYS = {"lines", "id", "note"}


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
        return [(spec, None) for _ in lines]
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


def final_state(scene):
    states = scene_states(scene)
    return states[-1] if states else (scene_spec(scene), None)


def words(text):
    return len(re.findall(r"\w+(?:['’]\w+)?", text))


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
        if lines and secs > 35:
            warnings.append(f"{tag}: ~{secs:.0f}s cho một hình — nên tách cảnh hoặc dùng show/change để hình thay đổi")

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
    if n < 20 or n > 45:
        warnings.append(f"{n} cảnh — khuyến nghị 25–40 cảnh cho video 7–12 phút")

    stats = {"scenes": n, "lines": len(all_text), "words": total_words,
             "est_minutes": round(total_words / wpm, 1), "language": lang}
    return errors, warnings, stats
