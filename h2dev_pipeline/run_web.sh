#!/usr/bin/env bash
# H2Dev Pipeline - Web UI Startup (MacOS / Linux)

cd "$(dirname "$0")"

echo "==================================================="
echo "  H2Dev Pipeline - Web UI Startup (MacOS/Linux)"
echo "==================================================="

# Check for virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "[i] Virtual environment not found. Setting it up automatically..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "[i] Installing dependencies..."
    pip install -r requirements.txt
    echo "[OK] Setup complete!"
fi

echo "[i] Starting Web UI server..."
# Try to open the browser automatically
if command -v open > /dev/null; then
    open http://localhost:5000
elif command -v xdg-open > /dev/null; then
    xdg-open http://localhost:5000
fi

python3 web_ui.py
