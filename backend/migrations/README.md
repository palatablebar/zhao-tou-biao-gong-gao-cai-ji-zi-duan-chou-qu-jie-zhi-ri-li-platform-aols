# 迁移说明

- 表结构以 `backend/src/models/` 下的 SQLAlchemy 2.0 声明为唯一事实来源，
  容器启动时由 `src/config/app.py` 的 `_bootstrap_database()` 执行 `Base.metadata.create_all()` 建表。
- `0001_initial.sql` 是同一份结构的 MySQL 8.0 DDL 快照，供评审/手工初始化使用（`IF NOT EXISTS` 可重复执行）。
- 目前没有增量迁移（没有 alembic）；后续加字段时新增 `0002_xxx.sql` 并同步 models。
- 幂等 seed 依赖的唯一键：`users.email`、`sites.domain`、`extraction_templates(site_id,name,version)`、
  `notices(site_id,external_id)`、`extracted_fields(notice_id,field_key)`、`deadline_events(notice_id,kind)`、
  `crawl_runs.seed_key`。
