import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:3456",
      "/vault": "http://localhost:3456",
      "/highlights": "http://localhost:3456",
      "/routing": "http://localhost:3456",
      "/zotero": "http://localhost:3456",
      "/changesets": {
        target: "http://localhost:3456",
        bypass: (req) => {
          if (req.headers.accept?.includes("text/html")) return "/index.html";
        },
      },
      "/migration": {
        target: "http://localhost:3456",
        bypass: (req) => {
          if (req.headers.accept?.includes("text/html")) return "/index.html";
        },
      },
    },
  },
  preview: {
    proxy: {},
  },
});
