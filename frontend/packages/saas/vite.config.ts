import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

/**
 * Dev API proxy target.
 * - Default: local zervi-rust gateway :3333（浏览器仍访问 :5174，由 Vite 转发）
 * - Flask :5200：VITE_PROXY_TARGET=http://127.0.0.1:5200
 * - 海外：VITE_PROXY_TARGET=https://api.genz.ltd （保持 VITE_API_BASE 为空，避免浏览器跨域）
 * - 若设置了 VITE_API_BASE，浏览器会直接打那个地址（需要 CORS）。
 */
const proxyTarget =
  process.env.VITE_PROXY_TARGET ||
  process.env.VITE_API_BASE ||
  "http://127.0.0.1:3333";

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
    host: "0.0.0.0",
    allowedHosts: true,
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