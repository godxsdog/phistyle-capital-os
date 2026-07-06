export type WalletTab = "overview" | "kent" | "wife" | "transferRules" | "purchaseOffers";

export const TAB_LABELS: Record<WalletTab, string> = {
  overview: "總覽",
  kent: "凱章",
  wife: "老婆",
  transferRules: "轉點規則",
  purchaseOffers: "買分價格",
};

export const OWNER_LABELS: Record<string, string> = {
  kent: "凱章",
  wife: "老婆",
};

export const KIND_LABELS = {
  ledger: {
    earn: "獲得",
    buy: "購買",
    transfer_in: "轉入",
    transfer_out: "轉出",
    redeem: "兌換",
    expire: "到期",
    adjustment: "調整",
  } as Record<string, string>,
  programKind: {
    airline: "航空",
    hotel: "飯店",
    bank: "銀行",
    other: "其他",
  } as Record<string, string>,
  offerKind: {
    official: "官方",
    promo: "活動",
    third_party: "第三方手動",
  } as Record<string, string>,
};

export const LEDGER_KIND_OPTIONS = [
  { value: "earn", label: KIND_LABELS.ledger.earn },
  { value: "buy", label: KIND_LABELS.ledger.buy },
  { value: "transfer_in", label: KIND_LABELS.ledger.transfer_in },
  { value: "transfer_out", label: KIND_LABELS.ledger.transfer_out },
  { value: "redeem", label: KIND_LABELS.ledger.redeem },
  { value: "expire", label: KIND_LABELS.ledger.expire },
  { value: "adjustment", label: KIND_LABELS.ledger.adjustment },
];

export const PROGRAM_KIND_OPTIONS = [
  { value: "airline", label: KIND_LABELS.programKind.airline },
  { value: "hotel", label: KIND_LABELS.programKind.hotel },
  { value: "bank", label: KIND_LABELS.programKind.bank },
  { value: "other", label: KIND_LABELS.programKind.other },
];

export const CURRENCY_OPTIONS = ["TWD", "USD", "JPY", "EUR", "GBP", "HKD", "CAD", "AUD", "CNY"];
