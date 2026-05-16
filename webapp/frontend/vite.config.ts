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
