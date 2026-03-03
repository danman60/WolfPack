import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { Web3Providers } from "@/lib/wagmi";
import { ExchangeProvider } from "@/lib/exchange";
import { ExchangeToggle } from "@/components/ExchangeToggle";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "WolfPack",
  description: "Multi-agent crypto intelligence & trading platform",
};

const NAV_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/intelligence", label: "Intelligence" },
  { href: "/trading", label: "Trading" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/pools", label: "LP Pools" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Web3Providers>
          <ExchangeProvider>
            <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--background)]/90 backdrop-blur-md">
              <nav className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-8">
                  <Link href="/" className="flex items-center gap-2 font-bold text-lg tracking-tight text-white">
                    <span className="text-xl">🐺</span>
                    WolfPack
                  </Link>
                  <div className="hidden md:flex items-center gap-1">
                    {NAV_LINKS.map((link) => (
                      <Link
                        key={link.href}
                        href={link.href}
                        className="px-3 py-1.5 text-sm font-medium text-gray-400 hover:text-white rounded-md hover:bg-white/5 transition-colors"
                      >
                        {link.label}
                      </Link>
                    ))}
                  </div>
                </div>
                <ExchangeToggle />
              </nav>
            </header>
            <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
          </ExchangeProvider>
        </Web3Providers>
      </body>
    </html>
  );
}
