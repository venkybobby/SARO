import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  define: {
    // Map CRA-style env var to Vite env var so existing source files work unchanged
    "process.env.REACT_APP_SARO_API_URL": JSON.stringify(
      process.env.VITE_SARO_API_URL || ""
    ),
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        // Vite 8 bundles with Rolldown, which accepts only the function form of
        // manualChunks — the object/name-map form fails the build with
        // "TypeError: manualChunks is not a function". Same two chunks as
        // before, matched by module path instead of by package name.
        // Order matters: react-router-dom's path also contains "react".
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (/node_modules[\\/]react-router(-dom)?[\\/]/.test(id))
            return "router";
          if (/node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id))
            return "react";
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_SARO_API_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      // FND-060: Sidebar.jsx polls /health for the API-status badge; without
      // this entry Vite serves index.html and dev shows a false "API offline".
      "/health": {
        target: process.env.VITE_SARO_API_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
    // Vitest 4 made vi.spyOn() idempotent: re-spying an already-spied method
    // returns the EXISTING spy with its call history intact, instead of
    // installing a fresh one. Suites that re-create a spy in beforeEach (e.g.
    // TraceView.test.jsx's HTMLAnchorElement.prototype.click) therefore leak
    // call counts between tests, and `expect(spy).not.toHaveBeenCalled()`
    // sees the previous tests' clicks. Restoring after each test gives every
    // beforeEach a genuinely clean prototype, which is what vitest 2 did.
    restoreMocks: true,
  },
});
