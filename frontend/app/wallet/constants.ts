export type WalletTab = "overview" | "wanlitong" | "marriott" | "juneyao" | "otherSources" | "points";

export const TAB_LABELS: Record<WalletTab, string> = {
  overview: "總覽",
  wanlitong: "萬里通",
  marriott: "萬豪",
  juneyao: "吉祥",
  otherSources: "其他來源",
  points: "我的點數",
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

export const QUEST_PROGRAM_CODES = [
  { code: "AS", label: "阿拉斯加航空", aliases: ["Alaska", "Mileage Plan"] },
  { code: "UA", label: "聯合航空", aliases: ["United", "MileagePlus"] },
  { code: "AC", label: "加拿大航空 Aeroplan", aliases: ["Aeroplan", "Air Canada", "加拿大航空"] },
  { code: "NH", label: "全日空 ANA", aliases: ["ANA", "All Nippon", "全日空"] },
  { code: "BA", label: "英國航空 Avios", aliases: ["British Airways", "BA Avios", "英航"] },
  { code: "QR", label: "卡達航空", aliases: ["Qatar", "卡達", "卡塔爾"] },
  { code: "JL", label: "日本航空", aliases: ["JAL", "Japan Airlines", "日航"] },
  { code: "CX", label: "亞洲萬里通", aliases: ["Cathay", "Asia Miles", "國泰", "亞萬"] },
  { code: "BR", label: "長榮航空", aliases: ["EVA", "長榮"] },
  { code: "CI", label: "中華航空", aliases: ["China Airlines", "華航"] },
  { code: "SQ", label: "新加坡航空", aliases: ["Singapore Airlines", "KrisFlyer", "新航"] },
  { code: "TK", label: "土耳其航空", aliases: ["Turkish Airlines", "Miles&Smiles", "土航"] },
  { code: "EK", label: "阿聯酋航空", aliases: ["Emirates", "阿聯酋"] },
  { code: "EY", label: "阿提哈德航空", aliases: ["Etihad", "阿提哈德"] },
  { code: "QF", label: "澳洲航空", aliases: ["Qantas", "澳航"] },
  { code: "AF", label: "Flying Blue", aliases: ["Flying Blue", "Air France", "法航"] },
  { code: "AY", label: "芬蘭航空", aliases: ["Finnair", "芬蘭"] },
  { code: "LA", label: "LATAM 航空", aliases: ["LATAM"] },
  { code: "AV", label: "LifeMiles", aliases: ["LifeMiles", "Avianca"] },
  { code: "VN", label: "越南航空", aliases: ["Vietnam Airlines", "越南航空"] },
  { code: "AK", label: "亞洲航空", aliases: ["AirAsia", "亞洲航空", "亞航"] },
  { code: "攜程", label: "攜程", aliases: ["攜程", "携程", "Ctrip", "Trip.com"] },
  { code: "飛豬", label: "飛豬", aliases: ["飛豬", "飞猪", "Fliggy"] },
  { code: "雅高", label: "雅高心悅界", aliases: ["Accor", "ALL", "雅高"] },
  { code: "香格里", label: "香格里拉會", aliases: ["Shangri-La", "Shangri La", "香格里"] },
  { code: "溫德姆", label: "溫德姆獎賞", aliases: ["Wyndham", "溫德姆"] },
] as const;
