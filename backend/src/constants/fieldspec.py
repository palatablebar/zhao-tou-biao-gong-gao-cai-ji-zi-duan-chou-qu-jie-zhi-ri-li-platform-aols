"""字段抽取规格：锚点词、正则、单位/日期归一与评分口径。

算法 1（字段抽取置信度）的口径全部集中在这里，模板版本只覆盖「锚点词 + 正则」，
权重与分档不允许模板改动，保证同输入同分数。
"""
from __future__ import annotations

from src.constants.enums import FieldKey, QualLevel

# 上下文锚点最近邻窗口（字符）；超过该距离视为无有效上下文
ANCHOR_MAX_DISTANCE = 80

# 置信度权重：锚点距离 0.35 + 格式匹配 0.35 + 单位/日期明确性 0.30
CONFIDENCE_WEIGHTS: dict[str, float] = {
    "anchor": 0.35,
    "format": 0.35,
    "clarity": 0.30,
}

FIELD_SPEC: dict[str, dict] = {
    FieldKey.PROJECT_NAME.value: {
        "label": "项目名称",
        "anchors": ["项目名称", "工程名称", "采购项目名称", "标的名称"],
        "patterns": [r"(?P<value>[^\n，。；|]{6,60})"],
    },
    FieldKey.BUDGET_AMOUNT.value: {
        "label": "预算金额",
        "anchors": ["预算金额", "招标控制价", "最高限价", "采购预算", "项目投资额"],
        "patterns": [
            r"(?P<mod>约|暂定|估算|不超过|最高不超过)?\s*(?P<cur>人民币|￥|¥)?\s*"
            r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>亿元|万元|元)"
        ],
    },
    FieldKey.DEADLINE.value: {
        "label": "报名截止时间",
        "anchors": ["报名截止时间", "投标截止时间", "递交截止时间", "获取招标文件截止时间"],
        "patterns": [
            r"(?P<y>20\d{2})\s*[年\-/.]\s*(?P<m>\d{1,2})\s*[月\-/.]\s*(?P<d>\d{1,2})\s*日?"
            r"\s*(?:(?P<ampm>上午|下午|晚上|中午)?\s*(?P<hh>\d{1,2})\s*[:：点时]\s*(?P<mm>\d{1,2}|半)?\s*分?)?",
            r"(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日"
            r"\s*(?:(?P<ampm>上午|下午|晚上|中午)?\s*(?P<hh>\d{1,2})\s*[:：点时]\s*(?P<mm>\d{1,2}|半)?\s*分?)?",
            r"(?:报名截止后|投标截止后|后)\s*(?P<n>\d{1,2})\s*个工作日",
        ],
    },
    FieldKey.OPENING_PLACE.value: {
        "label": "开标地点",
        "anchors": ["开标地点", "开标地址", "递交地点", "开标室"],
        "patterns": [r"(?P<value>[^\n；|]{4,60})"],
    },
}

# 占位/无效话术：命中即判定「单位或日期不明确」
PLACEHOLDER_WORDS: tuple[str, ...] = (
    "另行通知",
    "另行公告",
    "详见",
    "待定",
    "面议",
    "见公告",
    "补充文件",
    "暂不明确",
)

# 金额单位 -> 元
UNIT_TO_YUAN: dict[str, float] = {
    "亿元": 100_000_000.0,
    "万元": 10_000.0,
    "元": 1.0,
}

# 客户资质门槛与本公司资质（工程咨询乙级 = grade_2）的差距
BIDDER_QUALIFICATION = QualLevel.GRADE_2.value
QUALIFY_GAP: dict[str, float] = {
    QualLevel.NONE.value: 0.0,
    QualLevel.GRADE_2.value: 0.0,
    QualLevel.GRADE_1.value: 0.45,
    QualLevel.GRADE_SPECIAL.value: 0.85,
}

QUAL_LABEL: dict[str, str] = {
    QualLevel.NONE.value: "无特殊资质要求",
    QualLevel.GRADE_2.value: "工程咨询乙级（二级）及以上",
    QualLevel.GRADE_1.value: "工程咨询甲级（一级）及以上",
    QualLevel.GRADE_SPECIAL.value: "工程咨询综合（特级）资质",
}

QUAL_RAW: dict[str, str] = {
    QualLevel.NONE.value: "无特殊资质要求",
    QualLevel.GRADE_2.value: "投标人须具备工程咨询乙级（二级）及以上资质",
    QualLevel.GRADE_1.value: "投标人须具备工程咨询甲级（一级）及以上资质",
    QualLevel.GRADE_SPECIAL.value: "投标人须具备工程咨询综合（特级）资质",
}

# 算法 2 分档阈值（settings 里可覆盖，这里给文档默认值）
RISK_BANDS = {
    "must_act_pressure": 0.45,
    "watch_pressure": 0.15,
    "qualify_blocking_gap": 0.5,
}

RISK_LABEL: dict[str, str] = {
    "must_act": "本周必投",
    "watch": "观察",
    "skip": "放弃",
    "unknown": "待补日期",
}
