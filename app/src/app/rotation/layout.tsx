import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Rotation | WolfPack",
  description: "Compare CAD, BTC, ETH and LINK paper decisions against holding. Review costs, performance and experimental research before making a shift.",
  robots: { index: false, follow: false },
};

export default function RotationLayout({ children }: { children: React.ReactNode }) {
  return children;
}
