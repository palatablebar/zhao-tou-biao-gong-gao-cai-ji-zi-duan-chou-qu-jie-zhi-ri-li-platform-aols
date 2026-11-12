"""文本工具：清洗、锚点定位、数值/日期辅助。"""
from __future__ import annotations

import re

SPACE_RE = re.compile(r"[\s\u3000]+")
SEPARATOR_CHARS = " \u3000:：=＝\t-—"


def clean_text(value: str | None) -> str:
    """正文清洗：统一空白、去掉多余空行，不改变锚点词与数字。"""
    if not value:
        return ""
    text = value.replace("\u3000", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def collapse_spaces(value: str | None) -> str:
    return SPACE_RE.sub(" ", (value or "")).strip()


def find_all(haystack: str, needle: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            return positions
        positions.append(idx)
        start = idx + len(needle)


def strip_separators(value: str) -> tuple[str, int]:
    """去掉值前面的分隔符，返回 (剩余文本, 被去掉的字符数)。"""
    index = 0
    while index < len(value) and value[index] in SEPARATOR_CHARS:
        index += 1
    return value[index:], index


def first_line(value: str, limit: int = 80) -> str:
    for line in value.split("\n"):
        if line.strip():
            return line.strip()[:limit]
    return ""


def comma_number(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def to_float(number: str | None) -> float | None:
    if not number:
        return None
    try:
        return float(number.replace(",", ""))
    except ValueError:
        return None
