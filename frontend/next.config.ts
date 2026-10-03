import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // A self-contained server in .next/standalone: what runs on the server (deploy/setup.sh).
  output: "standalone",
};

export default nextConfig;
