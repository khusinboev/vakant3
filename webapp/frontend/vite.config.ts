import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5174,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        // Name lazy page chunks after their folder (pages/Admin/index.tsx -> Admin-*.js)
        chunkFileNames: (chunk) => {
          // Lazy page chunks (pages/Admin/index.tsx) would otherwise all be called "index".
          const ids = [chunk.facadeModuleId ?? "", ...chunk.moduleIds];
          for (const id of ids) {
            const page = id.match(/\/src\/pages\/([^/]+)\//);
            if (page) return `assets/${page[1]}-[hash].js`;
            const dict = id.match(/\/src\/i18n\/(ru|en)\/index\.ts$/);
            if (dict) return `assets/i18n-${dict[1]}-[hash].js`;
          }
          return "assets/[name]-[hash].js";
        },
        manualChunks: {
          // React core — changes rarely, long-term cacheable
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          // State / data fetching
          "vendor-query": ["@tanstack/react-query", "axios", "zustand"],
          // Icons
          "vendor-icons": ["lucide-react"],
        },
      },
    },
    // Raise the warning threshold so the smaller chunks don't trigger warnings
    chunkSizeWarningLimit: 600,
  },
});
