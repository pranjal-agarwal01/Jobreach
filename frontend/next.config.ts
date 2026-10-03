import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // A self-contained server in .next/standalone, for the deploy image (frontend/Dockerfile).
  output: "standalone",
};

export default nextConfig;
