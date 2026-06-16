@echo off
cd /d "%~dp0"
echo ===================================================
echo   H2Dev Pipeline - Web UI Startup
echo ===================================================

:: Kiem tra moi truong ảo
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [!] Khong tim thay moi truong ao .venv.
    echo Vui long cai dat dependencies truoc khi chay.
    pause
    exit /b
)

:: Chay Flask server
echo [i] Dang khoi dong Web UI server...
start http://localhost:5000
python web_ui.py

pause
