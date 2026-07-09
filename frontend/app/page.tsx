import Link from "next/link";
import styles from "./LauncherPage.module.css";

// PhiStyle launcher — mobile-first home screen.
// IMPORTANT: all new pages must be added to LAUNCHER_TILES below so they
// stay reachable from the home screen.
type LauncherTile = {
  emoji: string;
  label: string;
  href: string;
};

const LAUNCHER_TILES: LauncherTile[] = [
  { emoji: "💰", label: "錢包總覽", href: "/wallet" },
  { emoji: "✈️", label: "換票比價", href: "/wallet/awards" },
  { emoji: "🏨", label: "住宿比價", href: "/wallet/hotels" },
  { emoji: "🔄", label: "轉點規則", href: "/wallet?tab=wanlitong" },
  { emoji: "📈", label: "交易決策", href: "/capital/decisions" },
  { emoji: "📋", label: "交易計畫", href: "/capital/trade-plans" },
  { emoji: "📊", label: "交易紀錄", href: "/capital/history" },
  { emoji: "📡", label: "市場資料", href: "/capital/market-data" },
  { emoji: "🧪", label: "回測", href: "/capital/backtests" },
  { emoji: "🛠", label: "工具", href: "/tools" },
];

async function getHealth(): Promise<string> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}/health`, { cache: "no-store" });
    if (!response.ok) {
      return `unavailable (${response.status})`;
    }
    const payload = (await response.json()) as { status?: string };
    return payload.status || "unknown";
  } catch {
    return "unavailable";
  }
}

export default async function Home() {
  const status = await getHealth();

  return (
    <main>
      <div className="shell">
        <section className="hero">
          <div className="eyebrow">PhiStyle</div>
          <h1>PhiStyle</h1>
          <p>交易決策、點數錢包與工具的個人入口，手機優先設計。</p>
        </section>

        <nav className={styles.grid} aria-label="功能選單">
          {LAUNCHER_TILES.map((tile) => (
            <Link key={tile.href} className={styles.tile} href={tile.href}>
              <span className={styles.emoji} aria-hidden="true">{tile.emoji}</span>
              <span className={styles.label}>{tile.label}</span>
            </Link>
          ))}
        </nav>

        <p className={styles.statusLine}>後端狀態：{status}</p>
      </div>
    </main>
  );
}
