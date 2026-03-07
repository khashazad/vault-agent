import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:3000",
      "/vault": "http://localhost:3000",
      "/highlights": "http://localhost:3000",
      "/changesets": "http://localhost:3000",
      "/routing": "http://localhost:3000",
      "/zotero": "http://localhost:3000",
    },
  },
});
