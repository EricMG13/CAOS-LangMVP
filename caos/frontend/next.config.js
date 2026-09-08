const { PHASE_DEVELOPMENT_SERVER } = require("next/constants");

const base = {
  reactStrictMode: true,
  output: "export",
  trailingSlash: true,
  skipTrailingSlashRedirect: true,
  images: { unoptimized: true },
  experimental: {
    turbopackFileSystemCacheForDev: false,
  },
};

module.exports = (phase) => phase === PHASE_DEVELOPMENT_SERVER
  ? {
      ...base,
      allowedDevOrigins: ["3000-" + (process.env.BASE44_PUBLIC_HOST_SUFFIX || "localhost")],
      async rewrites() {
        const apiUrl = process.env.API_PROXY_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
      },
    }
  : base;
