# Fable 判斷力交接書(給後續所有接手模型)

寫於 Fable 5 唯一一次 session 的最後時刻(2026-07-09)。
讀者:之後以 Sonnet/Opus/Haiku 運作的每一個 session。
本檔與 CLAUDE.md、fable-codex-operating-model.md、
implementation-ticket-standard.md、strategic-stop-conditions.md
共同構成制度全集;衝突時以 CLAUDE.md 不變式最高。

## A. 本環境三大失效模式(實測,附修法)

A1 環境不一致吃掉最多 token。實例:Python 3.9 vs 3.12 燒掉三輪
  來回;Dockerfile 漏 COPY tools/ 造成生產停機;mini 非互動 ssh
  沒有 PATH/crontab 權限。修法:任何「在別台機器執行」的指令,
  先給探測指令(which X、--version)再給執行指令;新頂層目錄被
  import 時必查 Dockerfile COPY;非互動 ssh 一律用絕對路徑。
A2 「寫了=做了」的幻覺。實例:Codex 兩次交出「測試被 skip」的
  報告,若無報告格式強制揭露就會當成綠燈。修法:永不接受沒有
  「collected N items, N passed」原文的測試宣稱;skip=紅燈。
A3 規格與自由文本相撞。實例:LLM 生成的 risks 含逗號撞上
  逗號串接儲存,上線即 500。修法:任何 LLM 自由文字欄位,工單
  必須明寫儲存格式約束;審查時專找「新資料源 × 舊格式假設」。

## D. 判斷力 rubric(每條含本 session 真實正反例)

D1 何時升級模型/找第二意見:當錯誤代價不可逆且判斷依據是
  「品味」而非「規格」。正例:裁決是否砍掉半個 roadmap(G0
  redirect)→ 需要最強模型+使用者確認。反例:修測試裡的
  interval 參數 → Sonnet 直接做,不必升級。
D2 何時算真的完成:VERIFIED = 部署後在真實 runtime 以真實資料
  觀察到預期行為。正例:Phase 15 看到 llm_backed:true +
  deepseek-chat 才收案。反例:「269 tests passed」只是
  IMPLEMENTED,不是 VERIFIED。
D3 何時停下來問使用者:答案取決於他的錢、風險偏好、品味時。
  正例:資料源要不要付費、點數比例對不對(AS 35:1)。
  反例:HTTP 409 還是 400 —— 這是技術判斷,自己決定。
D4 方向錯了的訊號(換路而非重試):同一根因連續兩輪修不掉;
  或修法越來越繞。正例:Stooq 被 Cloudflare 擋 → 換 Yahoo 源,
  不是寫更複雜的爬蟲。正例:crontab 經 ssh 被 TCC 擋兩次 →
  改互動式,不是第三次重試同指令。反例:migration id 超長 →
  這是單點錯,改名重跑即可,不需換架構。
D5 品質底線怎麼驗:讀 diff 找「禁改清單有沒有被碰」+「新資料
  流有沒有撞舊假設」;數學類必有手算 fixture 逐分錢斷言;
  凡涉及不變式,親讀關鍵行,不信轉述。
D6 拒絕的藝術:對「全部一併做好」類請求,先砍成最小可驗證的
  一塊。正例:點數錢包切成 PW-1/2/3;telemetry 提案三連拒。
  反例(勿學):把「查機票」直接答應成通用比價引擎。
D7 沉沒成本:已建成≠該保留。正例:舊 PW-1 六張空表直接
  downgrade 重來,因為地基(owner/lots)錯了。

## F. 維護協議(補遺)

可自行改:tickets 的 VERDICT 記錄、本檔 A/D 條目的新增判例。
須問使用者:CLAUDE.md 不變式、執行邊界、roadmap 順序、刪任何檔。
踩坑後:教訓以一行寫進本檔對應條目(格式:實例+修法),
超過 30 條時開新 session 精簡合併。改檔前 cp 原檔為 .bak。

## G. 給未來 session 的信

三件他沒問但你必須知道的事:
1. 這位使用者的節奏是「先衝再修」——他會跳過你的驗收步驟、
   同時開三條線、把 key 貼在對話裡。你的職責不是攔住他,是讓
   每次跳過都有記錄(WAIVED + 補償措施),讓 key 洩露後有
   「事後換 key」的提醒。制度要有彈性,不變式沒有。
2. 最值錢的檔案是 points-workflows-analysis.md 和他的裁決記錄
   ——那是他十年的判斷力。任何錢包/交易功能先讀它們再動手。
3. 真正的產品目標只有一個:讓他交易不再虧錢。所有華麗功能都
   服務於「寫計畫→被批判→留記錄→對答案」這條紀律迴圈。
   Phase 20 閘門(30筆紙上、90%遵守率)是聖線,別鬆。

這套制度最可能的退化方式與預防:
- 退化一:裁決變蓋章(報告來了直接 ACCEPTED)。預防:每次
  裁決必須引用至少一行你親自讀過的 diff/輸出,寫進 verdict。
- 退化二:工單越寫越薄,Codex 開始猜。預防:Sonnet pre-start
  review 四次全中的紀錄就是證據,永不跳過(使用者豁免要記錄)。
- 退化三:cron/監控壞了沒人發現(靜默腐敗)。預防:一切定時
  任務 fail loud;每月一次讓使用者跑 ingest_runs 健康檢查。
- 退化四:本檔被遺忘。預防:CLAUDE.md 已加路由;每個裁決
  session 開場先讀本檔 D 節。

誠實條款:拆解+驗證+審查補得了執行品質;「這個比例划不划算」
「這個風險值不值得」這類品味題,任何模型都補不了——遇到就給
數字、列選項、讓他選。查不到的事標註「未查證」,永不編造。
