@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 数据根目录：优先用已设好的 FW_ROOT；否则默认 D:\ResearchData，
REM 若本机没有 D 盘则退回到 %USERPROFILE%\ResearchData。
if not defined FW_ROOT (
  if exist D:\ (
    set "FW_ROOT=D:\ResearchData"
  ) else (
    set "FW_ROOT=%USERPROFILE%\ResearchData"
  )
)

if not exist .venv (
  echo [首次运行] 创建虚拟环境...
  python -m venv .venv || py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt

echo [数据目录] %FW_ROOT%
echo [访问地址] http://127.0.0.1:8000
python -m uvicorn fw_server:app --host 127.0.0.1 --port 8000
pause
