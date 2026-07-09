"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

type NavItem = {
  emoji: string;
  label: string;
  href: string;
};

const SIDE_NAV_ITEMS: NavItem[] = [
  { emoji: "🧭", label: "總覽", href: "/" },
  { emoji: "💰", label: "點數錢包", href: "/wallet" },
  { emoji: "✈️", label: "換票比價", href: "/wallet/awards" },
  { emoji: "🏨", label: "住宿比價", href: "/wallet/hotels" },
  { emoji: "📋", label: "交易計畫", href: "/capital/trade-plans" },
  { emoji: "📈", label: "交易決策", href: "/capital/decisions" },
  { emoji: "🛠", label: "工具", href: "/tools" },
];

const BOTTOM_NAV_ITEMS: NavItem[] = [
  { emoji: "🧭", label: "總覽", href: "/" },
  { emoji: "💰", label: "錢包", href: "/wallet" },
  { emoji: "📋", label: "交易計畫", href: "/capital/trade-plans" },
  { emoji: "✈️", label: "比價", href: "/wallet/awards" },
  { emoji: "🛠", label: "工具", href: "/tools" },
];

const MORE_NAV_ITEMS: NavItem[] = [
  { emoji: "🏨", label: "住宿比價", href: "/wallet/hotels" },
  { emoji: "📈", label: "交易決策", href: "/capital/decisions" },
  { emoji: "📊", label: "交易紀錄", href: "/capital/history" },
  { emoji: "📡", label: "市場資料", href: "/capital/market-data" },
  { emoji: "🧪", label: "回測", href: "/capital/backtests" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="主要導覽">
        <Link className="brand-mark" href="/">
          <span className="brand-icon">Φ</span>
          <span>
            <strong>PhiStyle</strong>
            <small>Capital OS</small>
          </span>
        </Link>
        <nav className="side-nav">
          {SIDE_NAV_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
        </nav>
      </aside>

      <div className="app-content">{children}</div>

      <nav className="bottom-tabs" aria-label="手機導覽">
        {BOTTOM_NAV_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} compact />
        ))}
        <details className="bottom-more">
          <summary>
            <span>⋯</span>
            <small>更多</small>
          </summary>
          <div className="bottom-more-panel">
            {MORE_NAV_ITEMS.map((item) => (
              <Link key={item.href} href={item.href}>
                <span aria-hidden="true">{item.emoji}</span>
                {item.label}
              </Link>
            ))}
          </div>
        </details>
      </nav>
    </div>
  );
}

function NavLink({ item, pathname, compact = false }: { item: NavItem; pathname: string; compact?: boolean }) {
  const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
  return (
    <Link className={isActive ? "nav-link nav-link-active" : "nav-link"} href={item.href}>
      <span aria-hidden="true">{item.emoji}</span>
      <small>{item.label}</small>
      {!compact ? <i aria-hidden="true" /> : null}
    </Link>
  );
}
