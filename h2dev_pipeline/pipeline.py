import os
import re
import sys
import io
import json
import time
import random
import base64
import subprocess
import asyncio
import math
import struct
import urllib.request
import wave
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import edge_tts
from moviepy import AudioFileClip, ImageClip, concatenate_videoclips, concatenate_audioclips, CompositeAudioClip

# Ép kiểu mã hóa UTF-8 cho console terminal Windows để tránh lỗi ký tự tiếng Việt
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

# --- CONFIG CONSTANTS ---
CONFIG_FILE = "config.json"
TEMP_DIR = "temp"
OUTPUT_DIR = "outputs"

# --- LOAD CONFIGURATION ---
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()
GEMINI_API_KEY = config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
USE_OMNIVOICE = config.get("use_omnivoice", False)
OMNIVOICE_CLI_PATH = config.get("omnivoice_cli_path", "python -m omnivoice")
OMNIVOICE_REF_AUDIO = config.get("omnivoice_ref_audio", "ref_voice.wav")
OMNIVOICE_LANGUAGE = config.get("omnivoice_language", "English")
OMNIVOICE_MODEL = config.get("omnivoice_model", "")
OMNIVOICE_REF_TEXT = config.get("omnivoice_ref_text", "")
VOICE_NAME = config.get("voice_name", "en-US-EmmaNeural")  # Default to US English voice
DELAY_MIN = config.get("delay_min", 5)
DELAY_MAX = config.get("delay_max", 15)
MAX_WAIT_IMAGE = config.get("max_wait_image", 240)
LANGUAGE = config.get("language", "en")
USE_WEB2API = config.get("use_web2api", True)
WEB2API_URL = config.get("web2api_url", "http://localhost:8081/v1")
WEB2API_KEY = config.get("web2api_key", "sk-gemini")
WEB2API_MODEL_SCRIPT = config.get("web2api_model_script") or config.get("web2api_model", "gemini-3.1-pro")
WEB2API_MODEL_SEO = config.get("web2api_model_seo") or config.get("web2api_model", "gemini-3.5-flash-thinking")

BG_MUSIC_PATH = config.get("bg_music_path", "bg_music.mp3")
BG_MUSIC_VOLUME = config.get("bg_music_volume", 0.05)
SFX_PATH = config.get("sfx_path", "sfx_page.wav")
SFX_VOLUME = config.get("sfx_volume", 0.25)
SFX_ENABLED = config.get("sfx_enabled", True)

KNOWLEDGE_BASE_PATH = config.get("knowledge_base_path", "h2dev_knowledge_base.json")
SCRIPT_WORD_COUNT_MIN = config.get("script_word_count_min", 1500)
SCRIPT_WORD_COUNT_MAX = config.get("script_word_count_max", 2400)
MIN_EVIDENCE_COUNT = config.get("min_evidence_count", 3)

# --- LOAD KNOWLEDGE BASE ---
def load_knowledge_base():
    for p in [KNOWLEDGE_BASE_PATH, os.path.join(os.path.dirname(__file__), KNOWLEDGE_BASE_PATH)]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARNING] Không thể đọc knowledge base: {e}")
    print("[i] Không tìm thấy knowledge base, sử dụng prompt mặc định.")
    return None

KB = load_knowledge_base()

def build_visual_style_block(kb):
    """Xây dựng khối mô tả visual style từ knowledge base."""
    if not kb:
        return ""
    vs = kb.get("visual_style_dna", {})
    chars = kb.get("visual_style_dna", {}).get("character_variants", {})
    bgs = kb.get("visual_style_dna", {}).get("backgrounds", {})
    frames = kb.get("visual_style_dna", {}).get("proven_frame_types", {})
    ipr = kb.get("image_prompt_rules", {})
    
    lines = []
    lines.append(f"Art style: {vs.get('art_style', '')}")
    lines.append(f"Main character: {vs.get('main_character', {}).get('description', '')}")
    lines.append("Character variants:")
    for k, v in chars.items():
        lines.append(f"  - {v}")
    lines.append("Background color zones by emotional tone:")
    for k, v in bgs.items():
        lines.append(f"  - {v.get('use_for', '')}: {v.get('colors', '')}")
    lines.append(f"On-screen text: {vs.get('on_screen_text', '')}")
    lines.append("Proven frame types to use when appropriate:")
    for k, v in frames.items():
        lines.append(f"  - {k.replace('_', ' ').title()}: {v}")
    lines.append(f"Abstract-to-concrete rule: {ipr.get('abstract_to_concrete', '')}")
    lines.append(f"Scene holding rule: {ipr.get('scene_holding', '')}")
    lines.append(f"Character consistency rule: {ipr.get('character_consistency', '')}")
    return "\n".join(lines)

def validate_script(script_data):
    """Kiểm tra chất lượng script (cảnh báo không chặn)."""
    segments = script_data.get("segments", [])
    all_text = " ".join(seg.get("text", "") for seg in segments)
    word_count = len(all_text.split())
    warnings = []
    
    if word_count < SCRIPT_WORD_COUNT_MIN:
        warnings.append(f"Script quá ngắn: {word_count} từ (tối thiểu: {SCRIPT_WORD_COUNT_MIN})")
    if word_count > SCRIPT_WORD_COUNT_MAX:
        warnings.append(f"Script quá dài: {word_count} từ (tối đa: {SCRIPT_WORD_COUNT_MAX})")
    if len(segments) < 15:
        warnings.append(f"Quá ít phân cảnh: {len(segments)} (khuyến nghị ≥ 20 cho video 7-12 phút)")
    
    # Kiểm tra evidence rule: tìm các tên riêng/nghiên cứu
    # Đơn giản: đếm từ viết hoa liên tiếp (tên riêng) — heuristic
    import re
    proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', all_text)
    if len(proper_nouns) < MIN_EVIDENCE_COUNT:
        warnings.append(f"Có thể thiếu evidence: chỉ phát hiện ~{len(proper_nouns)} tên riêng (khuyến nghị ≥ {MIN_EVIDENCE_COUNT} nghiên cứu/địa danh thực tế)")
    
    if warnings:
        print("[⚠ QUALITY CHECK]")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("[✓ QUALITY CHECK] Script đạt chuẩn chất lượng.")
    return warnings


# --- SETUP DIRECTORIES ---
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- HELPERS FOR DEFAULT AUDIO RESOURCES ---
def generate_default_sfx(output_path):
    print(f"  [i] Đang tự động tạo hiệu ứng âm thanh lật trang cục bộ: {output_path}...")
    try:
        sample_rate = 22050
        duration = 0.4 # 400 ms
        num_samples = int(sample_rate * duration)
        
        # Để tạo tiếng giấy lật (sột soạt), ta dùng nhiễu trắng được làm mịn (lowpass filtered noise)
        import random
        raw_noise = [random.uniform(-1.0, 1.0) for _ in range(num_samples)]
        
        # Bộ lọc làm mịn đơn giản (Moving Average) để giảm tần số quá cao (giúp giống giấy hơn tiếng xè xè)
        filtered_noise = []
        window_size = 5
        for i in range(num_samples):
            start_idx = max(0, i - window_size)
            end_idx = min(num_samples, i + 1)
            window = raw_noise[start_idx:end_idx]
            filtered_noise.append(sum(window) / len(window))
            
        with wave.open(output_path, 'wb') as wav_file:
            wav_file.setnchannels(1) # mono
            wav_file.setsampwidth(2) # 16-bit
            wav_file.setframerate(sample_rate)
            
            for i in range(num_samples):
                t = i / sample_rate
                # Envelope dạng hình quả chuông (lên nhanh rồi xuống chậm)
                # Phát triển nhanh từ 0 đến cực đại ở 0.12s, sau đó nhỏ dần về 0
                if t < 0.12:
                    envelope = math.sin(math.pi * (t / 0.12) / 2.0)
                else:
                    envelope = math.exp(-(t - 0.12) * 8.0)
                
                # Thêm biến động biên độ ngẫu nhiên nhỏ mô phỏng tiếng sột soạt ma sát giấy
                envelope *= (0.85 + 0.15 * math.sin(2.0 * math.pi * 50.0 * t))
                
                value = int(filtered_noise[i] * envelope * 12000.0) # giới hạn biên độ
                data = struct.pack('<h', value)
                wav_file.writeframesraw(data)
        print("  [✓] Tạo hiệu ứng âm thanh lật trang thành công.")
        return True
    except Exception as e:
        print(f"  [WARNING] Không thể tạo hiệu ứng âm thanh mặc định: {e}")
        return False

def download_default_bg_music(output_path):
    print(f"  [i] Đang tự động tải nhạc nền mặc định: {output_path}...")
    try:
        url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        urllib.request.urlretrieve(url, output_path)
        print("  [✓] Tải nhạc nền mặc định thành công.")
        return True
    except Exception as e:
        print(f"  [WARNING] Không thể tải nhạc nền mặc định từ internet: {e}")
        return False

# --- 1. MÔ-ĐUN LÊN KỊCH BẢN (GEMINI API / WEB2API) ---
def extract_json_from_text(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Tìm kiếm khối JSON bằng biểu thức chính quy
        m = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError as e:
                raise ValueError(f"Found JSON block but failed to parse: {e}")
        raise ValueError(f"Could not find any JSON block in response: {text[:200]}")

def run_script_generator(topic):
    if not USE_WEB2API and not GEMINI_API_KEY:
        print("[ERROR] Chưa cấu hình gemini_api_key trong file config.json hoặc biến môi trường.")
        return None
        
    # Kiểm tra xem topic có phải là file không
    is_file_input = False
    file_content = ""
    paths_to_try = [topic, os.path.join("..", topic), os.path.join("d:\\Creator video", topic)]
    for p in paths_to_try:
        if os.path.exists(p) and os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    file_content = f.read().strip()
                if file_content:
                    is_file_input = True
                    print(f"[+] Đã nhận dạng đầu vào là file kịch bản: {p}")
                    break
            except Exception as e:
                print(f"[WARNING] Không thể đọc file {p}: {e}")

    # Kiểm tra xem file có chứa timestamp đầu dòng hay không (dạng [mm:ss] hoặc [hh:mm:ss])
    is_timestamped_file = False
    if is_file_input:
        lines = file_content.split("\n")
        timestamp_lines = 0
        total_non_empty = 0
        for l in lines:
            l = l.strip()
            if not l:
                continue
            total_non_empty += 1
            if re.match(r'^\[\d{2}:\d{2}\]', l) or re.match(r'^\[\d{2}:\d{2}:\d{2}\]', l):
                timestamp_lines += 1
        if total_non_empty > 0 and timestamp_lines / total_non_empty > 0.5:
            is_timestamped_file = True
            print(f"[+] Đã nhận dạng file kịch bản có sẵn timestamp: {topic}")

    if is_timestamped_file:
        segments = []
        import shutil
        outputs_dir = os.path.join("..", "h2dev_flow_local", "outputs")
        if not os.path.exists(outputs_dir):
            outputs_dir = os.path.join("d:\\Creator video", "h2dev_flow_local", "outputs")
            
        print(f"[+] Đang tìm kiếm ảnh đã có sẵn tại: {outputs_dir}...")
        
        idx = 0
        for l in lines:
            l = l.strip()
            if not l:
                continue
            match = re.match(r'^\[(\d{2}):(\d{2})\]\s*(.*)$', l)
            prefix = ""
            text = ""
            if match:
                prefix = f"{match.group(1)}_{match.group(2)}"
                text = match.group(3).strip()
            else:
                match_long = re.match(r'^\[(\d{2}):(\d{2}):(\d{2})\]\s*(.*)$', l)
                if match_long:
                    prefix = f"{match_long.group(1)}_{match_long.group(2)}_{match_long.group(3)}"
                    text = match_long.group(4).strip()
            
            if prefix:
                # Tìm file ảnh bắt đầu bằng prefix
                found_img = None
                if os.path.exists(outputs_dir):
                    for fname in os.listdir(outputs_dir):
                        if fname.startswith(prefix) and fname.lower().endswith((".png", ".jpg", ".jpeg")):
                            found_img = os.path.join(outputs_dir, fname)
                            break
                
                # Copy sang thư mục temp
                dest_file = os.path.join(TEMP_DIR, f"image_{idx}.png")
                if found_img:
                    shutil.copy(found_img, dest_file)
                else:
                    print(f"  [WARNING] Không tìm thấy ảnh cho prefix: {prefix}")
                
                segments.append({
                    "text": text,
                    "prompt": f"Pre-generated image for {prefix}",
                })
                idx += 1
                
        script_data = {
            "title": "Doodle Video from Timestamped Script",
            "segments": segments
        }
        
        script_path = os.path.join(TEMP_DIR, "script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
            
        print(f"[✓] Đã nạp {len(segments)} phân cảnh từ file kịch bản có sẵn timestamp.")
        return script_data

    # --- XÂY DỰNG SYSTEM PROMPT ĐẦY ĐỦ DNA TỪ KNOWLEDGE BASE ---
    visual_block = build_visual_style_block(KB)
    
    # Lấy thông tin DNA từ knowledge base
    kb_content = KB.get("content_dna", {}) if KB else {}
    kb_angles = KB.get("viral_topic_angles", []) if KB else []
    
    # Xây dựng phần script rules
    hook_formula = kb_content.get("hook_formula", "Open with a sensory 2nd-person moment, then pivot with a reframe and contrast with a modern statistic.")
    narrative_arc = kb_content.get("narrative_arc", ["Hook", "Reframe", "Evidence stack", "Reconstruct scene", "Counterintuitive twist", "Modern mirror", "Echo closing"])
    evidence_rule = kb_content.get("evidence_rule", "Include at least 3 real named researchers, studies, or archaeological sites.")
    jargon_rule = kb_content.get("jargon_rule", "No jargon without plain-English explanation.")
    ending_rule = kb_content.get("ending_rule", "End by reflecting the truth back onto the viewer's modern life.")
    humor_rule = kb_content.get("humor_rule", "")
    script_rhythm = kb_content.get("script_rhythm", "Short sentence. Short sentence. One longer sentence. Short sentence. Question?")
    
    arc_text = " → ".join(narrative_arc)
    angles_text = "\n".join([f"  {i+1}. {a['template']}: {a['description']}" for i, a in enumerate(kb_angles)]) if kb_angles else ""
    
    if LANGUAGE == "en":
        lang_note = "Write the narration script in English, strictly in 2nd-person ('you', 'your ancestors', 'your body', 'your brain'). Never use 'we' or 'I'."
        title_example = '"Viral video title"'
        text_example = '"The English narration text for this segment."'
    else:
        lang_note = "Write the narration script in Vietnamese, strictly in 2nd-person ('bạn', 'tổ tiên của bạn', 'cơ thể của bạn', 'não bộ của bạn'). Never use 'chúng ta' or 'tôi'."
        title_example = '"Tên video viral"'
        text_example = '"Lời thuyết minh cho phân cảnh này."'
    
    system_instruction = (
        "You are a viral YouTube video creation engine for a hand-drawn doodle animation channel. "
        "You know exactly how this channel looks, sounds, and why it goes viral.\n\n"
        
        f"LANGUAGE: {lang_note}\n\n"
        
        "=== SCRIPT RULES ===\n"
        f"- Length: {SCRIPT_WORD_COUNT_MIN}–{SCRIPT_WORD_COUNT_MAX} words (roughly a 7–12 minute video).\n"
        "- Scene split rule: Split the entire script into small, atomic visual scenes. The text for each segment/scene MUST be VERY SHORT (1-3 sentences max). A 1500-word script should have around 100-150 segments.\n"
        "- Pure narration only — no headers, no bullet points, no visual cues, no stage directions, no parenthetical notes.\n"
        f"- Rhythm: {script_rhythm}\n"
        f"- Hook formula: {hook_formula}\n"
        f"- Narrative arc: {arc_text}\n"
        f"- Evidence rule: {evidence_rule}\n"
        f"- Jargon rule: {jargon_rule}\n"
        + (f"- Humor rule: {humor_rule}\n" if humor_rule else "")
        + f"- Ending rule: {ending_rule}\n\n"
        
        + (f"=== PROVEN VIRAL TOPIC ANGLES ===\n{angles_text}\n\n" if angles_text else "")
        +
        "=== VISUAL STYLE DNA (for image prompts) ===\n"
        f"{visual_block}\n\n"
        
        "=== IMAGE PROMPT INSTRUCTIONS ===\n"
        "For each segment of the script, you must also write a highly detailed English image prompt (prompts are ALWAYS in English regardless of script language).\n"
        "Each image prompt MUST:\n"
        "- Begin with the style anchor: 'Hand-drawn 2D doodle cartoon animation, flat solid colors, bold black hand-drawn outlines, slightly wobbly imperfect marker lines,'\n"
        "- Describe which characters are present (stating their hair/head type explicitly), their expression, objects in the scene, the flat background color zone matching the emotional tone, and any on-screen text/labels.\n"
        "- Translate abstract narration into concrete visuals (e.g., 'survival was a struggle' → stick figure pushing a boulder labeled 'SURVIVAL').\n"
        "- End with the style lock: 'no gradients, no drop shadows, no photographic textures, no photorealism, no 3D render, no realistic faces, no anime, 16:9 widescreen, simple educational YouTube explainer doodle style.'\n"
        "- Hold the same scene across consecutive segments if they describe the same moment — only adjust character expression or add one element. Do NOT create a new scene every segment.\n\n"
        
        "=== OUTPUT FORMAT ===\n"
        "You MUST return the output strictly in the following JSON format without any markdown wrappers or enclosing blocks:\n"
        "{\n"
        f"  \"title\": {title_example},\n"
        "  \"segments\": [\n"
        "    {\n"
        f"      \"text\": {text_example},\n"
        "      \"prompt\": \"A detailed English image prompt describing the doodle scene.\"\n"
        "    }\n"
        "  ]\n"
        "}"
    )

    if is_file_input:
        print(f"[+] Đang gửi yêu cầu phân tích kịch bản từ file để sinh prompt vẽ ảnh...")
        prompt = (
            f"Here is an existing script for a video. Please parse it and generate "
            f"detailed doodle image prompts for each paragraph/segment. Maintain the exact narrative texts "
            f"from the original script. Return the result in the required JSON format.\n\n"
            f"Original Script:\n{file_content}"
        )
    else:
        print(f"[+] Đang gửi yêu cầu sinh kịch bản cho chủ đề: '{topic}'...")
        if LANGUAGE == "en":
            prompt = f"Please write a complete doodle video script about the topic: {topic}"
        else:
            prompt = f"Hãy viết một kịch bản video doodle hoàn chỉnh về chủ đề: {topic}"
            
    response_text = ""
    try:
        if USE_WEB2API:
            import requests
            print(f"[+] Gọi API qua gemini-web2api tại {WEB2API_URL} (model: {WEB2API_MODEL_SCRIPT})...")
            url = f"{WEB2API_URL}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {WEB2API_KEY}"
            }
            payload = {
                "model": WEB2API_MODEL_SCRIPT,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ]
            }
            res = requests.post(url, json=payload, headers=headers, timeout=180)
            if res.status_code != 200:
                print(f"[ERROR] HTTP {res.status_code}: {res.text}")
                return None
            res_data = res.json()
            response_text = res_data["choices"][0]["message"]["content"]
        else:
            print(f"[+] Gọi API trực tiếp bằng Google Generative AI...")
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config={"response_mime_type": "application/json"},
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            response_text = response.text
            
        script_data = extract_json_from_text(response_text)
        
        # Validation: kiểm tra chất lượng script
        validate_script(script_data)
        
        script_path = os.path.join(TEMP_DIR, "script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
            
        print(f"[✓] Đã tạo và lưu kịch bản tại: {script_path}")
        return script_data
    except Exception as e:
        print(f"[ERROR] Lỗi khi sinh kịch bản: {e}")
        if response_text:
            print(f"[Debug] Response text: {response_text[:500]}...")
        return None

# --- 2. MÔ-ĐUN TẠO GIỌNG ĐỌC & TÍNH TOÁN TIMESTAMPS ---
async def generate_segment_audio_edge(text, output_path):
    # Sử dụng edge-tts để tạo giọng đọc tự nhiên (tiếng Việt neural) miễn phí
    communicate = edge_tts.Communicate(text, VOICE_NAME)
    await communicate.save(output_path)

def generate_voiceover_and_timestamps(script_data):
    print("[+] Dang bat dau tao giong doc va tinh toan mốc thoi gian (timestamps)...")
    segments = script_data.get("segments", [])
    
    audio_clips = []
    updated_segments = []
    current_time = 0.0
    
    for idx, seg in enumerate(segments):
        text = seg["text"]
        print(f"  - Phân canh {idx+1}/{len(segments)}: Thuyết minh -> '{text[:50]}...'")
        
        # Đường dẫn file âm thanh phân cảnh
        seg_audio_path = os.path.join(TEMP_DIR, f"segment_{idx}.wav")
        
        # Kiểm tra cache âm thanh đã tồn tại và hợp lệ
        if os.path.exists(seg_audio_path) and os.path.getsize(seg_audio_path) > 1024:
            print("    [i] Âm thanh phân cảnh đã tồn tại, bỏ qua tạo mới.")
        elif USE_OMNIVOICE:
            # Chạy OmniVoice cục bộ
            try:
                cmd = f'{OMNIVOICE_CLI_PATH} --text "{text}" --ref_audio "{OMNIVOICE_REF_AUDIO}" --output "{seg_audio_path}"'
                if OMNIVOICE_MODEL:
                    cmd += f' --model "{OMNIVOICE_MODEL}"'
                if OMNIVOICE_LANGUAGE:
                    cmd += f' --language "{OMNIVOICE_LANGUAGE}"'
                if OMNIVOICE_REF_TEXT:
                    cmd += f' --ref_text "{OMNIVOICE_REF_TEXT}"'
                
                print(f"    [+] Chạy OmniVoice: {cmd}")
                subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"    [WARNING] OmniVoice lỗi ({e}), tự động chuyển sang dùng edge-tts...")
                asyncio.run(generate_segment_audio_edge(text, seg_audio_path))
        else:
            # Mặc định sử dụng edge-tts
            asyncio.run(generate_segment_audio_edge(text, seg_audio_path))
            
        # Đọc thời lượng tệp âm thanh vừa tạo
        try:
            clip = AudioFileClip(seg_audio_path)
            duration = clip.duration
            audio_clips.append(clip)
            
            start_time = current_time
            end_time = current_time + duration
            current_time = end_time
            
            # Lưu lại thông tin mốc thời gian vào phân cảnh
            updated_seg = {
                "text": text,
                "prompt": seg["prompt"],
                "start": start_time,
                "end": end_time,
                "duration": duration,
                "audio_path": seg_audio_path
            }
            updated_segments.append(updated_seg)
        except Exception as e:
            print(f"    [ERROR] Khong the doc file am thanh: {e}")
            continue
            
    # Ghép nối các file âm thanh phân cảnh thành tệp thuyết minh đầy đủ
    if audio_clips:
        full_audio_path = os.path.join(TEMP_DIR, "full_narration.wav")
        full_clip = concatenate_audioclips(audio_clips)
        full_clip.write_audiofile(full_audio_path, fps=44100, logger=None)
        
        # Lưu timestamps.json
        timestamps_path = os.path.join(TEMP_DIR, "timestamps.json")
        with open(timestamps_path, "w", encoding="utf-8") as f:
            json.dump(updated_segments, f, ensure_ascii=False, indent=2)
            
        print(f"[✓] Da ghep file am thanh goc tai: {full_audio_path}")
        print(f"[✓] Da tinh toan xong timestamps luu tai: {timestamps_path}")
        return updated_segments, full_audio_path
        
    return None, None

# --- 3. MÔ-ĐUN SINH ẢNH TỰ ĐỘNG (PLAYWRIGHT GOOGLE FLOW) ---
def find_prompt_input(page):
    selectors = [
        '[data-slate-editor="true"]',
        '[contenteditable="true"][role="textbox"]',
        '[role="textbox"][aria-multiline="true"]',
        'div[role="textbox"]',
        '[contenteditable="true"]',
        '[contenteditable=""]',
        "textarea",
    ]
    for sel in selectors:
        locator = page.locator(sel)
        if locator.count() > 0:
            for i in range(locator.count()):
                el = locator.nth(i)
                if el.is_visible():
                    return el
            return locator.first
    return None

def set_prompt_text(page, input_el, text):
    is_content_editable = input_el.evaluate("el => el.isContentEditable")
    if is_content_editable:
        input_el.evaluate("""(el, val) => {
            try {
                const sel = window.getSelection();
                sel.removeAllRanges();
                const range = document.createRange();
                range.selectNodeContents(el);
                sel.addRange(range);
                el.dispatchEvent(new InputEvent("beforeinput", {
                    inputType: "deleteContentBackward",
                    bubbles: true, cancelable: true, composed: true
                }));
            } catch(e) {}
            el.dispatchEvent(new InputEvent("beforeinput", {
                inputType: "insertText",
                data: val,
                bubbles: true, cancelable: true, composed: true
            }));
        }""", text)
    else:
        input_el.fill(text)

def wake_prompt_box(page):
    input_el = find_prompt_input(page)
    if input_el:
        input_el.click()
        time.sleep(0.2)
        return input_el
    arrow = page.locator('button:has-text("arrow_forward"), [role="button"]:has-text("arrow_forward")')
    if arrow.count() > 0:
        first_arrow = arrow.first
        if first_arrow.is_visible():
            box = first_arrow.bounding_box()
            if box:
                page.mouse.click(box['x'] - 150, box['y'] + box['height'] / 2)
                time.sleep(0.3)
                return find_prompt_input(page)
    return find_prompt_input(page)

def get_completed_images(page):
    return page.evaluate("""() => {
        return Array.from(document.querySelectorAll('img'))
            .filter(img => {
                const src = img.currentSrc || img.src || "";
                if (!/^https?:|^blob:/.test(src)) return false;
                const w = img.naturalWidth || img.width;
                const h = img.naturalHeight || img.height;
                return w >= 256 && h >= 256;
            })
            .map(img => img.currentSrc || img.src);
    }""")

def get_image_data_url(page, src):
    return page.evaluate("""async (src) => {
        const res = await fetch(src);
        const blob = await res.blob();
        return await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }""", src)

def generate_images_workflow(segments, thumbnail_prompt=None):
    print("[+] Dang chuan bi kết nối Chrome de tu dong tao anh tren Google Flow...")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CHROME_CDP_URL)
        except Exception as e:
            print(f"[ERROR] Khong the ket noi den Chrome debug (port 9222): {e}")
            print("Vui long mo Chrome bang 'run_chrome.bat' (ben trong folder h2dev_flow_local) truoc khi chay script pipeline.")
            return False
            
        context = browser.contexts[0]
        flow_page = None
        for page in context.pages:
            if "/tools/flow" in page.url:
                flow_page = page
                break
        if not flow_page:
            for page in context.pages:
                if "/fx/" in page.url:
                    flow_page = page
                    break
        if not flow_page:
            print("[ERROR] Khong tim thay trang Google Flow trong trinh duyet Chrome.")
            print("Vui long mo link: https://labs.google/fx/tools/flow tren Chrome debug.")
            return False
            
        print(f"[OK] Da ket noi voi Google Flow: '{flow_page.title()}'")
        
        for idx, seg in enumerate(segments):
            prompt = seg["prompt"]
            # Thêm style anchors nếu chưa có
            if "Hand-drawn" not in prompt:
                style_anchor = "Hand-drawn 2D doodle cartoon animation, flat solid colors, bold black hand-drawn outlines, slightly wobbly imperfect marker lines, "
                style_lock = ", no gradients, no drop shadows, no photographic textures, no photorealism, no 3D render, no realistic faces, no anime, 16:9 widescreen, simple educational YouTube explainer doodle style."
                prompt = f"{style_anchor}{prompt}{style_lock}"
                
            dest_file = os.path.join(TEMP_DIR, f"image_{idx}.png")
            print(f"  - Dang tao anh {idx+1}/{len(segments)}: {prompt[:60]}...")
            
            if os.path.exists(dest_file) and os.path.getsize(dest_file) > 1024:
                print("    [i] Anh da ton tai, bo qua.")
                continue
                
            input_el = wake_prompt_box(flow_page)
            if not input_el:
                print("    [ERROR] Khong tim thay o nhap prompt. Thu lai...")
                continue
                
            input_el.click()
            time.sleep(0.1)
            set_prompt_text(flow_page, input_el, prompt)
            time.sleep(0.5)
            
            baseline = set(get_completed_images(flow_page))
            flow_page.keyboard.press("Enter")
            
            # Đợi ảnh mới
            start_time = time.time()
            new_image_src = None
            while time.time() - start_time < MAX_WAIT_IMAGE:
                current_imgs = get_completed_images(flow_page)
                new_imgs = [src for src in current_imgs if src not in baseline]
                if new_imgs:
                    new_image_src = new_imgs[0]
                    break
                time.sleep(2)
                
            if new_image_src:
                time.sleep(1.5)
                try:
                    data_url = get_image_data_url(flow_page, new_image_src)
                    header, encoded = data_url.split(",", 1)
                    data = base64.b64decode(encoded)
                    with open(dest_file, "wb") as f_img:
                        f_img.write(data)
                    print("    [✓] Luu anh thanh cong.")
                except Exception as e:
                    print(f"    [ERROR] Loi khi tai anh: {e}")
            else:
                print("    [ERROR] Cho anh qua thoi gian quy dinh (Timeout). Bo qua...")
                
            if idx < len(segments) - 1:
                sleep_time = random.uniform(DELAY_MIN, DELAY_MAX)
                time.sleep(sleep_time)
                
        # Nếu có thumbnail prompt, tiến hành sinh ảnh thumbnail
        if thumbnail_prompt:
            prompt = thumbnail_prompt
            if "Hand-drawn" not in prompt:
                style_anchor = "Hand-drawn 2D doodle cartoon animation, flat solid colors, bold black hand-drawn outlines, slightly wobbly imperfect marker lines, "
                style_lock = ", no gradients, no drop shadows, no photographic textures, no photorealism, no 3D render, no realistic faces, no anime, 16:9 widescreen, simple educational YouTube explainer doodle style."
                prompt = f"{style_anchor}{prompt}{style_lock}"
                
            dest_file = os.path.join(OUTPUT_DIR, "thumbnail.png")
            print(f"  - Dang tao anh Thumbnail: {prompt[:60]}...")
            
            if os.path.exists(dest_file) and os.path.getsize(dest_file) > 1024:
                print("    [i] Anh Thumbnail da ton tai, bo qua.")
            else:
                input_el = wake_prompt_box(flow_page)
                if input_el:
                    input_el.click()
                    time.sleep(0.1)
                    set_prompt_text(flow_page, input_el, prompt)
                    time.sleep(0.5)
                    
                    baseline = set(get_completed_images(flow_page))
                    flow_page.keyboard.press("Enter")
                    
                    start_time = time.time()
                    new_image_src = None
                    while time.time() - start_time < MAX_WAIT_IMAGE:
                        current_imgs = get_completed_images(flow_page)
                        new_imgs = [src for src in current_imgs if src not in baseline]
                        if new_imgs:
                            new_image_src = new_imgs[0]
                            break
                        time.sleep(2)
                        
                    if new_image_src:
                        time.sleep(1.5)
                        try:
                            data_url = get_image_data_url(flow_page, new_image_src)
                            header, encoded = data_url.split(",", 1)
                            data = base64.b64decode(encoded)
                            with open(dest_file, "wb") as f_img:
                                f_img.write(data)
                            print(f"    [✓] Luu anh Thumbnail thanh cong tai: {dest_file}")
                        except Exception as e:
                            print(f"    [ERROR] Loi khi tai anh Thumbnail: {e}")
                            
        return True

# --- 4. MÔ-ĐUN DỰNG & RENDER VIDEO (MOVIEPY + FFMPEG) ---
def format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        ms = 0
        s += 1
        if s == 60:
            s = 0
            m += 1
            if m == 60:
                m = 0
                h += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def generate_srt_file(segments, output_path):
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for idx, seg in enumerate(segments):
                f.write(f"{idx + 1}\n")
                start_str = format_srt_time(seg["start"])
                end_str = format_srt_time(seg["end"])
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{seg['text']}\n\n")
        print(f"[✓] Da tao file phu de SRT tai: {output_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Khong the tao file phu de SRT: {e}")
        return False

def assemble_final_video(segments, audio_path, output_video_path):
    print("[+] Dang bat dau ghep noi va xuat video .mp4...")
    video_clips = []
    
    for idx, seg in enumerate(segments):
        img_path = os.path.join(TEMP_DIR, f"image_{idx}.png")
        duration = seg["duration"]
        
        if not os.path.exists(img_path):
            print(f"  [WARNING] Khong tim thay anh image_{idx}.png, bo qua phan canh nay.")
            continue
            
        try:
            # Tạo clip ảnh tĩnh có thời lượng khớp với câu thuyết minh tương ứng
            img_clip = ImageClip(img_path).with_duration(duration)
            
            # Áp dụng hiệu ứng Ken Burns zoom-in chuyển động nhẹ bằng resized() của MoviePy 2.x
            # Phóng to nhẹ từ 1.0 đến 1.04 lần thời lượng của clip
            img_clip = img_clip.resized(lambda t: 1.0 + 0.04 * (t / duration))
            
            video_clips.append(img_clip)
        except Exception as e:
            print(f"  [ERROR] Loi khi doc file anh: {e}")
            
    if not video_clips:
        print("[ERROR] Khong co anh nao hop le de ghep thanh video.")
        return False
        
    try:
        # Ghép nối các clip ảnh
        video = concatenate_videoclips(video_clips, method="compose")
        # Luồng âm thanh phụ trợ (BGM và SFX)
        audio_clips = []
        
        # 1. Âm thanh thuyết minh gốc (Main Narration)
        narration_clip = AudioFileClip(audio_path)
        audio_clips.append(narration_clip)
        
        video_duration = narration_clip.duration
        
        # 2. Nhạc nền (BGM)
        # Tự động tải nhạc nền mặc định nếu chưa có
        if BG_MUSIC_PATH == "bg_music.mp3" and not os.path.exists(BG_MUSIC_PATH):
            download_default_bg_music(BG_MUSIC_PATH)
            
        resolved_bg_path = None
        for p in [BG_MUSIC_PATH, os.path.join(os.path.dirname(audio_path), BG_MUSIC_PATH), os.path.basename(BG_MUSIC_PATH)]:
            if p and os.path.exists(p) and os.path.isfile(p):
                resolved_bg_path = p
                break
                
        if resolved_bg_path:
            try:
                print(f"  [+] Đang lồng nhạc nền: {resolved_bg_path} (âm lượng: {BG_MUSIC_VOLUME})")
                import moviepy.audio.fx as afx
                bg_clip = AudioFileClip(resolved_bg_path)
                # Loop nhạc nền cho khớp thời lượng video và giảm âm lượng xuống
                bg_clip = bg_clip.with_effects([afx.AudioLoop(duration=video_duration)])
                bg_clip = bg_clip.with_volume_scaled(BG_MUSIC_VOLUME)
                audio_clips.append(bg_clip)
            except Exception as e:
                print(f"  [WARNING] Lỗi khi nạp nhạc nền: {e}")
        else:
            print(f"  [i] Không tìm thấy tệp nhạc nền '{BG_MUSIC_PATH}'. Bỏ qua nhạc nền.")
            
        # 3. Hiệu ứng âm thanh (SFX) tại mỗi điểm chuyển cảnh
        # Tự động tạo SFX mặc định nếu chưa có
        if SFX_ENABLED and SFX_PATH == "sfx_page.wav" and not os.path.exists(SFX_PATH):
            generate_default_sfx(SFX_PATH)
            
        resolved_sfx_path = None
        for p in [SFX_PATH, os.path.join(os.path.dirname(audio_path), SFX_PATH), os.path.basename(SFX_PATH)]:
            if p and os.path.exists(p) and os.path.isfile(p):
                resolved_sfx_path = p
                break
                
        if SFX_ENABLED and resolved_sfx_path:
            try:
                print(f"  [+] Đang chèn hiệu ứng âm thanh chuyển cảnh: {resolved_sfx_path} (âm lượng: {SFX_VOLUME})")
                sfx_template = AudioFileClip(resolved_sfx_path).with_volume_scaled(SFX_VOLUME)
                sfx_duration = sfx_template.duration
                
                for idx, seg in enumerate(segments):
                    # Không chèn SFX ở phân cảnh đầu tiên để bắt đầu mượt mà
                    if idx == 0:
                        continue
                    start_t = seg["start"]
                    # Đảm bảo hiệu ứng nằm trong thời lượng video
                    if start_t + sfx_duration <= video_duration:
                        sfx_segment = sfx_template.with_start(start_t)
                        audio_clips.append(sfx_segment)
            except Exception as e:
                print(f"  [WARNING] Lỗi khi nạp hiệu ứng âm thanh SFX: {e}")
        elif SFX_ENABLED:
            print(f"  [i] Không tìm thấy tệp hiệu ứng âm thanh '{SFX_PATH}'. Bỏ qua hiệu ứng âm thanh.")
            
        # Trộn tất cả âm thanh lại với nhau
        if len(audio_clips) > 1:
            final_audio = CompositeAudioClip(audio_clips)
        else:
            final_audio = narration_clip
            
        video = video.with_audio(final_audio)
        
        # Render xuất tệp tin video thành phẩm
        print(f"[+] Dang render video tai: {output_video_path}...")
        video.write_videoplayback = False # avoid showing player
        video.write_videofile(
            output_video_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=os.path.join(TEMP_DIR, "temp_audio.m4a"),
            remove_temp=True,
            logger=None
        )
        print("[✓] Render video hoan tat!")
        return True
    except Exception as e:
        print(f"[ERROR] Loi render video: {e}")
        return False

def run_youtube_seo_generator(script_data, segments):
    print("[+] Đang tự động tạo tiêu đề, mô tả SEO và tag cho YouTube...")
    
    # Chuẩn bị danh sách phân cảnh kèm mốc thời gian để gửi tới LLM
    segments_summary = []
    for idx, seg in enumerate(segments):
        start_sec = seg["start"]
        m = int(start_sec // 60)
        s = int(start_sec % 60)
        time_str = f"{m:02d}:{s:02d}"
        segments_summary.append(f"[{time_str}] {seg['text']}")
    segments_text = "\n".join(segments_summary)
    
    # Lấy SEO DNA từ knowledge base
    kb_seo = KB.get("seo_dna", {}) if KB else {}
    kb_angles = KB.get("viral_topic_angles", []) if KB else []
    kb_visual = KB.get("visual_style_dna", {}) if KB else {}
    
    title_rules = kb_seo.get("title_rules", "One scroll-stopping, curiosity-driven title under 70 characters.")
    desc_structure = kb_seo.get("description_structure", [])
    desc_text = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(desc_structure)]) if desc_structure else "Write a compelling description with chapters."
    tags_rules = kb_seo.get("tags_rules", "25–40 SEO tags, comma-separated.")
    angles_text = "\n".join([f"  - {a['template']}" for a in kb_angles]) if kb_angles else ""
    
    # Thumbnail visual DNA
    thumbnail_style = kb_visual.get("art_style", "Hand-drawn 2D doodle cartoon animation")
    chars = kb_visual.get("character_variants", {})
    char_text = "; ".join([f"{v}" for v in chars.values()]) if chars else "stick figure with orange hair"
    
    system_instruction = (
        "You are a YouTube growth expert specializing in viral video SEO for a hand-drawn doodle animation channel. "
        "You deeply understand what makes educational content go viral.\n\n"
        
        "=== TITLE RULES ===\n"
        f"{title_rules}\n"
        + (f"Proven viral title angles for this channel:\n{angles_text}\n\n" if angles_text else "\n")
        +
        "=== DESCRIPTION STRUCTURE ===\n"
        f"{desc_text}\n\n"
        
        "=== TAGS RULES ===\n"
        f"{tags_rules}\n\n"
        
        "=== THUMBNAIL PROMPT RULES ===\n"
        f"The thumbnail must match this art style: {thumbnail_style}\n"
        f"Character variants: {char_text}\n"
        "The thumbnail should be eye-catching, curiosity-driven, and clearly convey the video's topic in a single glance.\n\n"
        
        "=== OUTPUT FORMAT ===\n"
        "You MUST return the output strictly in the following JSON format without any markdown wrappers or enclosing blocks:\n"
        "{\n"
        "  \"titles\": [\"Title 1\", \"Title 2\", \"Title 3\"],\n"
        "  \"description\": \"Video description text with chapters...\",\n"
        "  \"tags\": [\"keyword1\", \"keyword2\", ... (25-40 tags)],\n"
        "  \"hashtags\": [\"#hash1\", \"#hash2\", ... (15-25 hashtags)],\n"
        "  \"thumbnail_prompt\": \"A detailed English image prompt describing the thumbnail scene.\"\n"
        "}"
    )
    
    prompt = (
        f"Generate YouTube SEO metadata for this video script with timestamps.\n\n"
        f"Original Timestamps & Script:\n{segments_text}"
    )
    
    response_text = ""
    try:
        if USE_WEB2API:
            import requests
            url = f"{WEB2API_URL}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {WEB2API_KEY}"
            }
            payload = {
                "model": WEB2API_MODEL_SEO,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ]
            }
            res = requests.post(url, json=payload, headers=headers, timeout=180)
            if res.status_code == 200:
                response_text = res.json()["choices"][0]["message"]["content"]
            else:
                print(f"[WARNING] Web2API response error: {res.text}")
        else:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config={"response_mime_type": "application/json"},
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            response_text = response.text
            
        seo_data = extract_json_from_text(response_text)
        return seo_data
    except Exception as e:
        print(f"[WARNING] Lỗi khi tạo SEO metadata: {e}")
        # Trả về metadata mặc định dự phòng
        return {
            "titles": [script_data.get("title", "Doodle Video")],
            "description": f"A video about this topic.\n\nTimestamps:\n{segments_text}",
            "tags": ["doodle", "animation"],
            "hashtags": ["#doodle", "#animation"],
            "thumbnail_prompt": "A hand-drawn 2D doodle cartoon thumbnail."
        }

def clean_filename(name):
    # Loại bỏ ký tự đặc biệt không hợp lệ trong Windows
    cleaned = re.sub(r'[\\/:*?"<>|]', '', name)
    # Thay khoảng trắng bằng dấu gạch dưới
    cleaned = re.sub(r'\s+', '_', cleaned)
    # Giới hạn độ dài và loại bỏ gạch dưới ở đầu/cuối
    return cleaned[:50].strip('_')

# --- HÀM KHỞI CHẠY PIPELINE ---
def run_pipeline(topic):
    # Đọc URL kết nối debug Chrome
    global CHROME_CDP_URL
    CHROME_CDP_URL = "http://localhost:9222"
    
    # Xác định thư mục dự án động dựa trên chủ đề hoặc tên file kịch bản
    if topic.lower().endswith(".txt") or "\\" in topic or "/" in topic:
        base = os.path.splitext(os.path.basename(topic))[0]
        project_name = clean_filename(base)
    else:
        project_name = clean_filename(topic)
        
    project_dir = os.path.join("projects", project_name)
    
    global TEMP_DIR, OUTPUT_DIR
    TEMP_DIR = os.path.join(project_dir, "temp")
    OUTPUT_DIR = os.path.join(project_dir, "outputs")
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print(" KHOI CHAY AUTOMATED DOODLE VIDEO PIPELINE")
    print(f" [PROJ] Thu muc du an: {project_dir}")
    print("=" * 60)
    
    # Bước 1: Sinh kịch bản & prompt
    script_data = run_script_generator(topic)
    if not script_data:
        return
        
    # Bước 2: Tạo âm thanh thuyết minh & tính toán mốc thời gian
    segments, audio_path = generate_voiceover_and_timestamps(script_data)
    if not segments or not audio_path:
        print("[ERROR] Tao am thanh & timestamps that bai.")
        return
        
    # Bước 3: Tạo SEO metadata (Tiêu đề, Mô tả, Tags, Thumbnail Prompt)
    seo_data = run_youtube_seo_generator(script_data, segments)
    thumbnail_prompt = seo_data.get("thumbnail_prompt") if seo_data else None
    
    # Lưu file JSON và TXT cho SEO metadata ngay sau khi tạo
    if seo_data:
        seo_json_path = os.path.join(OUTPUT_DIR, "youtube_metadata.json")
        with open(seo_json_path, "w", encoding="utf-8") as f:
            json.dump(seo_data, f, ensure_ascii=False, indent=2)
            
        seo_txt_path = os.path.join(OUTPUT_DIR, "youtube_metadata.txt")
        with open(seo_txt_path, "w", encoding="utf-8") as f:
            f.write("=== YOUTUBE VIDEO METADATA ===\n\n")
            f.write("--- TIEU DE GAY TO MAU / TITLE SUGGESTIONS ---\n")
            for i, t in enumerate(seo_data.get("titles", [])):
                f.write(f"{i+1}. {t}\n")
            f.write("\n")
            f.write("--- MO TA CHUAN SEO / DESCRIPTION (CONTAINING CHAPTERS) ---\n")
            f.write(seo_data.get("description", ""))
            f.write("\n\n")
            f.write("--- TAGS / KEYWORDS ---\n")
            f.write(", ".join(seo_data.get("tags", [])))
            f.write("\n\n")
            f.write("--- HASHTAGS ---\n")
            f.write(" ".join(seo_data.get("hashtags", [])))
            f.write("\n\n")
            f.write("--- PROMPT THUMBNAIL VE ANH ---\n")
            f.write(seo_data.get("thumbnail_prompt", ""))
            f.write("\n")
            
        print(f"[✓] Da tao va luu SEO Metadata tai: {seo_txt_path}")
        
    # Bước 4: Sinh ảnh tự động (và sinh Thumbnail nếu có)
    success = generate_images_workflow(segments, thumbnail_prompt=thumbnail_prompt)
    if not success:
        print("[ERROR] Sinh anh tự dong that bai. Vui long kiem tra lai trinh duyet Chrome Debug.")
        return
        
    # Nếu bỏ qua vẽ ảnh (do dùng file script có sẵn timestamp) hoặc sinh ảnh thumbnail thất bại
    # Ta copy ảnh đầu tiên làm ảnh thumbnail fallback
    thumbnail_path = os.path.join(OUTPUT_DIR, "thumbnail.png")
    if not os.path.exists(thumbnail_path):
        first_img = os.path.join(TEMP_DIR, "image_0.png")
        if os.path.exists(first_img):
            import shutil
            shutil.copy(first_img, thumbnail_path)
            print(f"[✓] Da copy anh dau tien lam thumbnail fallback tai: {thumbnail_path}")
            
    # Bước 5: Ghép nối & render video
    timestamp_suffix = int(time.time())
    final_output = os.path.join(OUTPUT_DIR, f"doodle_video_{timestamp_suffix}.mp4")
    srt_output = os.path.join(OUTPUT_DIR, f"doodle_video_{timestamp_suffix}.srt")
    
    # Tạo file phụ đề SRT
    generate_srt_file(segments, srt_output)
    
    # Render video
    success = assemble_final_video(segments, audio_path, final_output)
    if success:
        print(f"[✓] Render video hoan tat tai: {final_output}")
    else:
        print("[ERROR] Loi render video cuoi cung.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Prompt nhập chủ đề nếu chạy trực tiếp
        print("Nhap chu de video: ", end="")
        input_topic = input()
        if input_topic.strip():
            run_pipeline(input_topic.strip())
    else:
        topic_arg = " ".join(sys.argv[1:])
        run_pipeline(topic_arg)
