"""算法 1：字段抽取与置信度（重规则 + 上下文锚点，同输入同分数）。

置信度 = 0.35 × 锚点距离分 + 0.35 × 格式匹配分 + 0.30 × 单位/日期明确性分
- 锚点距离分：`1 - dist / 80`（dist = 锚点词结束到字段值起点的字符数，下限 0）
- 格式匹配分：金额看「数字 + 单位」结构，日期看绝对/相对/占位三档，地点看地址要素
- 明确性分：金额看单位与「约/暂定/不超过」修饰，日期看绝对/相对，地点看待定话术
置信度 < 0.55 进复核队列；同一条正文重复抽取结果逐字段一致。
"""
from __future__ import annotations

import re
from datetime import datetime

from src.config.settings import settings
from src.constants.enums import FieldKey
from src.constants.fieldspec import (
    ANCHOR_MAX_DISTANCE,
    BIDDER_QUALIFICATION,
    CONFIDENCE_WEIGHTS,
    FIELD_SPEC,
    PLACEHOLDER_WORDS,
    UNIT_TO_YUAN,
)
from src.utils.textutil import clean_text, collapse_spaces, find_all, first_line, strip_separators, to_float
from src.utils.workcalendar import add_workdays

WINDOW = 88

BUDGET_RE = re.compile(
    r"(?P<mod>约|暂定|估算|不超过|最高不超过)?\s*(?P<cur>人民币|￥|¥)?\s*"
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>亿元|万元|元)"
)
NUMBER_RE = re.compile(r"(?P<num>\d[\d,]*(?:\.\d+)?)")
FULL_DATE_RE = re.compile(
    r"(?P<y>20\d{2})\s*[年\-/.]\s*(?P<m>\d{1,2})\s*[月\-/.]\s*(?P<d>\d{1,2})\s*日?"
    r"\s*(?:(?P<ampm>上午|下午|晚上|中午)?\s*(?P<hh>\d{1,2})\s*[:：点时]\s*(?P<mm>\d{1,2}|半)?\s*分?)?"
)
PARTIAL_DATE_RE = re.compile(
    r"(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日"
    r"\s*(?:(?P<ampm>上午|下午|晚上|中午)?\s*(?P<hh>\d{1,2})\s*[:：点时]\s*(?P<mm>\d{1,2}|半)?\s*分?)?"
)
RELATIVE_DATE_RE = re.compile(r"(?:报名截止后|投标截止后|递交截止后|后)\s*(?P<n>\d{1,2})\s*个工作日")
ADDRESS_HINTS = ("省", "市", "区", "县", "路", "街", "号", "楼", "中心", "大厦", "会议室", "室")


def confidence_of(anchor: float, fmt: float, clarity: float) -> float:
    weights = CONFIDENCE_WEIGHTS
    value = (
        anchor * weights["anchor"]
        + fmt * weights["format"]
        + clarity * weights["clarity"]
    )
    return round(value, 3)


def anchor_score(distance: int) -> float:
    distance = max(distance, 0)
    return round(max(0.0, 1.0 - distance / ANCHOR_MAX_DISTANCE), 3)


def _missing(field_key: str, anchors: list[str]) -> dict:
    label = FIELD_SPEC[field_key]["label"]
    return {
        "field_key": field_key,
        "label": label,
        "value_text": None,
        "raw_text": None,
        "unit": None,
        "amount_yuan": None,
        "event_at": None,
        "precision": "missing",
        "is_estimated": False,
        "anchor_score": 0.0,
        "format_score": 0.0,
        "clarity_score": 0.0,
        "confidence": 0.0,
        "reason": f"未命中锚点（{'/'.join(anchors[:3])}），正文中未出现该字段标题",
        "missing": True,
    }


def _result(
    field_key: str,
    *,
    anchor: str,
    distance: int,
    fmt: float,
    clarity: float,
    raw: str,
    value_text: str | None,
    reason_parts: list[str],
    unit: str | None = None,
    amount_yuan: float | None = None,
    event_at: datetime | None = None,
    precision: str = "missing",
    is_estimated: bool = False,
) -> dict:
    a_score = anchor_score(distance)
    conf = confidence_of(a_score, fmt, clarity)
    reason = f"锚点『{anchor}』距离 {distance} 字；" + "；".join(reason_parts)
    return {
        "field_key": field_key,
        "label": FIELD_SPEC[field_key]["label"],
        "value_text": value_text,
        "raw_text": collapse_spaces(raw),
        "unit": unit,
        "amount_yuan": amount_yuan,
        "event_at": event_at,
        "precision": precision,
        "is_estimated": is_estimated,
        "anchor_score": a_score,
        "format_score": round(fmt, 3),
        "clarity_score": round(clarity, 3),
        "confidence": conf,
        "reason": reason,
        "missing": value_text is None,
    }


def _field_line(tail: str) -> tuple[str, int]:
    """取锚点后的「同一行」窗口：字段值不应跨行漂到下面的开标时间等字段。"""
    body, lead = strip_separators(tail)
    first = body.split("\n")[0][:72]
    return first, lead


def _find_placeholder(body: str) -> str | None:
    head = body[:26]
    for word in PLACEHOLDER_WORDS:
        idx = head.find(word)
        if idx >= 0:
            return head[idx: idx + min(len(word) + 6, 14)]
    return None


def _apply_ampm(hour: int, ampm: str | None) -> int:
    if ampm in ("下午", "晚上") and hour < 12:
        return hour + 12
    if ampm == "中午" and hour < 11:
        return hour + 12
    return hour


def _parse_date_match(match: re.Match, published_at: datetime) -> tuple[datetime | None, str, bool]:
    """返回 (事件时刻, precision, 是否相对估计)。"""
    groups = match.groupdict()
    if "n" in groups and groups.get("n"):
        days = int(groups["n"])
        return add_workdays(published_at, days, 17), "relative", True
    year = groups.get("y")
    month = groups.get("m")
    day = groups.get("d")
    if not month or not day:
        return None, "missing", False
    year_value = int(year) if year else published_at.year
    hh_raw = groups.get("hh")
    hour = 17
    minute = 0
    if hh_raw:
        hour = _apply_ampm(int(hh_raw), groups.get("ampm"))
        mm_raw = groups.get("mm")
        minute = 30 if mm_raw == "半" else int(mm_raw or 0)
    try:
        event_at = datetime(year_value, int(month), int(day), hour, minute)
    except ValueError:
        return None, "missing", False
    precision = "absolute" if year else "partial"
    return event_at, precision, False


def _extract_budget(text: str, anchors: list[str]) -> dict:
    field_key = FieldKey.BUDGET_AMOUNT.value
    best: dict | None = None
    for anchor in anchors:
        for idx in find_all(text, anchor):
            tail = text[idx + len(anchor): idx + len(anchor) + WINDOW]
            body, lead = _field_line(tail)
            if not body:
                continue
            match = BUDGET_RE.search(body)
            if match:
                number = to_float(match.group("num"))
                unit = match.group("unit")
                if number is None:
                    continue
                modifier = (match.group("mod") or "").strip()
                amount_yuan = round(number * UNIT_TO_YUAN[unit], 2)
                raw = collapse_spaces(body[match.start(): match.end()])
                value_text = raw
                if modifier in ("约", "暂定", "估算"):
                    clarity = 0.55
                    clarity_note = f"含「{modifier}」估算标记，按估算值处理"
                elif modifier in ("不超过", "最高不超过"):
                    clarity = 0.70
                    clarity_note = f"含「{modifier}」上限标记"
                else:
                    clarity = 1.0
                    clarity_note = f"单位明确（{unit}）"
                tax_window = body[match.end(): match.end() + 20]
                tax_note = "不含税" if "不含税" in tax_window else ("含税" if "含税" in tax_window else "")
                reason_parts = ["金额格式完整（数字+单位）", clarity_note]
                if tax_note:
                    reason_parts.append(tax_note)
                candidate = _result(
                    field_key,
                    anchor=anchor,
                    distance=lead + match.start(),
                    fmt=1.0,
                    clarity=clarity,
                    raw=raw,
                    value_text=value_text,
                    reason_parts=reason_parts,
                    unit=unit,
                    amount_yuan=amount_yuan,
                    precision="absolute",
                )
            else:
                number_only = NUMBER_RE.search(body[:36])
                if number_only and "保证金" not in body[: number_only.start()]:
                    number = to_float(number_only.group("num"))
                    raw = number_only.group(0)
                    candidate = _result(
                        field_key,
                        anchor=anchor,
                        distance=lead + number_only.start(),
                        fmt=0.55,
                        clarity=0.30,
                        raw=raw,
                        value_text=raw,
                        reason_parts=["只有数字没有金额单位（疑似元）", "单位缺失"],
                        unit="元",
                        amount_yuan=number,
                        precision="partial",
                    )
                else:
                    placeholder = _find_placeholder(body)
                    if not placeholder:
                        continue
                    candidate = _result(
                        field_key,
                        anchor=anchor,
                        distance=lead,
                        fmt=0.2,
                        clarity=0.0,
                        raw=placeholder,
                        value_text=None,
                        reason_parts=["正文为「面议/详见」类占位话术", "无可归一金额"],
                        precision="missing",
                    )
            if best is None or candidate["confidence"] > best["confidence"]:
                best = candidate
    return best or _missing(field_key, anchors)


def _extract_deadline(text: str, anchors: list[str], published_at: datetime) -> dict:
    field_key = FieldKey.DEADLINE.value
    best: dict | None = None
    for anchor in anchors:
        for idx in find_all(text, anchor):
            tail = text[idx + len(anchor): idx + len(anchor) + WINDOW]
            body, lead = _field_line(tail)
            if not body:
                continue
            window = body
            candidate: dict | None = None
            full = FULL_DATE_RE.search(window)
            partial = PARTIAL_DATE_RE.search(window)
            relative = RELATIVE_DATE_RE.search(window)
            if full:
                event_at, precision, estimated = _parse_date_match(full, published_at)
                match = full
            elif partial:
                event_at, precision, estimated = _parse_date_match(partial, published_at)
                match = partial
            elif relative:
                event_at, precision, estimated = _parse_date_match(relative, published_at)
                match = relative
            else:
                event_at, precision, estimated, match = None, "missing", False, None
            if match is not None and event_at is not None:
                has_time = bool(match.groupdict().get("hh"))
                if precision == "relative":
                    fmt, clarity = 0.45, 0.40
                    format_note = "相对日期（报名截止后 N 个工作日）"
                    clarity_note = "按公告日 + N 个工作日推算，属区间估计"
                    value_text = f"{event_at.strftime('%Y-%m-%d %H:%M')}（推算）"
                elif precision == "partial":
                    fmt, clarity = (0.75 if has_time else 0.70), 0.70
                    format_note = "日期缺年份，按公告年份补全"
                    clarity_note = "年份由上下文推断"
                    value_text = event_at.strftime("%Y-%m-%d %H:%M") if has_time else event_at.strftime("%Y-%m-%d")
                else:
                    fmt, clarity = (1.0 if has_time else 0.85), (1.0 if has_time else 0.80)
                    format_note = "绝对日期" + ("+时刻" if has_time else "（缺时刻，默认 17:00）")
                    clarity_note = "日期口径明确" if has_time else "时刻缺失，按当日 17:00 归位"
                    value_text = event_at.strftime("%Y-%m-%d %H:%M") if has_time else event_at.strftime("%Y-%m-%d")
                candidate = _result(
                    field_key,
                    anchor=anchor,
                    distance=lead + match.start(),
                    fmt=fmt,
                    clarity=clarity,
                    raw=match.group(0),
                    value_text=value_text,
                    reason_parts=[format_note, clarity_note],
                    event_at=event_at,
                    precision=precision,
                    is_estimated=estimated,
                )
            else:
                placeholder = _find_placeholder(body)
                if not placeholder:
                    continue
                candidate = _result(
                    field_key,
                    anchor=anchor,
                    distance=lead,
                    fmt=0.2,
                    clarity=0.0,
                    raw=placeholder,
                    value_text=None,
                    reason_parts=["正文为「另行通知/见公告」类占位话术", "无可归一日期"],
                    precision="missing",
                )
            if best is None or candidate["confidence"] > best["confidence"]:
                best = candidate
    return best or _missing(field_key, anchors)


def _extract_opening(text: str, anchors: list[str]) -> dict:
    field_key = FieldKey.OPENING_PLACE.value
    best: dict | None = None
    for anchor in anchors:
        for idx in find_all(text, anchor):
            tail = text[idx + len(anchor): idx + len(anchor) + WINDOW]
            body, lead = strip_separators(tail)
            if not body:
                continue
            placeholder = _find_placeholder(body[:20])
            if placeholder:
                candidate = _result(
                    field_key,
                    anchor=anchor,
                    distance=lead,
                    fmt=0.2,
                    clarity=0.0,
                    raw=placeholder,
                    value_text=None,
                    reason_parts=["正文为「另行通知」类占位话术", "无具体地址"],
                )
            else:
                line = first_line(body, 60).split("｜")[0].strip("。；;|")
                if not line:
                    continue
                hints = sum(1 for hint in ADDRESS_HINTS if hint in line)
                long_enough = len(line) >= 8
                if long_enough and hints >= 2:
                    fmt, clarity = 1.0, 1.0
                    format_note = "地址要素完整（市/区/路/楼）"
                    clarity_note = "地点明确"
                elif long_enough:
                    fmt, clarity = 0.80, 0.75
                    format_note = "有具体地点但地址要素不全"
                    clarity_note = "地点可读"
                else:
                    fmt, clarity = 0.40, 0.50
                    format_note = "地点过短"
                    clarity_note = "地点不完整"
                candidate = _result(
                    field_key,
                    anchor=anchor,
                    distance=lead,
                    fmt=fmt,
                    clarity=clarity,
                    raw=line,
                    value_text=line,
                    reason_parts=[format_note, clarity_note],
                    precision="absolute",
                )
            if best is None or candidate["confidence"] > best["confidence"]:
                best = candidate
    return best or _missing(field_key, anchors)


def _extract_project_name(text: str, anchors: list[str]) -> dict:
    field_key = FieldKey.PROJECT_NAME.value
    best: dict | None = None
    for anchor in anchors:
        for idx in find_all(text, anchor):
            tail = text[idx + len(anchor): idx + len(anchor) + WINDOW]
            body, lead = strip_separators(tail)
            line = first_line(body, 60).split("｜")[0].strip("。；;|")
            if not line:
                continue
            placeholder = _find_placeholder(line)
            if placeholder:
                fmt, clarity = 0.4, 0.5
                reason_parts = ["项目名称为占位内容", "需人工补全"]
            elif len(line) >= 8 and any(word in line for word in ("项目", "工程", "采购", "施工", "建设")):
                fmt, clarity = 1.0, 1.0
                reason_parts = ["名称结构完整（含工程/项目词）", "名称明确"]
            elif len(line) >= 6:
                fmt, clarity = 0.80, 0.75
                reason_parts = ["名称偏短", "名称可读"]
            else:
                fmt, clarity = 0.45, 0.55
                reason_parts = ["名称过短", "名称不完整"]
            candidate = _result(
                field_key,
                anchor=anchor,
                distance=lead,
                fmt=fmt,
                clarity=clarity,
                raw=line,
                value_text=None if placeholder else line,
                reason_parts=reason_parts,
                precision="absolute",
            )
            if best is None or candidate["confidence"] > best["confidence"]:
                best = candidate
    return best or _missing(field_key, anchors)


EXTRACTORS = {
    FieldKey.PROJECT_NAME.value: lambda text, anchors, published: _extract_project_name(text, anchors),
    FieldKey.BUDGET_AMOUNT.value: lambda text, anchors, published: _extract_budget(text, anchors),
    FieldKey.DEADLINE.value: lambda text, anchors, published: _extract_deadline(text, anchors, published),
    FieldKey.OPENING_PLACE.value: lambda text, anchors, published: _extract_opening(text, anchors),
}


def extract_field(
    text: str,
    field_key: str,
    published_at: datetime,
    anchors: list[str] | None = None,
) -> dict:
    spec = FIELD_SPEC[field_key]
    resolved = list(anchors or spec["anchors"])
    cleaner = EXTRACTORS[field_key]
    return cleaner(clean_text(text), resolved, published_at)


def extract_notice(
    text: str,
    published_at: datetime,
    anchors_by_field: dict[str, list[str]] | None = None,
) -> dict[str, dict]:
    body = clean_text(text)
    results: dict[str, dict] = {}
    for field_key in EXTRACTORS:
        anchors = (anchors_by_field or {}).get(field_key)
        spec = FIELD_SPEC[field_key]
        results[field_key] = EXTRACTORS[field_key](
            body, list(anchors or spec["anchors"]), published_at
        )
    return results


def is_low_confidence(confidence: float) -> bool:
    return confidence < settings.low_confidence_threshold


def parse_amount_text(value_text: str | None, unit: str | None = None) -> tuple[float | None, str | None, str | None]:
    """人工修正/文本解析：返回 (amount_yuan, unit, 归一后的值文本)。"""
    if not value_text:
        return None, None, None
    cleaned = collapse_spaces(value_text).replace("人民币", "").replace("¥", "").replace("￥", "")
    match = BUDGET_RE.search(cleaned)
    if match:
        number = to_float(match.group("num"))
        resolved_unit = match.group("unit")
        if number is None:
            return None, None, None
        return round(number * UNIT_TO_YUAN[resolved_unit], 2), resolved_unit, cleaned
    number_only = NUMBER_RE.search(cleaned)
    if number_only and unit in UNIT_TO_YUAN:
        number = to_float(number_only.group("num"))
        if number is None:
            return None, None, None
        return round(number * UNIT_TO_YUAN[unit], 2), unit, cleaned
    return None, None, cleaned


def parse_deadline_text(value_text: str | None, published_at: datetime | None = None) -> tuple[datetime | None, str, bool]:
    """人工修正/文本解析：返回 (事件时刻, precision, 是否估计)。"""
    if not value_text:
        return None, "missing", False
    cleaned = collapse_spaces(value_text)
    base = published_at or settings_demo_as_of()
    for pattern in (FULL_DATE_RE, PARTIAL_DATE_RE, RELATIVE_DATE_RE):
        match = pattern.search(cleaned)
        if match:
            return _parse_date_match(match, base)
    return None, "missing", False


def settings_demo_as_of() -> datetime:
    from src.services.deadline_service import demo_as_of

    return demo_as_of()


def bidder_qualification() -> str:
    return BIDDER_QUALIFICATION
