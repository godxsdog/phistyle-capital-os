export const STATUS_LABELS: Record<string, string> = {
  submitted: "已提交",
  triaged: "已分流",
  brain_reviewed: "已完成 Brain 審查",
  human_approved: "人工已核准",
  approved: "已核准",
  rejected: "已拒絕",
  archived: "已封存",
  active: "啟用",
  inactive: "停用",
  success: "成功",
  failed: "失敗",
  pending: "待處理",
  completed: "已完成",
  proposed: "待人工審查",
  open: "開放",
  used: "已使用",
  expired: "已過期",
  resolved: "已處理",
  success_with_warnings: "成功但有警告",
  correction_detected: "偵測到修正",
  quality_warning: "品質警告",
};

export const RISK_LABELS: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
};

export const MARKET_LABELS: Record<string, string> = {
  taifex: "台指期",
  us: "美股",
};

export const DIRECTION_LABELS: Record<string, string> = {
  long: "做多",
  short: "做空",
};

export const SCOPE_LABELS: Record<string, string> = {
  investment: "投資",
  trade_plan: "交易計畫",
};

export const REVIEW_DECISION_LABELS: Record<string, string> = {
  approve: "核准",
  reject: "拒絕",
};

export const RECOMMENDATION_LABELS: Record<string, string> = {
  approve: "建議核准",
  reject: "建議拒絕",
  request_changes: "建議修改",
  escalate_to_fable: "升級 Brain",
};

export const SOURCE_LABELS: Record<string, string> = {
  schwab: "Schwab",
  taifex: "TAIFEX",
  yahoo: "Yahoo",
  taifex_institutional: "三大法人",
};

export function labelFor(map: Record<string, string>, value: string | null | undefined, fallback = "未設定"): string {
  if (!value) return fallback;
  return map[value] || value;
}

export function formatDateZh(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}/${month}/${day}`;
}

export function formatDateTimeZh(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${year}/${month}/${day} ${hour}:${minute}`;
}

export function formatMoneyTwd(value: string | number | null | undefined): string {
  const numberValue = Number(value || 0);
  return `NT$${numberValue.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}`;
}

export function formatDecimal(value: string | number | null | undefined, digits = 2): string {
  return Number(value || 0).toLocaleString("zh-TW", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}
