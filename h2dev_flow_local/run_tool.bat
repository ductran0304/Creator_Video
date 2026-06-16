@echo off
title Khoi chay H2Dev Flow Local Tool
cd /d "%~dp0"

if not exist .venv (
    echo [H2DEV] Khong tim thay moi truong ao .venv. Dang khoi tao...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Khong the tao moi truong ao. Vui long kiem tra xem Python da duoc cai dat va them vao PATH chua.
        pause
        exit /b
    )
    echo [H2DEV] Dang kich hoat moi truong ao...
    call .venv\Scripts\activate.bat
    echo [H2DEV] Dang nang cap pip...
    python -m pip install --upgrade pip
    echo [H2DEV] Dang cai dat cac thu vien can thiet...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Cai dat thu vien that bai.
        pause
        exit /b
    )
    echo [H2DEV] Khoi tao thanh cong!
) else (
    echo [H2DEV] Kich hoat moi truong ao...
    call .venv\Scripts\activate.bat
)

echo [H2DEV] Dang chay main.py...
python main.py
pause
