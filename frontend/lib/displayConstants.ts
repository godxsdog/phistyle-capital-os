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
  open: "開放",
  used: "已使用",
  expired: "已過期",
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
