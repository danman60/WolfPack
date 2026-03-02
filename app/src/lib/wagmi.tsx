"use client";

import { createConfig, http } from "wagmi";
import { fallback } from "viem";
import { WagmiProvider } from "wagmi";
import { arbitrum, mainnet } from "wagmi/chains";
import { injected, walletConnect, coinbaseWallet } from "wagmi/connectors";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode, useState } from "react";

export const config = createConfig({
  chains: [arbitrum, mainnet],
  connectors: [
    injected({ shimDisconnect: true }),
    walletConnect({
      projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "demo",
      showQrModal: true,
    }),
    coinbaseWallet({ appName: "WolfPack" }),
  ],
  transports: {
    [arbitrum.id]: fallback([
      http(process.env.NEXT_PUBLIC_RPC_ARBITRUM || "https://arb1.arbitrum.io/rpc"),
      http("https://arbitrum.publicnode.com"),
    ]),
    [mainnet.id]: fallback([
      http(process.env.NEXT_PUBLIC_RPC_MAINNET || "https://ethereum.publicnode.com"),
      http("https://cloudflare-eth.com"),
    ]),
  },
});

export function Web3Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </WagmiProvider>
  );
}
