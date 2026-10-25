/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backendUrl = process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
      {
        source: "/scan/:path*",
        destination: `${backendUrl}/scan/:path*`,
      },
      {
        source: "/scan",
        destination: `${backendUrl}/scan`,
      },
    ];
  },
};

export default nextConfig;
