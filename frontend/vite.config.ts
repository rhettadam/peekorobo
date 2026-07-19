import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { createReadStream, existsSync, statSync } from "node:fs";
import { join, extname, normalize } from "node:path";
import { fileURLToPath } from "node:url";

// Repo-root assets/ folder (logo, avatars, game logos, icons). In dev we serve
// it at /assets so the SPA can use real assets without copying thousands of
// files into the frontend. In production, set VITE_ASSETS_BASE_URL to a CDN.
const ASSETS_DIR = fileURLToPath(new URL("../assets", import.meta.url));

const MIME: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".webp": "image/webp",
  ".html": "text/html",
};

function serveRepoAssets(): Plugin {
  return {
    name: "serve-repo-assets",
    configureServer(server) {
      server.middlewares.use("/assets", (req, res, next) => {
        const urlPath = decodeURIComponent((req.url || "").split("?")[0]);
        const filePath = normalize(join(ASSETS_DIR, urlPath));
        if (!filePath.startsWith(ASSETS_DIR)) {
          res.statusCode = 403;
          res.end("Forbidden");
          return;
        }
        if (!existsSync(filePath) || !statSync(filePath).isFile()) {
          next();
          return;
        }
        const type = MIME[extname(filePath).toLowerCase()];
        if (type) res.setHeader("Content-Type", type);
        res.setHeader("Cache-Control", "public, max-age=3600");
        createReadStream(filePath).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), serveRepoAssets()],
  server: {
    port: 5173,
    proxy: {
      // Forward /api/* to a standalone API running on :8000 (path prefix stripped).
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
