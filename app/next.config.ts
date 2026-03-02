import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/intel/:path*",
        destination: `${process.env.INTEL_SERVICE_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
