import { defineConfig } from 'vite';

// base './': dist/ läuft aus jedem Ordner, auch per python -m http.server
export default defineConfig({
  base: './',
  server: { port: 5180, strictPort: true },
  build: { chunkSizeWarningLimit: 2000 },
});
