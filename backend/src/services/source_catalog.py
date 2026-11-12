"""确定性「采源目录」：6 个交易中心/招标网 + 120 条公告正文。

用途：
1. seed 用它灌入 120 条公告（自然键 = site_id + external_id）；
2. 采集批次（CrawlRun）用它模拟「重新抓取同一批公告」，配合 content_hash 去重；
3. 抽取引擎在同一份正文上跑，保证同输入同分数（可复现）。

正文缺陷分布是刻意设计的（算法 1 的低置信来源）：
- 12 条公告预算金额写成「面议 / 详见招标文件」；
- 9 条公告开标地点写成「另行通知」；
- 8 条公告报名截止时间写成「另行通知」；
- 4 条公告预算金额与报名截止时间同时缺失（各 2 个字段）；
=> 37 个抽取字段置信度 < 0.55，进入复核队列。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape

from src.constants.enums import (
    CATEGORY_INDUSTRY,
    DeadlineKind,
    NoticeStatus,
    QualLevel,
    SiteStatus,
)
from src.constants.fieldspec import QUAL_RAW
from src.utils.textutil import clean_text


@dataclass(frozen=True)
class SiteSpec:
    key: str
    name: str
    domain: str
    region: str
    cadence: int
    qps: int
    priority: int
    status: str
    note: str
    notice_count: int


SITE_SPECS: list[SiteSpec] = [
    SiteSpec(
        key="ggzy",
        name="全国公共资源交易平台（工程招标）",
        domain="ggzy.gov.cn",
        region="全国",
        cadence=60,
        qps=2,
        priority=1,
        status=SiteStatus.ACTIVE.value,
        note="工程类公告主采源，公告量最大，字段格式最规范",
        notice_count=30,
    ),
    SiteSpec(
        key="gdggzy",
        name="广东省公共资源交易中心",
        domain="gdggzy.cn",
        region="华南",
        cadence=120,
        qps=2,
        priority=2,
        status=SiteStatus.ACTIVE.value,
        note="华南片区主源，含 PDF 转 HTML 附件正文",
        notice_count=24,
    ),
    SiteSpec(
        key="jsggzy",
        name="江苏省公共资源交易平台",
        domain="jsggzy.cn",
        region="华东",
        cadence=90,
        qps=3,
        priority=3,
        status=SiteStatus.ACTIVE.value,
        note="华东片区主源，金额单位混用（元/万元）",
        notice_count=22,
    ),
    SiteSpec(
        key="zjggzy",
        name="浙江省公共资源交易服务平台",
        domain="zjggzy.cn",
        region="华东",
        cadence=90,
        qps=3,
        priority=4,
        status=SiteStatus.ACTIVE.value,
        note="华东补充源，截止时间常用「报名截止后 N 个工作日」",
        notice_count=16,
    ),
    SiteSpec(
        key="scggzy",
        name="四川省公共资源交易信息网",
        domain="scggzy.cn",
        region="西南",
        cadence=180,
        qps=2,
        priority=5,
        status=SiteStatus.DEGRADED.value,
        note="西南片区源，近期响应偏慢（已降级但仍采集）",
        notice_count=15,
    ),
    SiteSpec(
        key="sdggzy",
        name="山东省公共资源交易中心",
        domain="sdggzy.cn",
        region="华北",
        cadence=180,
        qps=2,
        priority=6,
        status=SiteStatus.ACTIVE.value,
        note="华北片区源，开标地点写法不统一",
        notice_count=13,
    ),
]

# ---- 缺陷公告下标（全局 0..119，互不重叠）----
DEFECT_BUDGET: frozenset[int] = frozenset({3, 11, 19, 27, 35, 43, 51, 63, 71, 83, 95, 107})
DEFECT_OPENING: frozenset[int] = frozenset({7, 15, 23, 31, 39, 47, 55, 67, 79})
DEFECT_DEADLINE: frozenset[int] = frozenset({5, 13, 21, 29, 37, 45, 53, 61})
DEFECT_DOUBLE: frozenset[int] = frozenset({9, 17, 25, 33})

# ---- 「PDF 转 HTML」附件正文公告（正文带排版噪声）----
PDF_NOTICES: frozenset[int] = frozenset({44, 68})
# ---- 「报名截止后 3 个工作日」相对日期公告 ----
RELATIVE_DEADLINE_NOTICES: frozenset[int] = frozenset({99})

# ---- 截止日历 18 个跟踪事件（索引 / 类型 / 事件时刻 / 资质门槛覆盖）----
# 事件时刻为 None 的一条 = 报名截止时间「另行通知」，风险档位 unknown，需人工补全。
TRACKED_PLAN: list[dict] = [
    {"index": 0, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 12, 9, 30), "qualification": QualLevel.NONE.value},
    {"index": 1, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 12, 14, 0), "qualification": QualLevel.GRADE_1.value},
    {"index": 2, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 12, 16, 30), "qualification": QualLevel.GRADE_2.value},
    {"index": 4, "kind": DeadlineKind.BID_OPEN.value, "at": datetime(2026, 11, 12, 17, 30), "qualification": QualLevel.NONE.value},
    {"index": 6, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 13, 10, 0), "qualification": QualLevel.GRADE_2.value},
    {"index": 8, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 13, 12, 30), "qualification": QualLevel.GRADE_1.value},
    {"index": 10, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 13, 15, 0), "qualification": QualLevel.NONE.value},
    {"index": 12, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 13, 17, 0), "qualification": QualLevel.GRADE_2.value},
    {"index": 14, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 13, 18, 0), "qualification": QualLevel.GRADE_SPECIAL.value},
    {"index": 16, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 18, 15, 0), "qualification": QualLevel.NONE.value},
    {"index": 18, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 19, 12, 0), "qualification": QualLevel.GRADE_2.value},
    {"index": 20, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 19, 18, 0), "qualification": QualLevel.NONE.value},
    {"index": 22, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 20, 12, 0), "qualification": QualLevel.GRADE_1.value},
    {"index": 24, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 20, 14, 0), "qualification": QualLevel.GRADE_2.value},
    {"index": 26, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 23, 12, 0), "qualification": QualLevel.NONE.value},
    {"index": 28, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 24, 12, 0), "qualification": QualLevel.GRADE_2.value},
    {"index": 30, "kind": DeadlineKind.ENROLL.value, "at": datetime(2026, 11, 25, 18, 0), "qualification": QualLevel.NONE.value},
    {"index": 37, "kind": DeadlineKind.ENROLL.value, "at": None, "qualification": QualLevel.GRADE_1.value},
]

TRACKED_INDEXES: frozenset[int] = frozenset(item["index"] for item in TRACKED_PLAN)

BASE_TIME = datetime(2026, 11, 11, 6, 0, 0)
DEMO_AS_OF = datetime(2026, 11, 12, 9, 0, 0)

PROJECT_BASES: list[str] = [
    "滨江路综合管廊",
    "环城北路快速化改造",
    "高铁新城安置房",
    "老城区雨污分流",
    "东部新城地下空间",
    "文化艺术中心二期",
    "人民医院住院楼",
    "城北污水处理厂提标",
    "跨江第二大桥",
    "城市轨道交通三号线",
    "中央公园景观提升",
    "智慧交通信号系统",
    "老旧小区综合改造",
    "实验中学教学楼",
    "港区疏港公路",
    "会展中心幕墙",
    "城市河道综合整治",
    "体育中心改扩建",
    "第三自来水厂扩建",
    "生活垃圾焚烧发电",
    "市民服务中心",
    "城市大脑数据中心",
    "妇幼保健院迁建",
    "物流园区道路",
]

CITY_BY_REGION: dict[str, list[tuple[str, list[str]]]] = {
    "华南": [("广州市", ["天河区", "越秀区", "番禺区"]), ("深圳市", ["南山区", "宝安区"]), ("佛山市", ["南海区", "顺德区"]), ("东莞市", ["松山湖", "虎门镇"])],
    "华东": [("南京市", ["玄武区", "江宁区"]), ("苏州市", ["工业园区", "吴中区"]), ("杭州市", ["萧山区", "余杭区"]), ("宁波市", ["鄞州区", "北仑区"]), ("合肥市", ["蜀山区", "包河区"])],
    "西南": [("成都市", ["天府新区", "高新区"]), ("绵阳市", ["涪城区", "游仙区"])],
    "华北": [("青岛市", ["崂山区", "西海岸新区"]), ("烟台市", ["芝罘区", "开发区"]), ("济南市", ["历下区", "章丘区"])],
    "西北": [("西安市", ["雁塔区", "高新区"]), ("兰州市", ["城关区", "安宁区"])],
}
REGION_CYCLE: list[str] = ["华东", "华南", "华北", "西南", "西北"]

PURCHASER_TEMPLATE = "{city}{district}城市建设投资集团有限公司"
AGENT = "中鼎工程咨询有限公司"
OPENING_ROOM = ["开标一室", "开标二室", "开标三室", "第四评标室"]

PLACEHOLDER_BUDGET = "面议"
PLACEHOLDER_OPENING = "另行通知"


def _site_ranges() -> list[tuple[SiteSpec, int, int]]:
    ranges: list[tuple[SiteSpec, int, int]] = []
    cursor = 0
    for spec in SITE_SPECS:
        ranges.append((spec, cursor, cursor + spec.notice_count))
        cursor += spec.notice_count
    return ranges


def total_notice_count() -> int:
    return sum(spec.notice_count for spec in SITE_SPECS)


def site_for_index(index: int) -> SiteSpec:
    for spec, start, end in _site_ranges():
        if start <= index < end:
            return spec
    raise IndexError(f"notice index out of range: {index}")


def _city_for(spec: SiteSpec, index: int) -> tuple[str, str, str]:
    if spec.region == "全国":
        region = REGION_CYCLE[index % len(REGION_CYCLE)]
    else:
        region = spec.region
    cities = CITY_BY_REGION[region]
    city, districts = cities[index % len(cities)]
    district = districts[(index // len(cities)) % len(districts)]
    return region, city, district


def _budget_wan(index: int) -> float:
    return round(860.0 + index * 137.5 + (index % 5) * 42.25, 2)


def _format_wan(value: float) -> str:
    return f"{value:,.2f} 万元"


def _deadline_text(value: datetime) -> str:
    return f"{value.year}年{value.month}月{value.day}日 {value.hour:02d}:{value.minute:02d}"


def _published_at(index: int) -> datetime:
    return BASE_TIME - timedelta(days=(index % 10) + 1, minutes=(index * 13) % 540)


def _normal_deadline(index: int, published: datetime) -> datetime:
    return (published + timedelta(days=4 + (index % 8))).replace(hour=17, minute=0, second=0, microsecond=0)


def _build_lines(
    *,
    index: int,
    spec: SiteSpec,
    external_id: str,
    project_name: str,
    publisher: str,
    city: str,
    district: str,
    qualification: str,
    published: datetime,
    budget_text: str,
    deadline_text: str,
    opening_text: str,
    open_text: str,
) -> list[str]:
    category = CATEGORY_FOR_INDEX(index)
    lines = [
        f"{project_name}招标公告",
        f"交易编号：{external_id}",
        f"项目名称：{project_name}",
        f"招标人：{publisher}｜招标代理：{AGENT}",
        f"预算金额：{budget_text}",
        f"建设地点：{city}{district}",
        f"资质要求：{QUAL_RAW.get(qualification, '无特殊资质要求')}",
        f"报名截止时间：{deadline_text}",
        f"开标地点：{opening_text}",
        f"开标时间：{open_text}",
        f"公告类别：{category}｜发布媒体：{spec.name}",
        f"发布日期：{published.strftime('%Y年%m月%d日')}",
    ]
    if index in PDF_NOTICES:
        lines.insert(1, "附件正文（PDF 转 HTML 抽取，原始排版换行未清理）")
        lines.insert(2, "… 本页为公告附件第 2 页，页眉页脚与表格边框已丢弃 …")
        lines.append("… 附件第 3 页：投标人须知前附表（略）…")
    return lines


def CATEGORY_FOR_INDEX(index: int) -> str:
    from src.constants.enums import CATEGORIES

    return CATEGORIES[index % len(CATEGORIES)]


def render_html(title: str, lines: list[str]) -> str:
    paragraphs = "\n".join(f"  <p>{escape(line)}</p>" for line in lines if line)
    return (
        '<div class="notice-doc" data-render="html">\n'
        f"  <h2>{escape(title)}</h2>\n"
        f"{paragraphs}\n"
        "</div>"
    )


def build_notice(index: int) -> dict:
    """生成第 index 条公告（纯函数，同 index 同结果）。"""
    spec = site_for_index(index)
    seq = index + 1
    external_id = f"BID-{spec.key.upper()}-2026-{seq:04d}"
    region, city, district = _city_for(spec, index)
    base = PROJECT_BASES[index % len(PROJECT_BASES)]
    phase = ["一期", "二期", "三期", "四期"][(index // 2) % 4]
    category = CATEGORY_FOR_INDEX(index)
    project_name = f"{city}{base}工程（{phase}）施工"
    publisher = PURCHASER_TEMPLATE.format(city=city, district=district)
    qualification = [
        QualLevel.NONE.value,
        QualLevel.GRADE_2.value,
        QualLevel.GRADE_1.value,
        QualLevel.GRADE_2.value,
        QualLevel.NONE.value,
        QualLevel.GRADE_SPECIAL.value,
        QualLevel.GRADE_1.value,
        QualLevel.GRADE_2.value,
    ][index % 8]
    published = _published_at(index)
    budget_text = _format_wan(_budget_wan(index))
    deadline_at = _normal_deadline(index, published)
    deadline_text = _deadline_text(deadline_at)
    floor = 3 + (index % 9)
    opening_text = (
        f"{city}{district}公共资源交易服务中心 {OPENING_ROOM[index % 4]}"
        f"（{district}政务服务中心 {floor} 楼）"
    )

    tracked = next((item for item in TRACKED_PLAN if item["index"] == index), None)
    if tracked is not None:
        qualification = tracked["qualification"]
        if tracked["kind"] == DeadlineKind.ENROLL.value and tracked["at"] is not None:
            deadline_at = tracked["at"]
            deadline_text = _deadline_text(deadline_at)
        if tracked["kind"] == DeadlineKind.BID_OPEN.value:
            deadline_at = (tracked["at"] - timedelta(days=1)).replace(hour=17, minute=0)
            deadline_text = _deadline_text(deadline_at)
        if tracked["at"] is None:
            deadline_text = PLACEHOLDER_OPENING

    open_at = deadline_at + timedelta(hours=2) if tracked is None else (
        tracked["at"] if tracked["kind"] == DeadlineKind.BID_OPEN.value else deadline_at + timedelta(days=2, hours=-1)
    )
    open_text = _deadline_text(open_at)

    if index in RELATIVE_DEADLINE_NOTICES:
        deadline_text = "报名截止后 3 个工作日"
    if index in DEFECT_BUDGET or index in DEFECT_DOUBLE:
        budget_text = PLACEHOLDER_BUDGET if index % 2 == 0 else "详见招标文件"
    if index in DEFECT_OPENING:
        opening_text = PLACEHOLDER_OPENING
    if index in DEFECT_DEADLINE or index in DEFECT_DOUBLE:
        deadline_text = PLACEHOLDER_OPENING if index % 2 == 0 else "见公告补充文件"
    if index == 44:
        budget_text = "约 1,250 万元（含税）"
    if index == 68:
        deadline_text = "12月3日上午9点半"

    title = f"{project_name}招标公告（{external_id}）"
    lines = _build_lines(
        index=index,
        spec=spec,
        external_id=external_id,
        project_name=project_name,
        publisher=publisher,
        city=city,
        district=district,
        qualification=qualification,
        published=published,
        budget_text=budget_text,
        deadline_text=deadline_text,
        opening_text=opening_text,
        open_text=open_text,
    )
    clean = clean_text("\n".join(line for line in lines if line))
    html = render_html(title, lines)
    status = NoticeStatus.TRACKING.value if index in TRACKED_INDEXES else NoticeStatus.NEW.value
    return {
        "index": index,
        "site_key": spec.key,
        "external_id": external_id,
        "title": title,
        "url": f"https://{spec.domain}/notice/{external_id}",
        "publisher": publisher,
        "region": region,
        "category": category,
        "industry": CATEGORY_INDUSTRY[category],
        "published_at": published,
        "qualification": qualification,
        "body_kind": "pdf" if index in PDF_NOTICES else "html",
        "raw_html": html,
        "clean_text": clean,
        "byte_size": len(html.encode("utf-8")),
        "content_hash": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
        "status": status,
        "expected_deadline_at": deadline_at if index in TRACKED_INDEXES else None,
    }


def build_catalog() -> list[dict]:
    return [build_notice(index) for index in range(total_notice_count())]


def notices_for_site(domain: str) -> list[dict]:
    """采集批次在「重新抓取」时调用：返回该站点当前的公告目录（与 seed 完全一致）。"""
    spec = next((item for item in SITE_SPECS if item.domain == domain), None)
    if spec is None:
        return []
    return [build_notice(index) for index in range(total_notice_count()) if site_for_index(index).key == spec.key]


def tracked_plan_by_index() -> dict[int, dict]:
    return {item["index"]: item for item in TRACKED_PLAN}
