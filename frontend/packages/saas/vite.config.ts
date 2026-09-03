import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

/**
 * Dev API proxy target.
 * - Default: local Flask :5200
 * - Point at overseas without CORS pain (keep VITE_API_BASE unset so the
 *   browser stays same-origin and Vite proxies):
 *     VITE_PROXY_TARGET=https://api.genz.ltd pnpm --filter @looma/saas dev
 * - If VITE_API_BASE is set, the browser calls that host directly (needs CORS).
 */
const proxyTarget =
  process.env.VITE_PROXY_TARGET ||
  process.env.VITE_API_BASE ||
  "http://localhost:5200";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.ico", "apple-touch-icon.png"],
      manifest: {
        name: "T 空间 - AI 驱动的人才信任网络",
        short_name: "T 空间",
        description: "AI 驱动的人才信任网络 — 简历解析、职位匹配、智能报表",
        theme_color: "#145EFF",
        background_color: "#F1F4F6",
        display: "standalone",
        scope: "/",
        start_url: "/",
        icons: [
          {
            src: "/icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/icon-512.png",
            sizes: "512x512",
            type: "image/png",
          },
          {
            src: "/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        runtimeCaching: [
          {
            urlPattern: /\/v1\/.*/i,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-cache",
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 5, // 5 minutes
              },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@looma/shared-core": path.resolve(__dirname, "../shared-core/src"),
      "@saas": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5174,
    host: "127.0.0.1",
    allowedHosts: ["tspace.servbay.host"],
    proxy: {
      "/v1": {
        target: proxyTarget,
        changeOrigin: true,
        secure: true,
      },
      "/health": {
        target: proxyTarget,
        changeOrigin: true,
        secure: true,
      },
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      external: ["../planetx"],
    },
  },
});