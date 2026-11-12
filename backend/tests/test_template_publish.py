"""模板发布回归测试：先重算、后切换；失败回滚；人工值保留；幂等。

运行方式（无需 MySQL / Docker）：

    cd backend
    python -m unittest discover -s tests -v

测试用内存 SQLite + 采源目录的合成数据，覆盖发布服务与路由层。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from src.constants.enums import FieldStatus  # noqa: E402
from src.models import Base  # noqa: E402
from src.models.deadline_event import DeadlineEvent  # noqa: E402
from src.models.extracted_field import ExtractedField  # noqa: E402
from src.models.notice import Notice  # noqa: E402
from src.models.site import Site  # noqa: E402
from src.models.template import ExtractionTemplate  # noqa: E402
from src.services import (  # noqa: E402
    crawl_service,
    deadline_service,
    extraction_engine,
    field_service,
    publish_service,
    source_catalog,
    template_service,
)
from src.utils.errors import AppError  # noqa: E402

DEADLINE_ANCHOR_SWAP = {"deadline": {"anchors": ["开标时间"]}}
OPENING_ANCHOR_SWAP = {"opening_place": {"anchors": ["建设地点"]}}
NO_MATCH_ANCHORS = {"deadline": {"anchors": ["不存在的字段标题"]}}


class PublishFixture(unittest.TestCase):
    """一份和 seed 同构的最小库：6 采源 / 120 公告 / 480 字段 / 18 事件。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.sites: dict[str, Site] = {}
        for spec in source_catalog.SITE_SPECS:
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
            self.db.add(site)
            self.db.flush()
            self.sites[spec.domain] = site
        for payload in source_catalog.build_catalog():
            spec = next(item for item in source_catalog.SITE_SPECS if item.key == payload["site_key"])
            self.db.add(
                Notice(
                    site_id=self.sites[spec.domain].id,
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
                )
            )
        self.db.flush()
        self.site = self.sites["ggzy.gov.cn"]
        self.other_site = self.sites["gdggzy.cn"]
        default = template_service.default_rules()
        self.v1 = self._add_template(self.site, 1, "active", default, 0.94)
        self._add_template(self.other_site, 1, "active", default, 0.88)
        crawl_service.extract_all(self.db)
        deadline_service.ensure_tracked_events(self.db)
        deadline_service.recompute_events(self.db)
        self.db.commit()
        self.default = default

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    # ------------------------------------------------------------ helpers

    def _add_template(self, site: Site, version: int, status: str, rules: dict, coverage: float) -> ExtractionTemplate:
        template = ExtractionTemplate(
            site_id=site.id,
            name="工程招标标准模板" if site is self.site else "交易中心附件正文模板",
            version=version,
            status=status,
            field_rules=rules,
            coverage_score=coverage,
            created_by="admin@bidsift.io",
        )
        self.db.add(template)
        self.db.flush()
        return template

    def _draft(self, raw_rules: dict, version: int = 2) -> ExtractionTemplate:
        template = self._add_template(
            self.site, version, "draft", template_service.normalize_rules(raw_rules), 0.5
        )
        self.db.commit()
        return template

    def _counts(self) -> tuple[int, int]:
        return (
            self.db.scalar(select(func.count()).select_from(ExtractedField)),
            self.db.scalar(select(func.count()).select_from(DeadlineEvent)),
        )

    def _site_fields(self, site: Site) -> list[tuple]:
        rows = self.db.scalars(
            select(ExtractedField)
            .join(Notice, Notice.id == ExtractedField.notice_id)
            .where(Notice.site_id == site.id)
            .order_by(ExtractedField.id)
        ).all()
        return [(row.id, row.value_text, row.event_at, row.confidence, row.status, row.extracted_at) for row in rows]

    def _site_events(self, site: Site) -> list[tuple]:
        rows = self.db.scalars(
            select(DeadlineEvent)
            .join(Notice, Notice.id == DeadlineEvent.notice_id)
            .where(Notice.site_id == site.id)
            .order_by(DeadlineEvent.id)
        ).all()
        return [(row.id, row.event_at, row.precision, row.risk_level, row.risk_score) for row in rows]

    def _tracked_notice(self) -> Notice:
        return self.db.scalar(select(Notice).where(Notice.site_id == self.site.id).order_by(Notice.id))

    def _field(self, notice: Notice, key: str) -> ExtractedField:
        return self.db.scalar(
            select(ExtractedField).where(
                ExtractedField.notice_id == notice.id, ExtractedField.field_key == key
            )
        )


class PreviewTests(PublishFixture):
    def test_preview_reports_impact_and_writes_nothing(self) -> None:
        self._field(self._tracked_notice(), "deadline").status = FieldStatus.CORRECTED.value
        self.db.commit()
        v2 = self._draft(DEADLINE_ANCHOR_SWAP)
        fields_before = self._site_fields(self.site)
        events_before = self._site_events(self.site)

        preview = publish_service.preview_publish(self.db, v2.id)

        self.assertFalse(preview["applied"])
        self.assertGreater(preview["affected_notice_count"], 0)
        self.assertGreater(preview["field_summary"]["changed_value"], 0)
        self.assertEqual(preview["previous"]["version"], 1)
        self.assertIn("pending_dates", preview)
        # 只读：字段、事件、版本状态都不变
        self.assertEqual(fields_before, self._site_fields(self.site))
        self.assertEqual(events_before, self._site_events(self.site))
        self.assertEqual(v2.status, "draft")

    def test_preview_scoped_to_template_site(self) -> None:
        v2 = self._draft(OPENING_ANCHOR_SWAP)
        other_before = self._site_fields(self.other_site)
        publish_service.preview_publish(self.db, v2.id)
        self.assertEqual(other_before, self._site_fields(self.other_site))


class PublishSwitchTests(PublishFixture):
    def test_publish_recomputes_history_then_switches(self) -> None:
        v2 = self._draft(DEADLINE_ANCHOR_SWAP)
        other_before = (self._site_fields(self.other_site), self._site_events(self.other_site))
        result = publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
        self.db.commit()

        self.assertTrue(result["applied"])
        self.assertEqual(result["template"]["status"], "active")
        self.assertEqual(result["template"]["version"], 2)
        self.assertEqual(result["archived"], [self.v1.id])
        self.assertGreater(result["field_summary"]["changed_value"], 0)
        self.assertEqual(result["field_summary"]["unchanged"] + result["field_summary"]["updated"] + result["field_summary"]["preserved_manual"] + result["field_summary"]["created"], result["field_summary"]["total"])
        # 历史公告的日历事件已按新规则重算
        self.assertEqual(result["deadline_summary"]["event_count"], len(self._site_events(self.site)))
        # 其他采源不受影响
        self.assertEqual(other_before, (self._site_fields(self.other_site), self._site_events(self.other_site)))
        self.assertEqual(self._counts(), (480, 18))

        active = self.db.scalars(
            select(ExtractionTemplate).where(
                ExtractionTemplate.site_id == self.site.id, ExtractionTemplate.status == "active"
            )
        ).all()
        self.assertEqual([item.id for item in active], [v2.id])

    def test_manual_values_and_events_survive_publish(self) -> None:
        notice = self._tracked_notice()
        deadline = self._field(notice, "deadline")
        field_service.correct_field(self.db, deadline.id, {"value": "2026年12月31日 17:00"}, "analyst@bidsift.io")
        opening = self._field(notice, "opening_place")
        field_service.verify_field(self.db, opening.id, "analyst@bidsift.io")
        self.db.commit()

        v2 = self._draft(DEADLINE_ANCHOR_SWAP)
        result = publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
        self.db.commit()

        self.assertEqual(result["field_summary"]["preserved_manual"], 2)
        self.db.refresh(deadline)
        self.db.refresh(opening)
        self.assertEqual(deadline.status, FieldStatus.CORRECTED.value)
        self.assertEqual(deadline.value_text, "2026年12月31日 17:00")
        self.assertEqual(opening.status, FieldStatus.VERIFIED.value)
        event = self.db.scalar(
            select(DeadlineEvent).where(DeadlineEvent.notice_id == notice.id, DeadlineEvent.kind == "enroll")
        )
        self.assertEqual(event.event_at, deadline.event_at)

    def test_never_matching_rules_surface_pending_dates(self) -> None:
        v2 = self._draft(NO_MATCH_ANCHORS)
        preview = publish_service.preview_publish(self.db, v2.id)
        self.assertGreater(preview["deadline_summary"]["pending_date_count"], 0)
        result = publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
        self.db.commit()
        self.assertEqual(
            result["deadline_summary"]["risk_after"].get("unknown"),
            result["deadline_summary"]["pending_date_count"],
        )

    def test_republish_is_noop(self) -> None:
        v2 = self._draft(DEADLINE_ANCHOR_SWAP)
        publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
        self.db.commit()
        fields_before = self._site_fields(self.site)
        events_before = self._site_events(self.site)

        again = publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
        self.db.commit()

        self.assertTrue(again["noop"])
        self.assertEqual(again["archived"], [])
        self.assertEqual(fields_before, self._site_fields(self.site))
        self.assertEqual(events_before, self._site_events(self.site))
        self.assertEqual(self._counts(), (480, 18))

    def test_identical_rules_do_not_touch_rows(self) -> None:
        v2 = self._draft(self.default)
        fields_before = self._site_fields(self.site)
        events_before = self._site_events(self.site)
        result = publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
        self.db.commit()
        self.assertEqual(result["field_summary"]["updated"], 0)
        self.assertEqual(result["field_summary"]["unchanged"], len(fields_before))
        self.assertEqual(fields_before, self._site_fields(self.site))
        self.assertEqual(events_before, self._site_events(self.site))

    def test_switch_back_restores_previous_values(self) -> None:
        baseline = self._site_fields(self.site)
        v2 = self._draft(DEADLINE_ANCHOR_SWAP)
        publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
        self.db.commit()
        changed = self._site_fields(self.site)
        self.assertNotEqual([(row[1], row[2]) for row in baseline], [(row[1], row[2]) for row in changed])

        publish_service.publish_template(self.db, self.v1.id, "admin@bidsift.io")
        self.db.commit()
        restored = self._site_fields(self.site)
        self.assertEqual([(row[1], row[2], row[3]) for row in baseline], [(row[1], row[2], row[3]) for row in restored])
        self.assertEqual(self._counts(), (480, 18))


class FailureRecoveryTests(PublishFixture):
    def test_failed_switch_rolls_back_and_keeps_previous_version(self) -> None:
        v2 = self._draft(DEADLINE_ANCHOR_SWAP)
        fields_before = self._site_fields(self.site)
        events_before = self._site_events(self.site)
        templates_before = sorted(
            (item.id, item.status) for item in self.db.scalars(select(ExtractionTemplate)).all()
        )

        original = publish_service._archive_site_active
        publish_service._archive_site_active = lambda db, template: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            with self.assertRaises(AppError) as caught:
                publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
            self.db.rollback()
        finally:
            publish_service._archive_site_active = original

        self.assertEqual(caught.exception.code, "PUBLISH_FAILED")
        self.assertEqual(fields_before, self._site_fields(self.site))
        self.assertEqual(events_before, self._site_events(self.site))
        self.assertEqual(
            templates_before,
            sorted((item.id, item.status) for item in self.db.scalars(select(ExtractionTemplate)).all()),
        )
        self.assertEqual(self.v1.status, "active")

        # 重试能从上一版干净状态恢复
        retried = publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
        self.db.commit()
        self.assertEqual(retried["template"]["status"], "active")
        self.assertEqual(self._counts(), (480, 18))

    def test_extraction_error_aborts_before_any_write(self) -> None:
        v2 = self._draft(DEADLINE_ANCHOR_SWAP)
        fields_before = self._site_fields(self.site)

        original = extraction_engine.extract_notice
        extraction_engine.extract_notice = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad body"))
        try:
            with self.assertRaises(AppError) as caught:
                publish_service.publish_template(self.db, v2.id, "admin@bidsift.io")
            self.db.rollback()
        finally:
            extraction_engine.extract_notice = original

        self.assertEqual(caught.exception.code, "PUBLISH_FAILED")
        self.assertEqual(fields_before, self._site_fields(self.site))
        self.assertEqual(v2.status, "draft")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
