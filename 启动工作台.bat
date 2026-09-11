@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist .venv (
  echo [首次运行] 创建虚拟环境...
  python -m venv .venv || py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
python -m uvicorn fw_server:app --host 127.0.0.1 --port 8000
pause
