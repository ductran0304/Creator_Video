@echo off
:: Chay make_video.py voi moi truong ao .venv (tu tao lan dau).
:: Vi du:  make_video.bat validate ten_du_an
::         make_video.bat build ten_du_an --draft
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo [i] Chua co .venv - dang tao va cai thu vien...
    python -m venv .venv || goto :fail
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
)
.venv\Scripts\python.exe make_video.py %*
exit /b %errorlevel%

:fail
echo [LOI] Khong tao duoc moi truong. Kiem tra Python 3.10+ da cai va co trong PATH.
exit /b 1
