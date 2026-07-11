# Ticket: Phase PW-6 — 旅程尋票器(Trip Quest)

FABLE-APPROVED: yes (2026-07-10)。已列入 roadmap(本檔核准即
記錄;roadmap 檔案下次維護時補一行,不阻塞)。
OWNER: Codex。VERDICT: new Fable session。
DEPENDS: PW-3 ACCEPTED(已)。PRE-START Sonnet review:本工單
已含完整配對/排名/升格規則,Codex 自查後有未定義行為即 STOP,
不另跑獨立審查(比例原則;此裁量記錄在案)。

## 1-2. WHY / USER VALUE

「TPE↔OKA、Alaska、九十月、四天、來回總哩最少」這類需求,
從逐日手查變成填五欄按一鍵。首個真實用例即上述。

## 3. BINDING DECISIONS

- 輸入:origin, destination, programs(多選), window_start,
  window_end, trip_days N(配對容忍 ±1), cabin, pax,
  direction 固定 round_trip(單程 v1 不做)。
- 抓取:用既有 seats_aero_service 的 cached search,去程
  (origin→dest)與回程(dest→origin)各一次涵蓋整個日期窗;
  同 quest 同日已抓過即重用快照,尊重 Pro 1000 次/日。
- 配對:回程日 ∈ [去程日+N−1, 去程日+N+1];兩段同 program;
  兩段剩餘座位皆 ≥ pax。
- 排名鍵(裁決:稅金幣別可能混雜,不參與排名):
  1) 去+回總哩最小 2) 去程日最早。稅金按段原幣顯示,
  若 fx_rates 有該幣別匯率則附「≈NT$」參考值,無則只顯示原幣。
- 升格(裁決):一個結果 →「兩筆」award_quotes(去、回各一,
  既有單段模型不動),note 互相標注配對來源 quest_result id;
  使用者在 PW-2 各自評估資金來源。
- 結果落庫:trip_quests(查詢參數)+ quest_results(配對明細,
  含兩段日期/各段哩程/總哩/稅原幣/座位數/rank),重跑同參數
  同日 = 冪等重用;跨日重跑 = 新結果集(可用性會變)。
- 可選 DeepSeek 敘事摘要:Phase 15 呼叫模式,失敗靜默省略。

## AMENDMENT r1(Fable 2026-07-10,採 Codex STOP 選項 1)

F1 同一個 migration 內,award_quotes 加 note Text NULL
  (純 additive;禁區條款語義釐清:禁的是重構既有欄位/約束,
  nullable 附加欄比照 Phase 15 先例允許,此釐清適用於未來工單)。
F2 POST /wallet/award-quotes request 與 response 同步加 optional
  note;/wallet/awards 列表顯示 note(有值才顯示,小字)。
  既有呼叫零影響(欄位可選)。
F3 升格寫入 note 格式:「旅程尋票 #<quest_result_id> 去程」/
  「…回程」。

## 5/7. SCOPE + SCHEMA(一個 additive migration,id ≤32)

trip_quests: id PK; origin/destination Text NOT NULL; programs
Text NOT NULL(JSON list); window_start/window_end Date NOT NULL;
trip_days Integer NOT NULL; cabin Text NOT NULL; pax Integer NOT
NULL DEFAULT 1; created_at tstz NOT NULL default now。
quest_results: id PK; trip_quest_id FK CASCADE NOT NULL;
run_date Date NOT NULL; rank Integer NOT NULL; program Text NOT
NULL; outbound_date/return_date Date NOT NULL; outbound_miles/
return_miles/total_miles Numeric(18,0) NOT NULL; outbound_taxes/
return_taxes Text NULL(原幣字串); seats_min Integer NOT NULL;
raw_refs Text NULL; UNIQUE(trip_quest_id, run_date, rank)。
服務:trip_quest_service.py;main.py additive 路由;
/wallet/quests 頁(繁中、手機優先、鏡射 awards 路由模式),
launcher 加 🧭 旅程尋票;升格按鈕呼叫既有 quote 建立端點兩次。

## 6/8. OUT OF SCOPE / 禁區

單程/多城市;Live Search(維持商業限制);自動訂票;
跨 program 混段(去 Alaska 回別家 v1 不做);
禁改 PW-1..5 既有表、決策管線、llm_router。

## 13. ACCEPTANCE

配對手算 fixture:3 去程 × 3 回程、N=4、pax=2,斷言配對集合、
排名順序、座位過濾各一案;冪等(同日重跑 0 新列);
seats.aero 全 mock;升格產生恰好兩筆 quotes 且 note 互鏈;
既有測試全綠不改。

## 14. MANUAL VERIFICATION

真跑 TPE↔OKA / Alaska / 9-10月 / 4天 / 2人,確認第一名總哩
與 seats.aero 網站抽查一致;升格兩筆到 PW-2 各跑一次比價。

## 16. 標準完成報告 + migration 全文。
