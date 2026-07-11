# Ticket: Phase PW-7 — 多段同日接駁尋票(2-3 段)

FABLE-APPROVED: yes (2026-07-10)。OWNER: Codex。
VERDICT: new Fable session。DEPENDS: PW-6 ACCEPTED + 本輪 r1 bug
修正完成。PRE-START:Codex 自查,未定義行為即 STOP。

## 1-2. WHY / USER VALUE

「TPE-SIN + SIN-MLE 同一天、同計畫(如 UA)、每段都 ≥2 商務
座」——長程獎勵票的真實玩法是分段接駁。輸入 2-3 段航段,
系統找出所有「全部段同日可接」的日期並排名。

## 3. BINDING DECISIONS

- 輸入:segments 有序清單(2-3 段,每段 origin/destination)、
  programs 多選、日期窗、cabin、pax。所有段必須同一日期。
- 可接定義(v0 誠實簡化,UI 標注):同日即視為可接,
  「實際轉機時間與機場請自行確認」;不做時刻表銜接判斷
  (cached search 無可靠航班時刻)。
- 每段取價規則(與 r1 bug 修正同源,BINDING):在指定 cabin
  下,取「剩餘座位 ≥ pax 的最便宜 bucket」;哩程成本與座位數
  必須來自同一 bucket,禁止混桶。
- 排名:全段總哩最小 → 日期最早。稅金各段原幣顯示不參與排名
  (沿用 PW-6 裁決)。
- 落庫(一個 additive migration,id ≤32):trip_quests 加
  kind Text NOT NULL DEFAULT 'round_trip'('round_trip'|
  'chain')與 segments_json Text NULL;quest_results 加
  segments_json Text NULL(每段 date/miles/taxes/seats 明細,
  chain 模式下 outbound_*/return_* 欄填首段/末段值以相容既有
  顯示)。附加欄先例(F1 釐清)適用。
- UI:/wallet/quests 加模式切換「來回|多段同日」,多段模式
  顯示動態航段列(2-3 段,+/−按鈕),結果卡逐段展開。
- 升格:chain 結果 → 每段一筆 award_quote,note 標
  「多段尋票 #<id> 第n段」。

## 6/8. OUT OF SCOPE / 禁區

>3 段;跨日轉機;混計畫接駁;時刻表;Live Search;
禁改決策管線/交易表/llm_router。

## 13. ACCEPTANCE

手算 fixture:兩段 × 5 天窗、部分日期缺段,斷言僅全段可接日
入榜、排名正確、座位過濾(pax=2 踢掉 1 座桶);同日冪等;
mock 全部 seats.aero;既有 round_trip 測試全綠不改。

## 14. MANUAL VERIFICATION

真跑 TPE-SIN + SIN-MLE / UA / 11月窗 / 商務 / 2人,與
seats.aero 網站抽查一日。

## 16. 標準完成報告 + migration 全文。
