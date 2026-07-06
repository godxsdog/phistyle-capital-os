# Ticket: PW-1 r3 — Wallet UX 人性化修正(使用者實測回饋)

FABLE-APPROVED: yes (2026-07-07). OWNER: Codex. VERDICT: new Fable
session. Frontend-only + read-only API additions;禁改 schema/服務層
商業邏輯/migration(需要即 STOP)。

## 使用者原話(驗收的最終標準)

「看不懂怎麼用、很多選單都要自己填、沒有記憶選項、要繁體中文、
原本那套一頁一頁比較人性。」

## BINDING DECISIONS

1. 全站 UI 語言 = 繁體中文(zh-TW):/wallet 所有標籤、按鈕、
   狀態、警告、空狀態提示全部中文化。kind 等 enum 顯示中文
   (earn=獲得/buy=購買/transfer_in=轉入/transfer_out=轉出/
   redeem=兌換/expire=到期/adjustment=調整),送 API 仍用英文值。
   此後所有新 frontend 頁面預設繁中(寫入本工單即為政策)。
2. 頁面流以 legacy/points-wallet/index.html 為 UX 藍本(唯讀參考):
   一頁一頁的分頁結構——「總覽」「凱章」「老婆」「轉點規則」
   「買分價格」——而不是一頁塞所有表單。總覽 = 兩人合計價值、
   各計畫餘額表、到期警示。
3. 消滅手填:所有 program/account 欄位一律下拉選單(選項來自 DB,
   依 owner 過濾);日期預設今天;幣別預設 TWD;下拉不含自由文字。
   新計畫的建立走獨立「新增計畫」小表單,不混在交易輸入裡。
4. 記憶選項:上次選的 owner/program/kind/幣別 存 localStorage
   (僅 UI 偏好,非業務資料——不違反「PostgreSQL 單一真相」,
   業務數字永不進 localStorage)。重開頁面自動帶入。
5. 轉點規則顯示格式(範例即規格):
   「平安萬里通 → BA Avios:30,000 → 10,000(3:1,+20% 加贈,
   實得 12,000;有效至 2026-12-31)」
   即:人話句子 + 換算後實得數 + 有效期;表格可依 from/to 篩選。
   比例一律以「送出:實得」呈現,不裸露 ratio_from/ratio_to 欄位名。
6. 成本顯示:每點成本固定「NT$0.372/點」格式,三位小數;總值千分位。
7. 每個輸入表單頂部一行灰字說明這頁在幹嘛(例:「在這裡記錄
   點數的取得或使用,每一筆都會留下不可修改的帳本記錄」)。

## SCOPE

frontend/app/wallet/*、frontend/lib/walletApi.ts(僅型別/讀取)、
必要時 main.py 加唯讀查詢端點(additive)。tsc + next build 必須過。
測試:既有測試不動;UI 中文對照表放 constants 檔便於日後修改。

## OUT OF SCOPE

schema、服務層、migration、匯入邏輯、PW-2 引擎、認證、i18n 框架
(直接寫中文即可,不裝套件)。

## MANUAL VERIFICATION(使用者)

不看說明書的情況下:能在 30 秒內找到「幫老婆的 Qatar 加一筆點數」
的入口並完成;轉點規則頁一眼看懂任一條規則;重開頁面上次的
選擇還在;全程無英文介面文字。
