"use client";

import { createContext, useContext, useState, ReactNode } from "react";

type WalletContextType = {
  perpWallet: string;
  lpWallet: string;
  setPerpWallet: (w: string) => void;
  setLpWallet: (w: string) => void;
};

const WalletContext = createContext<WalletContextType>({
  perpWallet: "paper_perp",
  lpWallet: "paper_lp",
  setPerpWallet: () => {},
  setLpWallet: () => {},
});

export function WalletProvider({ children }: { children: ReactNode }) {
  const [perpWallet, setPerpWallet] = useState("paper_perp");
  const [lpWallet, setLpWallet] = useState("paper_lp");

  return (
    <WalletContext.Provider
      value={{ perpWallet, lpWallet, setPerpWallet, setLpWallet }}
    >
      {children}
    </WalletContext.Provider>
  );
}

export function useWalletContext() {
  return useContext(WalletContext);
}
