import type {NextConfig} from "next";
import path from "node:path";

const apiBase =
  process.env.CONTROL_API_INTERNAL_URL ?? "http://control-api:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  typedRoutes: false,
  turbopack: {
    root: path.resolve(import.meta.dirname, "../.."),
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "base-uri 'self'",
              "connect-src 'self'",
              "font-src 'self'",
              "form-action 'self'",
              "frame-ancestors 'none'",
              "img-src 'self' data:",
              "object-src 'none'",
              "script-src 'self' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
            ].join("; "),
          },
          {key: "X-Content-Type-Options", value: "nosniff"},
          {key: "X-Frame-Options", value: "DENY"},
          {key: "Referrer-Policy", value: "no-referrer"},
          {key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()"},
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/public/:path*",
        destination: `${apiBase}/public/:path*`,
      },
    ];
  },
};

export default nextConfig;
