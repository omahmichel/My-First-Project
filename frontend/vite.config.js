import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite development configuration. The proxy is ready for the future Django API.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
