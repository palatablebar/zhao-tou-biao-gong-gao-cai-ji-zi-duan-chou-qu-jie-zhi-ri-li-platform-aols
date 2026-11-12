-- bidsift 初始 schema（MySQL 8.0 / utf8mb4）
-- 说明：运行期由 SQLAlchemy 2.0 `Base.metadata.create_all()` 自动建表；
-- 本文件用于评审时直接阅读表结构，或在既有 DBA 流程中手动初始化。
-- 唯一约束即 seed 的幂等自然键。

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(160) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(80) NOT NULL,
  role VARCHAR(20) NOT NULL,
  industry VARCHAR(20) NULL,
  seed_key VARCHAR(120) NULL UNIQUE,
  created_at DATETIME NOT NULL,
  KEY idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  actor_email VARCHAR(160) NOT NULL,
  actor_role VARCHAR(20) NOT NULL,
  action VARCHAR(60) NOT NULL,
  entity VARCHAR(40) NOT NULL,
  entity_id VARCHAR(40) NULL,
  detail JSON NOT NULL,
  ip VARCHAR(60) NULL,
  layer VARCHAR(20) NOT NULL DEFAULT 'domain',
  seed_key VARCHAR(160) NULL UNIQUE,
  created_at DATETIME NOT NULL,
  KEY idx_audit_actor (actor_email),
  KEY idx_audit_action (action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sites (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  domain VARCHAR(120) NOT NULL UNIQUE,
  region VARCHAR(20) NOT NULL,
  cadence_minutes INT NOT NULL DEFAULT 60,
  qps_limit INT NOT NULL DEFAULT 2,
  status VARCHAR(20) NOT NULL,
  priority INT NOT NULL DEFAULT 5,
  note VARCHAR(255) NULL,
  created_at DATETIME NOT NULL,
  KEY idx_sites_region (region),
  KEY idx_sites_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS extraction_templates (
  id INT AUTO_INCREMENT PRIMARY KEY,
  site_id INT NOT NULL,
  name VARCHAR(80) NOT NULL,
  version INT NOT NULL DEFAULT 1,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  field_rules JSON NOT NULL,
  coverage_score DOUBLE NOT NULL DEFAULT 0,
  change_note VARCHAR(255) NULL,
  created_by VARCHAR(160) NOT NULL,
  created_at DATETIME NOT NULL,
  published_at DATETIME NULL,
  UNIQUE KEY uq_template_version (site_id, name, version),
  CONSTRAINT fk_template_site FOREIGN KEY (site_id) REFERENCES sites (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS crawl_runs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  seed_key VARCHAR(120) NULL UNIQUE,
  status VARCHAR(20) NOT NULL DEFAULT 'running',
  triggered_by VARCHAR(160) NOT NULL,
  site_count INT NOT NULL DEFAULT 0,
  fetched_count INT NOT NULL DEFAULT 0,
  inserted_count INT NOT NULL DEFAULT 0,
  duplicate_count INT NOT NULL DEFAULT 0,
  error_count INT NOT NULL DEFAULT 0,
  field_count INT NOT NULL DEFAULT 0,
  low_confidence_count INT NOT NULL DEFAULT 0,
  duration_ms INT NOT NULL DEFAULT 0,
  note VARCHAR(255) NULL,
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  KEY idx_runs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notices (
  id INT AUTO_INCREMENT PRIMARY KEY,
  site_id INT NOT NULL,
  crawl_run_id INT NULL,
  external_id VARCHAR(80) NOT NULL,
  title VARCHAR(255) NOT NULL,
  url VARCHAR(400) NOT NULL,
  publisher VARCHAR(160) NOT NULL,
  region VARCHAR(20) NOT NULL,
  category VARCHAR(30) NOT NULL,
  industry VARCHAR(20) NOT NULL,
  published_at DATETIME NOT NULL,
  qualification VARCHAR(20) NOT NULL DEFAULT 'none',
  body_kind VARCHAR(20) NOT NULL DEFAULT 'html',
  raw_html LONGTEXT NOT NULL,
  clean_text LONGTEXT NOT NULL,
  content_hash VARCHAR(64) NOT NULL,
  byte_size INT NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'new',
  seed_key VARCHAR(160) NULL UNIQUE,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_notice_external (site_id, external_id),
  KEY idx_notices_region (region),
  KEY idx_notices_category (category),
  KEY idx_notices_published (published_at),
  KEY idx_notices_hash (content_hash),
  CONSTRAINT fk_notice_site FOREIGN KEY (site_id) REFERENCES sites (id),
  CONSTRAINT fk_notice_run FOREIGN KEY (crawl_run_id) REFERENCES crawl_runs (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS extracted_fields (
  id INT AUTO_INCREMENT PRIMARY KEY,
  notice_id INT NOT NULL,
  field_key VARCHAR(30) NOT NULL,
  value_text VARCHAR(255) NULL,
  raw_text TEXT NULL,
  unit VARCHAR(20) NULL,
  amount_yuan DOUBLE NULL,
  event_at DATETIME NULL,
  precision VARCHAR(20) NOT NULL DEFAULT 'missing',
  is_estimated TINYINT(1) NOT NULL DEFAULT 0,
  anchor_score DOUBLE NOT NULL DEFAULT 0,
  format_score DOUBLE NOT NULL DEFAULT 0,
  clarity_score DOUBLE NOT NULL DEFAULT 0,
  confidence DOUBLE NOT NULL DEFAULT 0,
  reason VARCHAR(400) NOT NULL DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'extracted',
  reviewer VARCHAR(160) NULL,
  reviewed_at DATETIME NULL,
  extracted_at DATETIME NOT NULL,
  UNIQUE KEY uq_field_notice_key (notice_id, field_key),
  KEY idx_field_confidence (confidence),
  KEY idx_field_status (status),
  CONSTRAINT fk_field_notice FOREIGN KEY (notice_id) REFERENCES notices (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS deadline_events (
  id INT AUTO_INCREMENT PRIMARY KEY,
  notice_id INT NOT NULL,
  kind VARCHAR(20) NOT NULL DEFAULT 'enroll',
  event_at DATETIME NULL,
  precision VARCHAR(20) NOT NULL DEFAULT 'absolute',
  work_hours_remaining DOUBLE NULL,
  deadline_pressure DOUBLE NULL,
  qualify_gap DOUBLE NULL,
  risk_score DOUBLE NULL,
  risk_level VARCHAR(20) NOT NULL DEFAULT 'unknown',
  note VARCHAR(255) NULL,
  seed_key VARCHAR(160) NULL UNIQUE,
  computed_at DATETIME NOT NULL,
  UNIQUE KEY uq_deadline_notice_kind (notice_id, kind),
  KEY idx_deadline_event_at (event_at),
  KEY idx_deadline_risk (risk_level),
  CONSTRAINT fk_deadline_notice FOREIGN KEY (notice_id) REFERENCES notices (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
