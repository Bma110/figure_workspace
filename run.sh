#!/usr/bin/env bash
# macOS / Linux 启动脚本。Windows 用 启动工作台.bat。
set -e
cd "$(dirname "$0")"

# 数据根目录：优先用已设好的 FW_ROOT；否则默认 ~/ResearchData。
export FW_ROOT="${FW_ROOT:-$HOME/ResearchData}"

if [ ! -d .venv ]; then
  echo "[首次运行] 创建虚拟环境..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -r requirements.txt

echo "[数据目录] $FW_ROOT"
echo "[访问地址] http://127.0.0.1:8000"
python -m uvicorn fw_server:app --host 127.0.0.1 --port 8000
