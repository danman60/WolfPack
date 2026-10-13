import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    const headers = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
      { key: "Content-Security-Policy", value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'" },
      { key: "Strict-Transport-Security", value: "max-age=31536000" },
    ];
    return [
      { source: "/rotation/:path*", headers },
      { source: "/api/rotation/:path*", headers },
    ];
  },
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
