"use client";

import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

// Load wallet connector code only on the existing exchange/wallet surfaces.
const LegacyProviders = dynamic(() => import("./LegacyProviders"));

export function AppProviders({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (pathname.startsWith("/rotation")) return children;
  return <LegacyProviders>{children}</LegacyProviders>;
}
