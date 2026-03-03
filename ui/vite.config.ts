import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:3000",
      "/vault": "http://localhost:3000",
      "/highlights": "http://localhost:3000",
      "/changesets": "http://localhost:3000",
    },
  },
});
