import type { NextConfig } from "next";

// API proxy is handled by app/api/proxy/[...path]/route.ts (App Router route handler).
// It reads BACKEND_URL at runtime (server-side), avoiding the NEXT_PUBLIC_* build-time
// baking issue that would cause rewrites to fall back to localhost:8000.
const nextConfig: NextConfig = {
  env: {
    APP_ENV: process.env.APP_ENV,
  },
};

export default nextConfig;
