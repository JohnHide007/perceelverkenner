import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Bouwt een minimale server (server.js + alleen de benodigde node_modules)
  // zodat de Docker-image klein blijft.
  output: "standalone",
};

export default nextConfig;
