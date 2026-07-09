# Ticket: Phase PW-5 — 飯店兌換比較器(G3)

FABLE-APPROVED: yes (2026-07-09)。規格上位:
docs/strategy/points-workflows-analysis.md(Marriott 飯店流程
Step 1-6)。動機:三張 50K FNC 於 2026-08-28 到期,使用者需要
在到期前用比較器決定怎麼燒。
PRE-START: Sonnet clarity review 必跑。OWNER: Codex。
VERDICT: new Fable session。DEPENDS: PW-4 ACCEPTED(已)。

## 1-2. WHY / USER VALUE

同一晚住宿,輸入現金價與點數價,系統排比四種支付方式的真實
成本:A 現金 / B 純點數(以使用者 lot 實際成本計價,無 lot 部分
標「無成本基礎」)/ C 免房券(列出可用的 active 券,含到期日,
優先建議快到期者)/ D 券+補點(使用者輸入補點上限與所需補點)。
v0 是「誠實比較器」不是神諭:每個選項給數字與注記,排序供參,
決定權在人。

## 3. BINDING DECISIONS

- 新表 hotel_stay_quotes(一個 additive migration,id ≤32):
  id PK; hotel_name Text NOT NULL; stay_date Date NOT NULL; nights
  Integer NOT NULL DEFAULT 1; program_id FK RESTRICT NOT NULL;
  cash_price_twd Numeric(18,2) NOT NULL; points_price Numeric(18,0)
  NOT NULL(每晚點數價×晚數的總價);taxes_note Text NULL;
  topup_allowed Boolean NOT NULL DEFAULT false; topup_points
  Numeric(18,0) NULL; created_at tstz NOT NULL default now。
- 評估(唯讀,不動 lots/vouchers,與 PW-2 同紀律):
  A 現金 = cash_price_twd。
  B 純點數 = points_price × 該 owner 該 program 的 lot 加權平均
    每點成本(FIFO 模擬);餘額不足 → 選項標「點數不足」不參與
    排名;無 lot 成本部分以 0 計並標注。
  C 券:列出該 program 的 active 券中 face_value_points ≥
    points_price 者;成本顯示 = 0 現金支出,注記「消耗面額
    {face}K 券(到期 {date})」;多張可用時建議最早到期。
  D 券+補點:topup_allowed 且 points_price − face ≤ topup_points
    時成立;成本 = 補點數 × lot 每點成本,注記同 C。
  另附每晚每點價值 = cash_price / points_price(cpp,供人判斷
  「這次兌換值不值」,對照使用者自己的估值)。
- 比較結果不落庫(v0 即算即顯,quote 本身落庫可重算);
  「標記已用某券」沿用 PW-4 的 used 流程,不在本 phase 自動化。
- 機會成本(G4 的住宿價值基準)不做,注記欄提示使用者自行心算。
- UI:/wallet 新分頁「🏨 住宿比價」(或 /wallet/hotels),
  全繁中、手機優先、quote 表單+四選項卡片排比、最划算者加冠。
  launcher 不用改(錢包內分頁)。

VERDICT: ACCEPTED (Fable, 2026-07-09; commit c0fc2d4). Migration
0017 approved. VERIFIED after deploy + 0017 + user runs the two
manual cases (one-night FNC=NT$0; two-night = 券+10,000)。

## AMENDMENT r1(Fable 2026-07-09,Sonnet review 後;優先於原文)

E1 owner:hotel_stay_quotes 加 owner Text NOT NULL(住宿是
  個人訂的,不做雙 owner 枚舉);B/C/D 全部以該 owner 的帳戶
  與券計算。
E2 points_price 改語義為「每晚點數價」(欄名 points_price_
  per_night Numeric(18,0) NOT NULL);總點數 = 每晚 × nights。
E3 FNC 一晚一張(Marriott 真實規則):C = 用 face ≥ 每晚點數價
  的 active 券逐晚覆蓋,最早到期優先,可用券數 < nights 時,
  其餘晚數以 B 邏輯計價並注記「{n} 晚用券 + {m} 晚點數」。
  D = 對 face < 每晚價的券,若 topup_allowed 且每晚缺口 ≤
  topup_points,該晚成本 = 缺口 × lot 每點成本;券選序:最早
  到期優先,同日到期取缺口最小。
E4 B 的兩種情況分開:balance < 總點數 →「點數不足」不進排名;
  balance 足但 lots 不足額(simulate_fifo partial)→ 進排名,
  未覆蓋部分以 0 計並標「部分無成本基礎」。
E5 UI 定案:獨立路由 /wallet/hotels(鏡射 /wallet/awards 模式,
  不動 WalletTab/constants),launcher 加 🏨 住宿比價。
E6 驗收 fixture 補 nights=2 案例:兩晚每晚 50K、一張 50K 券、
  lot 0.2/點 → C = 一晚券 + 一晚 10,000 TWD,斷言到分。

## 5-8. SCOPE / 禁區

改動:point_wallet_service(或新 hotel_compare_service)、
main.py additive、/wallet 前端、一個 migration、測試。
禁改:PW-1..4 既有表、award_cost_engine、決策管線、交易表、
llm_router。零 LLM。

## 13. ACCEPTANCE

手算 fixture:同一晚 cash 12,000 / points 50,000 / lot 成本
0.2/點 / 一張 50K 券 → A=12000、B=10000、C=0+注記、cpp=0.24,
斷言到分;點數不足與 topup 邊界(恰好等於/超過上限)各一測;
唯讀證明;既有測試全綠不改。

## 14. MANUAL VERIFICATION

輸入你真實考慮的一晚(例如日本行的 Marriott),確認四選項
數字與你手算一致,券的建議是最早到期那張。

## 16. 標準完成報告 + migration 全文。
