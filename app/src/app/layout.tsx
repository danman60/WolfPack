import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Web3Providers } from "@/lib/wagmi";
import { ExchangeProvider } from "@/lib/exchange";
import { Nav } from "@/components/Nav";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "WolfPack",
  description: "Multi-agent crypto intelligence & trading platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Web3Providers>
          <ExchangeProvider>
            <Nav />
            <main className="max-w-7xl mx-auto px-5 py-8">{children}</main>
          </ExchangeProvider>
        </Web3Providers>
      </body>
    </html>
  );
}
