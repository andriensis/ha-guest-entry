import { resolve } from "path";
import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  base: "./",
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:7979", changeOrigin: true },
      "/internal": { target: "http://localhost:7979", changeOrigin: true },
      "/admin": { target: "http://localhost:7980", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        admin: resolve(__dirname, "admin.html"),
      },
    },
  },
});
