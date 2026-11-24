import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// In development the Vite proxy plays the gateway's role: /api -> VITE_API_TARGET (default http://localhost:8080)
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": { target: env.VITE_API_TARGET ?? "http://localhost:8080", changeOrigin: true } },
    },
  };
});
