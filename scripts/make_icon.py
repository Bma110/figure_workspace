"""从 static/icon.png 生成多尺寸 static/icon.ico（快捷方式 / 任务栏图标用）。"""
from pathlib import Path

from PIL import Image

root = Path(__file__).resolve().parent.parent
src = root / "static" / "icon.png"
dst = root / "static" / "icon.ico"
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

Image.open(src).convert("RGBA").save(dst, sizes=sizes)
print(f"wrote {dst} ({dst.stat().st_size} bytes)")
