"""服务层：业务规则与算法都在这层，controller 只做编排与审计。

模块清单（按依赖顺序）：
- source_catalog   确定性采源目录（6 站点 / 120 条公告正文）
- extraction_engine 算法 1：字段抽取与置信度
- deadline_service  算法 2：截止风险评分
- auth/site/template/notice/field/crawl/report/audit 各业务服务

包内不做聚合导入，避免服务之间循环引用；使用方直接 `from src.services import xxx_service`。
"""
