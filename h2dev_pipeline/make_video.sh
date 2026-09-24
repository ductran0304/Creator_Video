#!/usr/bin/env bash
# Chạy make_video.py với môi trường ảo .venv (tự tạo lần đầu). macOS / Linux.
# Ví dụ:  ./make_video.sh validate ten_du_an
#         ./make_video.sh build ten_du_an --draft
set -e
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
    echo "[i] Chưa có .venv — đang tạo và cài thư viện..."
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python make_video.py "$@"
