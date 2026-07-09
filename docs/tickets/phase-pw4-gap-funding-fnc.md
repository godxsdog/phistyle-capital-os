# Ticket: Phase PW-4 — 缺口式資金 + 免房券資產(G1+G2)

FABLE-APPROVED: yes (2026-07-09)。規格上位:
docs/strategy/points-workflows-analysis.md(G1/G2 節)。
PRE-START: fresh-context Sonnet clarity review 必跑,BLOCKER 回
Fable session。OWNER: Codex。VERDICT: new Fable session。
DEPENDS: PW-2 ACCEPTED(已)。

## 1-2. WHY / USER VALUE

使用者的真實主路徑是「既有 18,911 + 只補缺口 6,089」,而 PW-2
引擎的純粹方法把它排除了(v0 已知限制)。另外三張 2026-08-28
到期的 50K 免房券(FNC)系統完全看不見。本 phase 補齊兩者。

## 3. BINDING DECISIONS

G1 缺口式混合資金(gap funding):
- 新方法 method="gap_fill":對每個 (owner, 目標計畫帳戶),
  若 0 < 既有餘額 < 需求,計算缺口 = 需求 − 既有餘額,然後對
  「缺口」枚舉 PW-2 全部既有方法(轉點鏈/買分/現買現轉),
  情境成本 = 既有部分(lots FIFO 模擬,無 lot 部分成本 0 並標
  「部分無成本基礎」)+ 缺口補足最優解。
- 混搭邊界不變:缺口本身仍走單一補足路徑(不做缺口再拆多源);
  跨 owner 仍禁止。path_json 記兩段(existing + fill)。
- 引擎仍絕對唯讀;funding_scenarios.method 枚舉加 'gap_fill',
  無 schema 變更(method 是 Text)。
G2 FNC 免房券資產:
- 新表 hotel_vouchers(一個 additive migration,id ≤32):
  id PK; owner Text NOT NULL; program_id FK RESTRICT NOT NULL;
  face_value_points Numeric(18,0) NOT NULL(如 50000);
  expires_at Date NOT NULL; status Text NOT NULL DEFAULT 'active'
  (active|used|expired);acquired_note Text NULL;used_note Text
  NULL;created_at tstz NOT NULL default now。
- CRUD 端點+錢包「我的點數」頁新增 FNC 區塊(繁中):張數、
  面額、到期倒數,≤90 天紅色警示;到期掃描指令(掛既有
  tick/expiry 模式)把 FNC 到期納入 expiry_alerts(FK 對不上
  accounts → expiry_alerts 需要可空 account_id 或新欄?
  裁決:expiry_alerts 加 nullable voucher_id FK(同 migration,
  additive),account_id 改為 NULL 允許——若此變更超出 additive
  (改既有欄 nullability)= 允許的例外,ALTER COLUMN DROP NOT
  NULL 屬低風險,migration 中明確註記。
- 標記 used:寫 used_note,狀態單向 active→used|expired,
  不可逆轉(終局狀態精神,invariant 3 同源)。
- v0 不做「FNC+補點住宿比較器」(那是 G3,另一張票);
  本 phase 只讓 FNC 被看見、被提醒、被記錄。

VERDICT: ACCEPTED (Fable, 2026-07-09; commit a0a4cc9). Migration
0016_pw4_vouchers approved (D1 verbatim incl. noted ALTER exception).
VERIFIED after deploy + 0016 + user enters 3 real 50K FNCs + one
gap_fill evaluation.

## AMENDMENT r1(Fable 2026-07-09,Sonnet review 後裁決)

D1 expiry_alerts 約束:account_id 改 NULL 允許並加 voucher_id
  FK NULL 之外,再加:(a) 新 UNIQUE(voucher_id, threshold_days,
  expires_at, checked_on);(b) CHECK 恰一非空
  ((account_id IS NULL) != (voucher_id IS NULL))。既有 UNIQUE
  保留(仍負責帳戶列去重)。全部同一 migration。
D2 scan_expiry_alerts 重構(明確規格):在既有帳戶迴圈後新增
  voucher 迴圈——查 active 且未過期 vouchers,同四門檻,去重
  查詢以 voucher_id 為鍵,訊息格式:「🏨 {owner} 的
  {program} 免房券({face_value_points//1000}K)將於 {days} 天後
  到期」。過期者順帶 status→expired。
D3 hotel program 列:不 seed。Marriott/Hilton 等 program 列已由
  legacy 匯入存在(34 帳戶佐證);FNC 建立表單用既有 program
  下拉,缺的計畫使用者以既有「新增計畫」UI 自建。kind 欄不修。
D4 status 單向性:service 層強制(invariant 8 模式,比照
  Phase 14 guard 寫法),違規 raise → API 409。

## 5-8. SCOPE / 禁區

改動:award_cost_engine(gap_fill)、point_wallet_service(FNC
CRUD)、expiry 掃描、main.py additive、/wallet 頁 FNC 區塊、
launcher 不變(在既有錢包內)。禁改:PW-1/2/3 既有表結構
(除上述 expiry_alerts 例外)、決策管線、交易表、llm_router。

## 13. ACCEPTANCE

gap_fill 手算 fixture:既有 18,911 + 缺 6,089 經 35:1 轉點,
總成本斷言到分;既有=0 或 ≥需求時 gap_fill 不出現(退回純方
法);唯讀證明(evaluate 前後 lots/vouchers 不變)。FNC:CRUD、
到期掃描 90/60/30/7、status 單向性測試。既有測試全綠不改。

## 14. MANUAL VERIFICATION

輸入三張真實 50K FNC(2026-08-28 到期)→ 錢包看到紅色倒數;
用一筆真實換票需求跑比價,確認出現 gap_fill 情境且數學對。

## 16. 標準完成報告 + migration 全文。
