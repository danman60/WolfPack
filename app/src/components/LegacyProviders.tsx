"use client";

import type { ReactNode } from "react";
import { Web3Providers } from "@/lib/wagmi";
import { ExchangeProvider } from "@/lib/exchange";
import { WalletProvider } from "@/lib/wallet/context";

export default function LegacyProviders({ children }: { children: ReactNode }) {
  return <Web3Providers><ExchangeProvider><WalletProvider>{children}</WalletProvider></ExchangeProvider></Web3Providers>;
}
