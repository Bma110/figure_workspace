"""文件夹名清洗 + 文件名样本提示解析。"""
import re

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WS = re.compile(r"\s+")
# 样本码段：含字母与数字、总长 >=4、仅字母/数字/连字符（- 为码内连字符）。
# 解析为尽力而为：day7、rep1 等短"字母+数字"token 也可能命中；实践中优先真实连字符样本码。
_SAMPLE = re.compile(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9-]{4,}", re.I)
_PURE_CODE = re.compile(r"\b(?:EXP|P)\d{2,4}\b", re.I)
_WORD = re.compile(r"[_\s]+")


def folder_slug(label: str) -> str:
    """把展示名转为 Windows 合法文件夹名：去空白、非法字符。保留中文。"""
    s = _INVALID.sub("", label or "")
    s = _WS.sub("", s)
    s = s.strip().rstrip(".")
    return s or "untitled"


def unique_name(name: str, existing: list[str]) -> str:
    """若 name 已存在于 existing，追加 ' (n)' 直到不冲突。"""
    if name not in existing:
        return name
    stem = name.rsplit(".", 1)[0] if "." in name else name
    ext = "." + name.rsplit(".", 1)[1] if "." in name else ""
    i = 2
    while f"{stem} ({i}){ext}" in existing:
        i += 1
    return f"{stem} ({i}){ext}"


def parse_sample_hint(filename: str) -> str:
    """尽力从文件名提样本码（如 SA-MLOY4-001），没有则返回空；纯实验编号(EXP/P+数字)跳过。"""
    if not filename:
        return ""
    stem = filename.rsplit(".", 1)[0]
    for token in _WORD.split(stem):
        if _PURE_CODE.search(token):
            continue  # 避开纯实验/项目编号（EXP024 / P1234 等）
        if _SAMPLE.fullmatch(token):
            return token
    return ""
