# bidsift · 招投标公告采集、字段抽取与截止日历台

> 把 6 个公共资源交易中心每天滚进来的招标公告，自动抽成结构化字段、按工作日历排出截止风险，并导出「本周必投名单」。

## 1. 真实场景

**模拟客户**：中鼎工程咨询有限公司 · 投标情报组（12 人），服务 5 家建筑工程客户。

**现有工作流**：情报专员每天盯 6 个公共资源交易中心 + 3 个省招标网，日均 300+ 条公告；
逐条打开页面，把「项目名称 / 预算金额 / 报名截止时间 / 开标地点」抄进 Excel，再手工排截止日历。

**三个痛点**

1. 站点结构各异，XPath 模板一改就废，改完还得回补历史数据；
2. 公告正文与「PDF 转 HTML」附件里字段散落，金额单位混乱（万元 / 元 / 约 / ￥），截止时间常写成「报名截止后 3 个工作日」；
3. 截止临近无人提醒，错过报名窗口——一次漏投的代价是一整条标段的营收。

**上下游**：上游是交易中心公告页与附件 → 本系统替代「人工抄录 + Excel 日历」 →
下游是客户 BD 按日历排标、项目经理取字段填标书、组长按周导出必投名单。

## 2. 角色与权限

| 角色 | 账号 | 能做什么 | 不能做什么（后端真实 403） |
|---|---|---|---|
| `admin` 情报组长 | `admin@bidsift.io` | 采源配置、模板发布、跑采集批次、复核字段、重算风险、导出全量 CSV、看审计日志 | — |
| `analyst` 情报专员 | `analyst@bidsift.io` | 跑采集批次、复核/修正字段、新建模板草稿、重算风险、导出 CSV | 改采源配置（403）、发布模板（403）、看审计日志（403） |
| `client` 客户 BD | `client@bidsift.io` | 只读公告登记簿 / 公告详情 / 截止日历，导出**本行业**必投名单 | 跑采集（403）、复核字段（403）、复核队列与漏抽报表（403）、重算风险（403）、改采源（403） |

密码统一 `Demo@2026`（`client@bidsift.io` 的行业为「市政」，导出时只含市政类公告）。

## 3. 主要功能

1. **公告登记簿**：6 采源筛选、区域/分类筛选、低置信标记、风险章、分页；一键「跑采集批次」。
2. **公告卷宗详情**：清洗后正文逐行展示并标出锚点命中行；右侧 4 个字段的「原文 → 归一值 → 三段分母 → 置信度」核对卡，支持人工修正 / 通过 / 驳回。
3. **采源与模板治理**：站点列表（频率、限流、状态、低置信数）、模板版本表、两个版本之间的锚点/正则差异对比、草稿发布。
4. **截止日历**：周视图 7 列排期 + 本周必投名单 + 风险分布 + 算法口径说明；按基准时刻重算。
5. **复核队列 / 漏抽报表**：低置信字段按分数升序排队；站点 × 字段的缺失率与平均置信度矩阵。
6. **审计日志**（admin）：登录、采集、复核、导出、模板发布全部留痕。

## 4. 两个真算算法

### 算法 1：字段抽取与置信度（`backend/src/services/extraction_engine.py`）

- 输入：公告清洗正文 + 站点生效模板的锚点词/正则；输出 `{field, value, raw, confidence, reason}`。
- 规则集覆盖 4 个字段：项目名称 / 预算金额 / 报名截止时间 / 开标地点。
- 上下文锚点：取锚点词后**同一行**最近邻（≤80 字），避免串到下一行的「开标时间」。
- 单位归一：亿元 / 万元 / 元 → `amount_yuan`；`约/暂定/估算` → 明确性 0.55，`不超过/最高限价` → 0.70。
- 日期归一：绝对日期（含「12月3日上午9点半」这类缺年份写法，按公告年份补全）、相对日期
  （「报名截止后 N 个工作日」按公告日 + N 个工作日推算并标记 `relative`）、占位话术（另行通知 / 见公告）。
- **置信度 = 0.35 × 锚点距离分 + 0.35 × 格式匹配分 + 0.30 × 单位/日期明确性分**，
  锚点距离分 = `1 − 距离/80`；`< 0.55` 进复核队列。同一正文重复抽取结果逐字段一致（纯函数，无随机）。

### 算法 2：截止风险评分（`backend/src/services/deadline_service.py`）

- 剩余工作时长 `h`：工作日 09:00–18:00，剔除周末与 2026 年法定节假日（简化表）。
- `deadline_pressure = clamp(1 − h / 72, 0, 1)`。
- `qualify_gap`：本公司工程咨询乙级（二级）→ 无/二级 0.0、一级 0.45、特级 0.85。
- `risk_score = 100 × (0.62 × deadline_pressure + 0.38 × (1 − qualify_gap))`。
- 分档：`gap ≥ 0.5 → skip`；`pressure ≥ 0.45 → must_act`；`0.15 ≤ pressure < 0.45 → watch`；
  `pressure < 0.15 → skip`；日期缺失 → `unknown`（不参与分档，等人工补全）。
- 评估基准时刻可传 `as_of`（默认演示基准 `2026-11-12 09:00`），保证可复现。

## 5. 快速启动

```bash
cd batch-20261112/projects/gb-567
cp .env.example .env
docker compose up -d --build          # 5 服务：frontend/backend/worker/db/redis
# 等 5/5 healthy（首次镜像构建约 2-4 分钟）
curl -s http://localhost:19240/api/health
# 手动再跑一次 seed（可选，幂等）：
docker compose exec backend python -m scripts.seed_demo
```

访问：`http://localhost:18240`（前端）· `http://localhost:19240/api/health`（后端健康检查）·
MySQL 映射 `127.0.0.1:17740`。

`SEED_DEMO=true` 时 backend 启动会自动执行一次幂等 seed，并在日志打印：

```
SEED_SUMMARY brand=bidsift sites=6 notices=120 fields=480 deadlines=18 users=3
```

## 6. 本地开发

```bash
# 后端
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
SEED_DEMO=false uvicorn src.main:app --reload --port 8000
# 前端（代理到 19240）
cd frontend && npm install && npm run dev
```

## 7. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18.3 + TypeScript 5.6 + Vite 5 + react-router 6（无 UI 框架，自绘 SVG/CSS 图表） |
| 后端 | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic 2 |
| 异步 | Celery 5.4（beat 心跳 / 单站采集 / 全站巡检 / 截止风险重算） |
| 数据库 | MySQL 8.0（utf8mb4） |
| 缓存/队列 | Redis 7 |
| 容器 | Docker Compose，5 服务全部 healthcheck，命名卷持久化 |

## 8. 目录结构

```
gb-567/
├── docker-compose.yml        # 5 服务、healthcheck、命名卷
├── .env / .env.example
├── backend/
│   ├── Dockerfile  requirements.txt
│   ├── migrations/0001_initial.sql
│   ├── scripts/seed_demo.py        # 幂等 seed（自然键 upsert）
│   └── src/
│       ├── config/   # settings / database / celery_app / app
│       ├── constants/# enums / roles / error_codes / limits / fieldspec
│       ├── models/   # 6 实体 + User + AuditLog
│       ├── schemas/  # 请求体校验
│       ├── services/ # 业务 + 两个算法 + source_catalog
│       ├── controllers/
│       ├── routes/   # /api/...
│       ├── middlewares/ # JWT / RBAC / 审计 / 限流 / 全局错误
│       └── utils/
└── frontend/
    └── src/{api,stores,types,components/common,components/layout,hooks,pages,router,utils,constants,styles}
```

## 9. 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `bidsift` | 容器名前缀 |
| `FRONTEND_PORT` / `BACKEND_PORT` / `DB_PORT` | `18240` / `19240` / `17740` | 题目分配端口 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_ROOT_PASSWORD` | `bidsift*` | MySQL 初始化 |
| `JWT_SECRET` | 演示用 | JWT 签名密钥 |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker + 限流计数 |
| `SEED_DEMO` | `true` | 启动自动幂等 seed |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_CRAWL_PER_MINUTE` | `240` / `20` | 限流窗口 |

## 10. 共享枚举出现位置

同一组枚举在前后端各定义一份，改一处必须同步另一处：

| 枚举 | 后端 | 前端 |
|---|---|---|
| `Role` | `backend/src/constants/enums.py`、`roles.py` | `frontend/src/types/models.ts`、`constants/roles.ts` |
| `SiteStatus` | `enums.py` | `types/models.ts`、`constants/enums.ts`(`SITE_STATUS_LABEL`) |
| `RunStatus` | `enums.py` | 同上（`RUN_STATUS_LABEL`） |
| `NoticeStatus` | `enums.py` | 同上（`NOTICE_STATUS_LABEL`） |
| `FieldKey` / `FieldStatus` | `enums.py` / `fieldspec.py` | `types/models.ts`、`constants/enums.ts` |
| `DeadlineKind` / `RiskLevel` | `enums.py` / `fieldspec.py` | 同上（`DEADLINE_KIND_LABEL` / `RISK_LABEL`） |
| `QualLevel` | `enums.py` + `fieldspec.QUALIFY_GAP` | `constants/enums.ts`(`QUAL_LABEL`) |
| `TemplateStatus` | `enums.py` | `constants/enums.ts` |

## 11. Docker 说明

- 恰好 5 服务；`docker-compose.yml` 顶层 `name: bidsift`，无 `version:`；
- 依赖顺序：`db`/`redis` healthy → `backend` → `worker`/`frontend`；
- 健康检查：db `mysqladmin ping`、redis `redis-cli ping`、backend `/api/health`、
  worker 心跳（Redis `bidsift:worker:heartbeat`）+ Celery ping 双判据、frontend `wget /`；
- 命名卷：`db_data`（MySQL 数据）、`redis_data`（AOF）。

## 12. 演示账号

| 邮箱 | 密码 | 角色 |
|---|---|---|
| `admin@bidsift.io` | `Demo@2026` | 情报组长 |
| `analyst@bidsift.io` | `Demo@2026` | 情报专员 |
| `client@bidsift.io` | `Demo@2026` | 客户 BD（只读，行业=市政） |

## 13. 验收口径（seed 后）

- 6 采源 / 3 个模板版本 / 120 条公告（2 条为「PDF 转 HTML」附件正文）/ 480 个抽取字段（其中 37 个低置信）/
  18 个截止事件（必投 8 / 观察 5 / 放弃 4 / 待补 1，按演示基准时刻计算）。

## 14. License

演示项目，仅用于工程能力评审；seed 数据为程序生成的合成数据，不含任何真实公告。
