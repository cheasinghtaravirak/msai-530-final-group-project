import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the Vite proxy plays the gateway's role: /api -> http://localhost:8080
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8080", changeOrigin: true } },
  },
});
