import Link from "next/link";
import { Card, KpiCard, PageHeader, StatusChip } from "../components/ui";
import { formatDateZh, formatMoneyTwd } from "../lib/displayConstants";

type LauncherTile = {
  emoji: string;
  label: string;
  href: string;
  note: string;
};

type PortfolioSummary = {
  total_real_cost_basis_twd: string;
};

type TradePlanSummary = {
  id: number;
};

type BacktestRunSummary = {
  id: number;
  created_at: string;
  spec_snapshot: Record<string, unknown>;
};

type ExpiryAlertSummary = {
  id: number;
  status: string;
};

const LAUNCHER_TILES: LauncherTile[] = [
  { emoji: "💰", label: "錢包總覽", href: "/wallet", note: "餘額、成本、到期提醒" },
  { emoji: "✈️", label: "換票比價", href: "/wallet/awards", note: "里程需求與補點成本" },
  { emoji: "🧭", label: "旅程尋票", href: "/wallet/quests", note: "來回日期窗與哩程配對" },
  { emoji: "🏨", label: "住宿比價", href: "/wallet/hotels", note: "現金、點數、房券比較" },
  { emoji: "🔄", label: "轉點規則", href: "/wallet?tab=wanlitong", note: "來源計畫視角管理" },
  { emoji: "📈", label: "交易決策", href: "/capital/decisions", note: "Brain 與人工審查狀態" },
  { emoji: "📋", label: "交易計畫", href: "/capital/trade-plans", note: "紙上交易與風控路徑" },
  { emoji: "📊", label: "交易紀錄", href: "/capital/history", note: "匯入與虧損歸因" },
  { emoji: "📡", label: "市場資料", href: "/capital/market-data", note: "watchlist 與資料健康" },
  { emoji: "🧪", label: "回測", href: "/capital/backtests", note: "決定論策略驗證" },
  { emoji: "🛠", label: "工具", href: "/tools", note: "臨時監視器與維運工具" },
];

async function getJson<T>(path: string): Promise<T | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export default async function Home() {
  const [portfolio, tradePlans, backtests, expiryAlerts, health] = await Promise.all([
    getJson<PortfolioSummary>("/wallet/portfolio"),
    getJson<TradePlanSummary[]>("/capital/trade-plans"),
    getJson<BacktestRunSummary[]>("/capital/backtests/runs"),
    getJson<ExpiryAlertSummary[]>("/wallet/expiry-alerts"),
    getJson<{ status?: string }>("/health"),
  ]);

  const latestBacktest = backtests?.[0] || null;
  const latestBacktestName = latestBacktest
    ? String(latestBacktest.spec_snapshot.name || `#${latestBacktest.id}`)
    : "尚無紀錄";
  const activeExpiryAlerts = expiryAlerts?.filter((alert) => alert.status !== "resolved").length ?? 0;

  return (
    <main>
      <div className="shell">
        <PageHeader
          kicker="PhiStyle Capital OS"
          title="總覽儀表板"
          description="把點數、交易計畫、市場資料與工具集中在一個入口，先看狀態，再進功能。"
          actions={<StatusChip value={health?.status === "ok" ? "success" : "pending"} />}
        />

        <section className="overview-grid" aria-label="核心指標">
          <KpiCard
            label="點數總值 TWD"
            value={portfolio ? formatMoneyTwd(portfolio.total_real_cost_basis_twd) : "暫無資料"}
            note="依錢包既有成本基礎計算"
            tone="accent"
          />
          <KpiCard
            label="開放中交易計畫"
            value={tradePlans ? tradePlans.length.toLocaleString("zh-TW") : "暫無資料"}
            note="沿用交易計畫列表端點"
            tone="neutral"
          />
          <KpiCard
            label="最近回測"
            value={latestBacktestName}
            note={latestBacktest ? formatDateZh(latestBacktest.created_at) : "尚未執行"}
            tone="warning"
          />
          <KpiCard
            label="到期警示"
            value={expiryAlerts ? activeExpiryAlerts.toLocaleString("zh-TW") : "暫無資料"}
            note="90/60/30/7 天提醒"
            tone={activeExpiryAlerts > 0 ? "warning" : "neutral"}
          />
        </section>

        <Card>
          <div className="stage-header">
            <div>
              <div className="section-kicker">快速入口</div>
              <h2>30 秒內到任何功能</h2>
            </div>
          </div>
          <nav className="feature-grid" id="more" aria-label="功能選單">
            {LAUNCHER_TILES.map((tile) => (
              <Link key={tile.href} className="feature-tile" href={tile.href}>
                <span className="feature-emoji" aria-hidden="true">
                  {tile.emoji}
                </span>
                <strong>{tile.label}</strong>
                <small>{tile.note}</small>
              </Link>
            ))}
          </nav>
        </Card>
      </div>
    </main>
  );
}
