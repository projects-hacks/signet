import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

import { defineConfig } from "vite";

// Two pages, not a router. Static hosting's history fallback is undocumented on
// the platform this deploys to, and a homepage that 404s is worse than a URL
// with a directory in it. The base is absolute because a nested page cannot
// resolve a relative asset path back to the root.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        home: resolve(__dirname, "index.html"),
        verify: resolve(__dirname, "verify/index.html"),
      },
    },
  },
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8822", changeOrigin: true } },
  },
});
