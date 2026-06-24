import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replaceAll("\\", "/");
          if (!normalizedId.includes("node_modules")) {
            return undefined;
          }
          if (normalizedId.includes("echarts") || normalizedId.includes("zrender")) {
            return "vendor-echarts";
          }
          if (normalizedId.includes("element-plus") || normalizedId.includes("@element-plus")) {
            return "vendor-element";
          }
          if (normalizedId.includes("@vue") || normalizedId.includes("vue-router") || normalizedId.includes("pinia")) {
            return "vendor-vue";
          }
          if (normalizedId.includes("@xterm")) {
            return "vendor-xterm";
          }
          if (normalizedId.includes("@novnc")) {
            return "vendor-novnc";
          }
          if (normalizedId.includes("axios")) {
            return "vendor-http";
          }
          return "vendor";
        },
      },
    },
  },
  esbuild: {
    target: "es2022",
  },
  optimizeDeps: {
    esbuildOptions: {
      target: "es2022",
    },
  },
  server: {
    proxy: {
      "/api": process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
  },
});
