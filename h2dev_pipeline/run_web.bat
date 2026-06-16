@echo off
cd /d "%~dp0"
echo ===================================================
echo   H2Dev Pipeline - Web UI Startup
echo ===================================================

:: Kiem tra moi truong ảo
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [i] Khong tim thay moi truong ao .venv. Dang tu dong cai dat...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [i] Dang cai dat dependencies (mat khoang 1-2 phut)...
    pip install -r requirements.txt
    echo [✓] Cai dat xong!
)

:: Chay Flask server
echo [i] Dang khoi dong Web UI server...
start http://localhost:5000
python web_ui.py

pause
