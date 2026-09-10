import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The app lives in a subdirectory of the repository.
  turbopack: { root: __dirname },
};

export default nextConfig;
