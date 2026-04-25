import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "../sparkd/static", emptyOutDir: true },
  server: {
    proxy: {
      "/boxes": "http://127.0.0.1:8765",
      "/recipes": "http://127.0.0.1:8765",
      "/launches": "http://127.0.0.1:8765",
      "/jobs": "http://127.0.0.1:8765",
      "/healthz": "http://127.0.0.1:8765",
      "/ws": { target: "ws://127.0.0.1:8765", ws: true },
    },
  },
  test: { environment: "jsdom" },
});
