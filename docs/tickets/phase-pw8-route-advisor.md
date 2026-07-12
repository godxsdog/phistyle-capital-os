# Ticket: Phase PW-8 — 攻略知識庫 + 目的地里程顧問

FABLE-APPROVED: yes (2026-07-11)。OWNER: Codex。VERDICT: new
Fable session。DEPENDS: 無硬依賴(與 PW-6 r1/PW-7 可並行,
但排在其後)。PRE-START:自查,未定義即 STOP。

## 1-2. WHY / USER VALUE

使用者持有成長中的哩程攻略庫(現 20 份 txt,將達 28+,在
data-rescue/guides/,gitignored 付費內容永不入庫 git)。
目標:輸入目的地(起點預設 TPE)→ 推薦適用的里程計畫與甜點
兌換(哪家計畫、幾哩、艙等、關鍵規則),並引用攻略出處。

## 3. BINDING DECISIONS

- 三層架構(系統既有模式,禁 RAG/向量庫):
  L1 文件庫:import 指令把 guides/*.txt 存入既有
    knowledge_documents(title=檔名去前綴、content 全文、
    source='mileage_guide');冪等 by content hash。休眠的
    Knowledge 層就此啟用,invariant 不變。
  L2 結構化甜點:新表 route_sweet_spots(additive migration,
    id ≤32):id PK; program_id FK RESTRICT NOT NULL;
    origin_tag Text NOT NULL DEFAULT 'TPE'; dest_tag Text NOT
    NULL(機場碼或區域碼); cabin Text NOT NULL; miles_cost
    Numeric(18,0) NULL; tip Text NOT NULL(一句話甜點);
    caveats Text NULL; source_doc_id FK knowledge_documents
    RESTRICT NOT NULL; status Text NOT NULL DEFAULT '未確認'
    ('未確認'|'已確認'|'已否決'); created_at。
    另 dest_regions 小表:airport Text PK; region Text NOT NULL
    (NRT→日本 等,seed 常用 40 個機場,使用者可增修)。
  L3 查詢:/wallet/advisor 頁——輸入目的地機場碼 → 決定論
    匹配「已確認」sweet spots(dest_tag = 機場碼或其 region)
    → 依 miles_cost 排序列出(計畫/艙等/哩數/tip/出處連結);
    下方「AI 綜合建議」(可選):把命中攻略的相關段落餵
    DeepSeek(Phase 15 模式),prompt 明令「僅根據提供文本,
    不得補充外部知識」,輸出標注引用檔名;失敗靜默省略。
- 解析指令(L1→L2):逐檔餵 DeepSeek 嚴格 JSON 萃取候選
  sweet spots(可多筆/檔);全部落地為「未確認」;dry-run
  先列清單。/wallet/advisor 附「待確認」管理區:使用者逐筆
  確認/否決/就地修數字(r3 AI 解析先例,數字過人眼才算數)。
- 新攻略加入流程 = 丟檔進 guides/ → 重跑 import+解析
  (冪等,只處理新檔)→ 確認新記錄。寫進頁面說明。
- launcher 加 🗺 里程顧問。

## AMENDMENT r1(Fable 2026-07-12,採 STOP 選項 1 + 補齊資料)

G1 Knowledge 映射(不改 knowledge_documents schema):
  source_type='import';tags 含 'mileage_guide' 與
  'sha256:<內容雜湊>'(冪等鍵);file_path=原始檔名;
  title=檔名去時間戳前綴。
G2 狀態機(BINDING):未確認 → 已確認|已否決;
  已確認 → 已否決(甜點貶值退役用);已否決=終態不可逆。
  僅「未確認」可編輯欄位;要改已確認的數字 = 否決舊筆、
  另建新筆(手動或重解析),保留審計軌跡。service 層強制。
G3 dest_regions seed(BINDING,以下列清單為準、全數 seed,
  不另綁數量;r2 修正:原「48 筆」為計數錯誤,實為 54):
  日本:NRT HND KIX ITM NGO FUK CTS OKA
  韓國:ICN GMP PUS
  港澳中:HKG MFM PVG PEK CAN
  東南亞:SIN BKK KUL CGK MNL SGN HAN DAD
  南亞/島嶼:MLE DEL BOM CMB
  歐洲:LHR CDG FRA AMS ZRH IST MXP FCO MAD VIE MUC
  北美:LAX SFO SEA JFK ORD BOS YVR HNL
  澳紐:SYD MEL BNE AKL
  中東:DXB DOH AUH
  region 值用上列中文組名;seed 進 migration(參照資料屬
  additive 例外,先例:Phase 17 內建商品)。
G4 roadmap 條目:工單核准即生效,roadmap 檔下次維護補一行,
  不阻塞(沿 PW-6 先例)。

## 6/8. OUT OF SCOPE / 禁區

向量庫/embedding;自動確認;爬攻略來源網站;起點多選
(v0 固定 TPE,欄位留 origin_tag 供未來);
禁改決策管線/交易表/llm_router 既有邏輯(DeepSeekProvider
照 Phase 15 模式使用)。

## 13. ACCEPTANCE

import 冪等(重跑 0 新增);解析 mock LLM,含格式錯誤 fallback;
匹配:機場碼直中與 region 間接命中各一案、未確認不入結果;
確認/否決狀態單向測試;既有測試全綠。

## 14. MANUAL VERIFICATION

真跑 import+解析 20 檔,抽 3 筆對照原文確認數字;
查 NRT,確認推薦含 ANA/長榮/國泰等攻略對應計畫且出處正確。

## 16. 標準完成報告 + migration 全文。
