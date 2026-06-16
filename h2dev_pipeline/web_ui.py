"""
H2Dev Pipeline — Web UI Server
Flask backend với SSE (Server-Sent Events) để stream pipeline output realtime.
"""
import os
import sys
import json
import time
import queue
import threading
import glob
import logging
from flask import Flask, render_template, request, jsonify, Response, send_from_directory

# Disable Werkzeug logging to prevent HTTP requests from flooding the console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- Đường dẫn tuyệt đối tới thư mục pipeline ---
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PIPELINE_DIR, "config.json")
PROJECTS_DIR = os.path.join(PIPELINE_DIR, "projects")

app = Flask(__name__,
            template_folder=os.path.join(PIPELINE_DIR, "templates"),
            static_folder=os.path.join(PIPELINE_DIR, "static"))

# --- State Management ---
log_queue = queue.Queue()
pipeline_state = {
    "status": "idle",       # idle | running | completed | error
    "stage": 0,             # 0-6
    "stage_name": "",
    "project_name": "",
    "topic": "",
    "started_at": None,
    "completed_at": None,
    "error": ""
}
pipeline_thread = None

STAGES = [
    {"id": 1, "name": "Script Generation",       "icon": "✍️",  "key": "script"},
    {"id": 2, "name": "Voiceover & Timestamps",   "icon": "🎙️", "key": "voiceover"},
    {"id": 3, "name": "SEO Metadata",              "icon": "📊",  "key": "seo"},
    {"id": 4, "name": "Image Generation",          "icon": "🎨",  "key": "images"},
    {"id": 5, "name": "Audio Mixing",              "icon": "🎵",  "key": "audio"},
    {"id": 6, "name": "Video Render",              "icon": "🎬",  "key": "render"},
]

# Patterns phát hiện stage từ output text
STAGE_PATTERNS = [
    (1, ["sinh kịch bản", "script_generator", "Gọi API qua", "phân tích kịch bản"]),
    (2, ["tao giong doc", "generate_voiceover", "Phân canh", "segment_"]),
    (3, ["tạo tiêu đề", "SEO", "seo_generator", "youtube_metadata"]),
    (4, ["kết nối Chrome", "tao anh", "Google Flow", "Dang tao anh"]),
    (5, ["nhạc nền", "hiệu ứng âm thanh", "BGM", "SFX", "Đang lồng", "Đang chèn"]),
    (6, ["render video", "Dang render", "write_videofile"]),
]


# --- Stdout Capture ---
class OutputCapture:
    """Bắt stdout và gửi vào queue để stream qua SSE."""
    def __init__(self, original_stdout):
        self.original = original_stdout
        self.encoding = getattr(original_stdout, 'encoding', 'utf-8')

    def write(self, text):
        if isinstance(text, bytes):
            try:
                text = text.decode(self.encoding or 'utf-8', errors='replace')
            except Exception:
                text = str(text)
                
        if text and text.strip():
            try:
                self.original.write(text)
            except Exception:
                pass
            log_queue.put(text.strip())
            self._detect_stage(text)

    def flush(self):
        try:
            self.original.flush()
        except Exception:
            pass

    def reconfigure(self, **kwargs):
        """Bỏ qua reconfigure từ pipeline.py để tránh ghi đè capture."""
        pass

    def _detect_stage(self, text):
        text_lower = text.lower()
        for stage_num, patterns in STAGE_PATTERNS:
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    if pipeline_state["stage"] < stage_num:
                        pipeline_state["stage"] = stage_num
                        pipeline_state["stage_name"] = STAGES[stage_num - 1]["name"]
                    break

        if "render video hoan tat" in text_lower or "render video hoàn tất" in text_lower:
            pipeline_state["status"] = "completed"
            pipeline_state["completed_at"] = time.time()
        elif "[error]" in text_lower and pipeline_state["status"] == "running":
            pipeline_state["error"] = text.strip()


# --- Pipeline Thread ---
def run_pipeline_thread(topic):
    """Chạy pipeline trong background thread."""
    global pipeline_state
    try:
        pipeline_state["status"] = "running"
        pipeline_state["stage"] = 0
        pipeline_state["stage_name"] = "Initializing..."
        pipeline_state["started_at"] = time.time()
        pipeline_state["completed_at"] = None
        pipeline_state["error"] = ""
        pipeline_state["topic"] = topic

        # Import pipeline (phải import SAU khi đã capture stdout)
        sys.path.insert(0, PIPELINE_DIR)
        import pipeline as pl

        # Reload config
        pl.config = pl.load_config()
        pl.LANGUAGE = pl.config.get("language", "en")
        pl.VOICE_NAME = pl.config.get("voice_name", "en-US-EmmaNeural")
        pl.USE_WEB2API = pl.config.get("use_web2api", True)
        pl.WEB2API_URL = pl.config.get("web2api_url", "http://localhost:8081/v1")
        pl.WEB2API_KEY = pl.config.get("web2api_key", "sk-gemini")
        pl.WEB2API_MODEL_SCRIPT = pl.config.get("web2api_model_script", "gemini-3.1-pro")
        pl.WEB2API_MODEL_SEO = pl.config.get("web2api_model_seo", "gemini-3.5-flash-thinking")
        pl.KB = pl.load_knowledge_base()

        # Chạy pipeline
        pl.run_pipeline(topic)

        if pipeline_state["status"] == "running":
            pipeline_state["status"] = "completed"
            pipeline_state["completed_at"] = time.time()

    except Exception as e:
        pipeline_state["status"] = "error"
        pipeline_state["error"] = str(e)
        log_queue.put(f"[FATAL ERROR] {e}")


# --- Helpers ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_projects():
    """Quét thư mục projects/ và trả về danh sách dự án."""
    projects = []
    if not os.path.exists(PROJECTS_DIR):
        return projects

    for name in sorted(os.listdir(PROJECTS_DIR), reverse=True):
        project_path = os.path.join(PROJECTS_DIR, name)
        if not os.path.isdir(project_path):
            continue

        outputs_dir = os.path.join(project_path, "outputs")
        info = {
            "name": name,
            "display_name": name.replace("_", " ").title(),
            "path": project_path,
            "has_video": False,
            "has_thumbnail": False,
            "has_seo": False,
            "video_file": None,
            "thumbnail_url": None,
            "seo_data": None,
            "created_at": None
        }

        if os.path.exists(outputs_dir):
            # Tìm video
            videos = glob.glob(os.path.join(outputs_dir, "doodle_video_*.mp4"))
            if videos:
                latest_video = max(videos, key=os.path.getmtime)
                info["has_video"] = True
                info["video_file"] = os.path.basename(latest_video)
                info["created_at"] = os.path.getmtime(latest_video)

            # Thumbnail
            thumb = os.path.join(outputs_dir, "thumbnail.png")
            if os.path.exists(thumb):
                info["has_thumbnail"] = True
                info["thumbnail_url"] = f"/media/{name}/outputs/thumbnail.png"

            # SEO metadata
            seo_path = os.path.join(outputs_dir, "youtube_metadata.json")
            if os.path.exists(seo_path):
                try:
                    with open(seo_path, "r", encoding="utf-8") as f:
                        info["seo_data"] = json.load(f)
                    info["has_seo"] = True
                except Exception:
                    pass

        if info["created_at"] is None:
            info["created_at"] = os.path.getmtime(project_path)

        projects.append(info)

    # Sắp xếp theo ngày tạo (mới nhất trước)
    projects.sort(key=lambda p: p["created_at"] or 0, reverse=True)
    return projects


# ========================================
#  ROUTES
# ========================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/pipeline/start", methods=["POST"])
def start_pipeline():
    global pipeline_thread
    if pipeline_state["status"] == "running":
        return jsonify({"error": "Pipeline đang chạy. Vui lòng đợi hoàn thành."}), 409

    data = request.json or {}
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Vui lòng nhập chủ đề video."}), 400

    # Cập nhật language nếu có
    lang = data.get("language")
    if lang:
        cfg = load_config()
        cfg["language"] = lang
        save_config(cfg)

    # Reset state
    pipeline_state["project_name"] = ""

    # Chạy pipeline trong thread riêng
    pipeline_thread = threading.Thread(target=run_pipeline_thread, args=(topic,), daemon=True)
    pipeline_thread.start()

    return jsonify({"status": "started", "topic": topic})


@app.route("/api/pipeline/status")
def get_status():
    elapsed = None
    if pipeline_state["started_at"]:
        end = pipeline_state["completed_at"] or time.time()
        elapsed = round(end - pipeline_state["started_at"], 1)

    return jsonify({
        **pipeline_state,
        "stages": STAGES,
        "elapsed_seconds": elapsed
    })


@app.route("/api/pipeline/stream")
def stream():
    """SSE endpoint — stream log output realtime."""
    def generate():
        while True:
            try:
                msg = log_queue.get(timeout=2)
                data = json.dumps({"type": "log", "message": msg, "stage": pipeline_state["stage"], "status": pipeline_state["status"]})
                yield f"data: {data}\n\n"
            except queue.Empty:
                # Heartbeat giữ kết nối sống
                data = json.dumps({"type": "heartbeat", "stage": pipeline_state["stage"], "status": pipeline_state["status"]})
                yield f"data: {data}\n\n"

            # Dừng stream nếu pipeline hoàn thành hoặc lỗi
            if pipeline_state["status"] in ("completed", "error", "idle"):
                # Flush remaining messages
                while not log_queue.empty():
                    try:
                        msg = log_queue.get_nowait()
                        data = json.dumps({"type": "log", "message": msg, "stage": pipeline_state["stage"], "status": pipeline_state["status"]})
                        yield f"data: {data}\n\n"
                    except queue.Empty:
                        break
                # Gửi event kết thúc
                data = json.dumps({"type": "done", "status": pipeline_state["status"], "stage": pipeline_state["stage"]})
                yield f"data: {data}\n\n"
                break

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/projects")
def list_projects():
    return jsonify(get_projects())


@app.route("/api/projects/<name>")
def get_project(name):
    projects = get_projects()
    for p in projects:
        if p["name"] == name:
            return jsonify(p)
    return jsonify({"error": "Project not found"}), 404


@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(load_config())


@app.route("/api/config", methods=["POST"])
def update_config():
    try:
        new_config = request.json
        save_config(new_config)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/media/<path:filepath>")
def serve_media(filepath):
    """Phục vụ file media từ thư mục projects/."""
    return send_from_directory(PROJECTS_DIR, filepath)


# ========================================
#  ENTRY POINT
# ========================================
if __name__ == "__main__":
    # Capture stdout TRƯỚC khi import pipeline
    original_stdout = sys.stdout
    sys.stdout = OutputCapture(original_stdout)
    sys.stderr = OutputCapture(sys.stderr)

    print("[H2DEV] Web UI Server đang khởi động...")
    print(f"[H2DEV] Pipeline dir: {PIPELINE_DIR}")
    print(f"[H2DEV] Mở trình duyệt tại: http://localhost:5000")

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
