@echo off
title Khoi dong Chrome Debugging Mode
echo Dang kiem tra vi tri cai dat Chrome...

set CHROME_PATH=""
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH="%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

if %CHROME_PATH% == "" (
    echo Khong tim thay Google Chrome tren cac thu muc mac dinh.
    echo Vui long mo Chrome bang tay voi cac tham so sau:
    echo chrome.exe --remote-debugging-port=9222 --user-data-dir="%~dp0.chrome_profile"
    pause
    exit /b
)

echo Tim thay Chrome tai: %CHROME_PATH%
echo Dang khoi dong Chrome voi Remote Debugging Port 9222...
echo Du lieu profile se duoc luu tai: "%~dp0.chrome_profile"
start "" %CHROME_PATH% --remote-debugging-port=9222 --user-data-dir="%~dp0.chrome_profile"

echo Da mo Chrome.
echo Vui long truy cap: https://labs.google/fx/tools/flow
echo Dang nhap tai khoan Google Labs cua ban va chuan bi chay tool Python.
pause
