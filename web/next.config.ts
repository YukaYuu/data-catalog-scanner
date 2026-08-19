import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output so the Docker image only needs the production
  // server bundle, not the full node_modules tree -- matches the API's
  // Dockerfile using a distroless final stage for the same reason.
  output: "standalone",
};

export default nextConfig;
