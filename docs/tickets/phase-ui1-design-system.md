# Ticket: UI-1 — 全站設計系統 + 完全繁體化

FABLE-APPROVED: yes (2026-07-09)。純前端,禁改任何 API 行為/
schema/商業邏輯(需要=STOP)。OWNER: Codex。VERDICT: new Fable
session。參考風格(BINDING):自架財務儀表板系(Firefly III/
Actual Budget)的乾淨卡片式 + TradingView 的紅綠狀態色語言。

## BINDING DECISIONS

U1 共用 Layout(一次建,全站套):
  桌面 = 左側固定側欄導覽(logo + 7 入口,沿用 launcher 的
  emoji+名稱);手機(<768px)= 底部 tab bar(5 個高頻:總覽/
  錢包/交易計畫/比價/工具)+ 其餘收進「更多」。現有 launcher
  首頁改為「總覽儀表板」:頂部 KPI 卡片列(點數總值 TWD、
  開放中交易計畫數、最近回測、到期警示數——全部呼叫既有
  端點,無新後端)。
U2 設計 token(CSS variables,單一 globals 檔):
  背景 #0f172a 深色為預設(交易人夜盤習慣),文字 #e2e8f0,
  卡片 #1e293b,主色 teal #14b8a6(沿用 PWA 圖示),
  漲/獲利 #ef4444 紅、跌/虧損 #22c55e 綠(台股慣例:紅漲綠跌
  ——這是台灣使用者,不用美式配色),警示 amber。字體
  system-ui 堆疊,數字用 tabular-nums。
U3 共用元件(components/ 下,全站替換散落樣式):
  Card、KPI 卡、DataTable(斑馬紋、手機橫向捲動)、
  StatusChip(狀態→中文+色:human_approved=已核准/綠底…
  完整對照表寫進 constants)、PageHeader(標題+說明一行)、
  EmptyState(空資料時的中文引導+行動按鈕)。
U4 完全繁體化:capital 系列頁(decisions/history/trade-plans/
  backtests/market-data)所有標籤、按鈕、表頭、狀態、錯誤訊息、
  空狀態全部中文化;enum 顯示中文、傳輸仍英文值;所有中文
  對照集中 constants 檔(wallet 已有的沿用擴充)。金額千分位、
  每點成本三位小數、日期 YYYY/MM/DD。
U5 逐頁重排原則:不改任何資料流與端點呼叫,只換殼——
  每頁 = PageHeader + 卡片分區 + 共用 DataTable。表單維持
  r3 慣例(下拉、記憶偏好、頂部灰字說明)。
U6 手機優先驗收:iPhone 寬度下每頁無橫向溢出、按鈕可拇指觸及。

## SCOPE / 禁區

只動 frontend/**;launcher/PWA 沿用;禁改 walletApi/capitalApi
的請求邏輯(型別與顯示層可動);tsc+build 必過;既有前端行為
(r3/r4 驗收過的)不得退化。

## 驗收(使用者唯一標準)

手機開任意頁:全中文、深色、紅漲綠跌、表格不破版;
總覽一眼看到四張 KPI 卡;30 秒內從總覽走到任何功能。

## 標準完成報告;分兩個 commit:
1. feat: design system + shared layout (ui-1a)
2. feat: localize capital pages zh-tw (ui-1b)
