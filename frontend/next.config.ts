import type { NextConfig } from "next";

const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Browser requests to /api/* are proxied to FastAPI, so the session cookie is
  // first-party on this domain and no CORS is needed.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
  images: {
    remotePatterns: [{ protocol: "https", hostname: "**.cdninstagram.com" }, { protocol: "https", hostname: "**.fbcdn.net" }],
  },
};

export default nextConfig;
