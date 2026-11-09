import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages project site path. The same config also works with npm run dev.
export default defineConfig({
  base: "/bug-archaeology/",
  plugins: [react()],
  server: { port: 5173 }
});
