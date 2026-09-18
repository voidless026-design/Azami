import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The desktop app talks to the local backend; in dev we proxy /api to it.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8099", changeOrigin: true, ws: true },
    },
  },
  build: { outDir: "dist", sourcemap: true },
});
