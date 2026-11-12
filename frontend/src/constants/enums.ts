/** 前端共享枚举（后端 src/constants/enums.py 对应同一组值）。 */
import type {
  DeadlineKind,
  FieldKey,
  FieldStatus,
  NoticeStatus,
  RiskLevel,
  RunStatus,
  SiteStatus,
  TemplateStatus,
} from '../types/models';

export const SITE_STATUS_LABEL: Record<SiteStatus, string> = {
  active: '采集中',
  degraded: '已降级',
  paused: '已暂停',
};

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  running: '执行中',
  success: '成功',
  partial: '部分成功',
  failed: '失败',
};

export const NOTICE_STATUS_LABEL: Record<NoticeStatus, string> = {
  new: '新入库',
  tracking: '跟踪中',
  reviewing: '复核中',
  archived: '已归档',
};

export const FIELD_LABEL: Record<FieldKey, string> = {
  project_name: '项目名称',
  budget_amount: '预算金额',
  deadline: '报名截止时间',
  opening_place: '开标地点',
};

export const FIELD_STATUS_LABEL: Record<FieldStatus, string> = {
  extracted: '待复核',
  verified: '已通过',
  corrected: '已修正',
  rejected: '已驳回',
};

export const RISK_LABEL: Record<RiskLevel, string> = {
  must_act: '本周必投',
  watch: '观察',
  skip: '放弃',
  unknown: '待补日期',
};

export const DEADLINE_KIND_LABEL: Record<DeadlineKind, string> = {
  enroll: '报名截止',
  bid_open: '开标',
  qa: '答疑截止',
};

export const TEMPLATE_STATUS_LABEL: Record<TemplateStatus, string> = {
  draft: '草稿',
  active: '生效中',
  archived: '已归档',
};

export const QUAL_LABEL: Record<string, string> = {
  none: '无特殊资质',
  grade_2: '乙级（二级）',
  grade_1: '甲级（一级）',
  grade_special: '综合（特级）',
};

export const CATEGORIES = [
  '市政道路',
  '桥梁隧道',
  '园林绿化',
  '房建总包',
  '装饰装修',
  '水利工程',
  '环保治理',
  '智慧城市',
];

export const REGIONS = ['华南', '华东', '华北', '西南', '西北'];

/** 算法 1 口径说明（与后端 constants/fieldspec.py 一致，仅用于展示） */
export const CONFIDENCE_FORMULA = [
  { key: 'anchor', label: '锚点距离分', weight: 0.35, hint: '1 − 锚点到值起点的字符数 / 80' },
  { key: 'format', label: '格式匹配分', weight: 0.35, hint: '金额需「数字 + 单位」；日期分绝对/相对/占位' },
  { key: 'clarity', label: '单位/日期明确性', weight: 0.3, hint: '约/暂定/占位话术会拉低明确性' },
];

export const LOW_CONFIDENCE_THRESHOLD = 0.55;
