import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@looma/shared-core": path.resolve(__dirname, "../shared-core/src"),
      "@planetx": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
    allowedHosts: ["planetx.servbay.host"],
    proxy: {
      "/v1": {
        target: process.env.VITE_API_BASE || "http://localhost:5200",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      // Ensure SaaS code never enters PlanetX bundle
      external: ["../saas"],
    },
  },
});
