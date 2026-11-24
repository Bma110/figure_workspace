@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal

REM 1) Find a Python with venv support: system python/py.
set "py="
where python >nul 2>nul && set "py=python"
if defined py goto have_python
where py >nul 2>nul && set "py=py"

:have_python
if not defined py goto no_python

REM 2) Data root: prefer set FW_ROOT; else D:\ResearchData if D exists, else USERPROFILE.
if not defined FW_ROOT (
  if exist D:\ set "FW_ROOT=D:\ResearchData"
)
if not defined FW_ROOT set "FW_ROOT=%USERPROFILE%\ResearchData"

REM 3) Show a small banner if present.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\print_startup_banner.ps1" -Banner

REM 4) Modern splash if modern terminal is available.
call :show_modern_splash

REM 5) Set up venv and install deps (only if needed).
if not exist .venv (
  echo [首次运行] 创建虚拟环境...
  %py% -m venv .venv >nul 2>nul || (%py% -m venv .venv & echo [警告] venv 创建较慢或失败，建议看看报错)
)
call .venv\Scripts\activate.bat >nul 2>nul
echo [首次运行] 安装依赖(如已安装这里会很快跳过)...
pip install -q -r requirements.txt >nul 2>nul
if not exist .venv\Scripts\python.exe set "py=.venv\Scripts\python.exe"

REM 6) Start banner + print info.
echo [数据目录] %FW_ROOT%
echo [访问地址] http://127.0.0.1:8000  (Ctrl+C 退出)
echo:
python -m uvicorn fw_server:app --host 127.0.0.1 --port 8000
goto :eof

:show_modern_splash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\show_modern_splash.ps1" -Title "Figure 工作台启动" -Caption "Fig workspaces — research figures" >nul 2>nul
goto :eof

:no_python
echo [错误] 未找到 Python 或 py，请先在 https://www.python.org 安装 Python >= 3.10 并加入 PATH。
pause
goto :eof
