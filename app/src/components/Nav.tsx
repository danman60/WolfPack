"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ExchangeToggle } from "./ExchangeToggle";

const NAV_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/intelligence", label: "Intelligence" },
  { href: "/trading", label: "Trading" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/backtest", label: "Backtest" },
  { href: "/pools", label: "LP Pools" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-xl backdrop-saturate-150">
      <nav className="max-w-7xl mx-auto px-5 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-10">
          <Link
            href="/"
            className="flex items-center gap-2.5 group"
          >
            <div className="w-8 h-8 rounded-lg bg-[var(--wolf-emerald)]/10 border border-[var(--wolf-emerald)]/20 flex items-center justify-center group-hover:bg-[var(--wolf-emerald)]/15 group-hover:border-[var(--wolf-emerald)]/30 transition-all">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--wolf-emerald)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <span className="font-bold text-[15px] tracking-tight text-white">
              WolfPack
            </span>
          </Link>
          <div className="hidden md:flex items-center gap-0.5">
            {NAV_LINKS.map((link) => {
              const isActive =
                link.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(link.href);

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`nav-link ${isActive ? "nav-link-active" : ""}`}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>
        <ExchangeToggle />
      </nav>
    </header>
  );
}
