import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Relative base so the build runs anywhere it is mounted, and a dev proxy so the
// frontend calls the same paths in development that it will call in production.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8822", changeOrigin: true } },
  },
});
