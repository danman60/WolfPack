"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ExchangeToggle } from "./ExchangeToggle";

const NAV_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/intelligence", label: "Intelligence" },
  { href: "/trading", label: "Trading" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/backtest", label: "Backtest" },
  { href: "/auto-bot", label: "Auto-Bot" },
  { href: "/evolution", label: "Evolution" },
  { href: "/pools", label: "LP Pools" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [cbState, setCbState] = useState<string>("unknown");

  useEffect(() => {
    const fetchCB = async () => {
      try {
        const res = await fetch("/intel/circuit-breaker");
        if (res.ok) {
          const data = await res.json();
          // The modules endpoint returns the latest module output
          const state = data?.output?.state || data?.state || "unknown";
          setCbState(state);
        }
      } catch {
        // Silently fail — badge just stays unknown
      }
    };

    fetchCB();
    const interval = setInterval(fetchCB, 30000); // every 30s
    return () => clearInterval(interval);
  }, []);

  const cbColor = cbState === "ACTIVE" ? "bg-green-500" :
                  cbState === "SUSPENDED" ? "bg-amber-500" :
                  cbState === "EMERGENCY_STOP" ? "bg-red-500" :
                  "bg-gray-500";
  const cbLabel = cbState === "ACTIVE" ? "Circuit Breaker: Active" :
                  cbState === "SUSPENDED" ? "Circuit Breaker: Suspended" :
                  cbState === "EMERGENCY_STOP" ? "Circuit Breaker: Emergency Stop" :
                  "Circuit Breaker: Unknown";

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-xl backdrop-saturate-150">
      <nav className="max-w-7xl mx-auto px-4 md:px-5 py-3.5 flex items-center justify-between">
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
            <span className="font-bold text-[15px] tracking-tight text-white flex items-center gap-1.5">
              WolfPack
              <span
                className={`${cbColor} rounded-full w-2 h-2 inline-block`}
                title={cbLabel}
              />
            </span>
          </Link>
          {/* Desktop nav */}
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
        <div className="flex items-center gap-3">
          <div className="hidden md:block">
            <ExchangeToggle />
          </div>
          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2.5 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-white/5 active:bg-white/10 transition"
            aria-label="Toggle menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              {mobileOpen ? (
                <>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </>
              ) : (
                <>
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </>
              )}
            </svg>
          </button>
        </div>
      </nav>
      {/* Mobile dropdown */}
      {mobileOpen && (
        <div className="md:hidden border-t border-[var(--border)] bg-[var(--background)]/95 backdrop-blur-xl px-4 py-3 space-y-1 mobile-nav-enter">
          {NAV_LINKS.map((link) => {
            const isActive =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href);

            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className={`block py-3 px-3 rounded-lg text-sm font-medium transition min-h-[44px] flex items-center ${
                  isActive
                    ? "bg-[var(--wolf-emerald)]/10 text-[var(--wolf-emerald)] border-l-2 border-[var(--wolf-emerald)]"
                    : "text-gray-400 hover:text-white hover:bg-white/5 active:bg-white/10"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
          <div className="pt-2 border-t border-[var(--border)] mt-2">
            <ExchangeToggle />
          </div>
        </div>
      )}
    </header>
  );
}
