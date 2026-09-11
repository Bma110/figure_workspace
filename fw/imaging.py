"""图片格式归一：把浏览器渲染不了的格式（tif/tiff 等）转成 PNG 字节。"""
import io

from PIL import Image

# 浏览器 <img> 能直接解码的扩展名（含 BMP）。
RENDERABLE = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def needs_conversion(ext: str) -> bool:
    return ext.lower() not in RENDERABLE


def to_png(data: bytes) -> bytes:
    """任意 Pillow 可读的图片 → PNG 字节。多页取首页；16-bit 等非常规模式转 RGB。"""
    im = Image.open(io.BytesIO(data))
    if im.mode not in ("RGB", "RGBA", "L"):
        im = im.convert("RGB")
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()
