"""幂等 seed：3 账号 / 6 站点 / 3 个模板版本 / 120 条公告 / 480 个抽取字段 / 18 个截止事件。

自然键：
- users.email、sites.domain、templates(site_id,name,version)、notices(site_id,external_id)
- extracted_fields(notice_id,field_key)（已复核字段不覆盖）
- deadline_events(notice_id,kind)
- crawl_runs.seed_key

重复执行不新增、不覆盖人工修改；结束打印一行 SEED_SUMMARY（键顺序固定）。
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from src.config.database import session_scope
from src.constants.enums import TemplateStatus
from src.models.audit import AuditLog
from src.models.crawl_run import CrawlRun
from src.models.deadline_event import DeadlineEvent
from src.models.extracted_field import ExtractedField
from src.models.notice import Notice
from src.models.site import Site
from src.models.template import ExtractionTemplate
from src.models.user import User
from src.services import audit_service, crawl_service, deadline_service, source_catalog, template_service
from src.utils.security import hash_password

DEMO_PASSWORD = "Demo@2026"

DEMO_USERS = [
    ("admin@bidsift.io", "情报组长 · 周敏", "admin", None),
    ("analyst@bidsift.io", "情报专员 · 陈拓", "analyst", None),
    ("client@bidsift.io", "客户 BD · 林岚（只读）", "client", "市政"),
]

BASELINE_RUN_KEY = "crawl:baseline:2026-11-11"
TEMPLATE_V2_EXTRA_ANCHORS = {
    "budget_amount": ["最高限价", "招标控制上限"],
    "deadline": ["递交截止", "报名截止后 N 个工作日"],
}


def ensure_users(db) -> dict[str, User]:
    users: dict[str, User] = {}
    for email, display_name, role, industry in DEMO_USERS:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is None:
            existing = User(
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name=display_name,
                role=role,
                industry=industry,
                seed_key=f"user:{email}",
            )
            db.add(existing)
            db.flush()
        users[email] = existing
    return users


def ensure_sites(db) -> dict[str, Site]:
    sites: dict[str, Site] = {}
    for spec in source_catalog.SITE_SPECS:
        site = db.scalar(select(Site).where(Site.domain == spec.domain))
        if site is None:
            site = Site(
                name=spec.name,
                domain=spec.domain,
                region=spec.region,
                cadence_minutes=spec.cadence,
                qps_limit=spec.qps,
                status=spec.status,
                priority=spec.priority,
                note=spec.note,
            )
            db.add(site)
            db.flush()
        sites[spec.domain] = site
    return sites


def ensure_templates(db, sites: dict[str, Site]) -> dict[str, ExtractionTemplate]:
    default_rules = template_service.default_rules()
    v2_rules = template_service.normalize_rules(
        {
            key: {
                "anchors": list(default_rules[key]["anchors"]) + TEMPLATE_V2_EXTRA_ANCHORS.get(key, []),
                "patterns": list(default_rules[key]["patterns"]),
            }
            for key in default_rules
            if key in TEMPLATE_V2_EXTRA_ANCHORS
        }
    )
    ggzy = sites["ggzy.gov.cn"]
    gdggzy = sites["gdggzy.cn"]
    templates: dict[str, ExtractionTemplate] = {}
    templates["ggzy-v1"] = template_service.upsert_version(
        db,
        site_id=ggzy.id,
        name="工程招标标准模板",
        version=1,
        status=TemplateStatus.ACTIVE.value,
        rules=default_rules,
        coverage=0.94,
        change_note="初始版本：4 个字段锚点 + 金额/日期归一",
        created_by="admin@bidsift.io",
        published_at=source_catalog.BASE_TIME - timedelta(days=20),
    )
    templates["ggzy-v2"] = template_service.upsert_version(
        db,
        site_id=ggzy.id,
        name="工程招标标准模板",
        version=2,
        status=TemplateStatus.DRAFT.value,
        rules=v2_rules,
        coverage=0.97,
        change_note="新增「最高限价」锚点；日期补充「报名截止后 N 个工作日」推算",
        created_by="analyst@bidsift.io",
    )
    templates["gd-v1"] = template_service.upsert_version(
        db,
        site_id=gdggzy.id,
        name="交易中心附件正文模板",
        version=1,
        status=TemplateStatus.ACTIVE.value,
        rules=default_rules,
        coverage=0.88,
        change_note="适配「PDF 转 HTML」附件正文（排版噪声未清理）",
        created_by="admin@bidsift.io",
        published_at=source_catalog.BASE_TIME - timedelta(days=12),
    )
    return templates


def ensure_baseline_run(db) -> CrawlRun:
    run = db.scalar(select(CrawlRun).where(CrawlRun.seed_key == BASELINE_RUN_KEY))
    if run is None:
        run = CrawlRun(
            seed_key=BASELINE_RUN_KEY,
            status="success",
            triggered_by="admin@bidsift.io",
            site_count=len(source_catalog.SITE_SPECS),
            fetched_count=source_catalog.total_notice_count(),
            inserted_count=source_catalog.total_notice_count(),
            duplicate_count=0,
            error_count=0,
            duration_ms=4120,
            note="首轮全站采集（2026-11-11 06:00 批次）",
            started_at=source_catalog.BASE_TIME,
            finished_at=source_catalog.BASE_TIME + timedelta(minutes=1, seconds=52),
        )
        db.add(run)
        db.flush()
    return run


def ensure_notices(db, sites: dict[str, Site], run: CrawlRun) -> int:
    created = 0
    for payload in source_catalog.build_catalog():
        site = sites_by_domain(payload["site_key"], sites)
        existing = db.scalar(
            select(Notice).where(Notice.site_id == site.id, Notice.external_id == payload["external_id"])
        )
        if existing is not None:
            continue
        db.add(
            Notice(
                site_id=site.id,
                crawl_run_id=run.id,
                external_id=payload["external_id"],
                title=payload["title"],
                url=payload["url"],
                publisher=payload["publisher"],
                region=payload["region"],
                category=payload["category"],
                industry=payload["industry"],
                published_at=payload["published_at"],
                qualification=payload["qualification"],
                body_kind=payload["body_kind"],
                raw_html=payload["raw_html"],
                clean_text=payload["clean_text"],
                content_hash=payload["content_hash"],
                byte_size=payload["byte_size"],
                status=payload["status"],
                seed_key=f"notice:{payload['index']:04d}",
            )
        )
        created += 1
    db.flush()
    return created


def sites_by_domain(site_key: str, sites: dict[str, Site]) -> Site:
    spec = next(item for item in source_catalog.SITE_SPECS if item.key == site_key)
    return sites[spec.domain]


def ensure_audit_trail(db, users: dict[str, User]) -> None:
    admin = users["admin@bidsift.io"]
    analyst = users["analyst@bidsift.io"]
    audit_service.record(
        db,
        actor_email=admin.email,
        actor_role=admin.role,
        action="site.bootstrap",
        entity="site",
        entity_id=None,
        detail={"sites": len(source_catalog.SITE_SPECS), "note": "首轮采源登记"},
        seed_key="audit:seed:site-bootstrap",
    )
    audit_service.record(
        db,
        actor_email=analyst.email,
        actor_role=analyst.role,
        action="template.create",
        entity="template",
        entity_id=None,
        detail={"name": "工程招标标准模板", "version": 2},
        seed_key="audit:seed:template-v2",
    )
    audit_service.record(
        db,
        actor_email=admin.email,
        actor_role=admin.role,
        action="crawl.run",
        entity="crawl_run",
        entity_id=None,
        detail={"batch": "2026-11-11 06:00", "fetched": source_catalog.total_notice_count()},
        seed_key="audit:seed:first-crawl",
    )


def seed_all() -> str:
    """执行一次幂等 seed，返回 SEED_SUMMARY 行。"""
    with session_scope() as db:
        users = ensure_users(db)
        sites = ensure_sites(db)
        ensure_templates(db, sites)
        run = ensure_baseline_run(db)
        ensure_notices(db, sites, run)
        extraction = crawl_service.extract_all(db)
        deadline_service.ensure_tracked_events(db)
        risk = deadline_service.recompute_events(db)
        run.field_count = extraction["field_count"]
        run.low_confidence_count = extraction["low_confidence_count"]
        run.note = (
            f"首轮全站采集（2026-11-11 06:00 批次）；抽取 {extraction['field_count']} 字段，"
            f"低置信 {extraction['low_confidence_count']}"
        )
        ensure_audit_trail(db, users)
        db.flush()

        sites_count = db.scalar(select(func.count()).select_from(Site)) or 0
        notices_count = db.scalar(select(func.count()).select_from(Notice)) or 0
        fields_count = db.scalar(select(func.count()).select_from(ExtractedField)) or 0
        deadlines_count = db.scalar(select(func.count()).select_from(DeadlineEvent)) or 0
        users_count = db.scalar(select(func.count()).select_from(User)) or 0
        return (
            f"SEED_SUMMARY brand=bidsift "
            f"sites={sites_count} "
            f"notices={notices_count} "
            f"fields={fields_count} "
            f"deadlines={deadlines_count} "
            f"users={users_count}"
        )


if __name__ == "__main__":  # pragma: no cover
    print(seed_all())
