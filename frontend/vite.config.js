import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Vite Configuration for Auto-Apply Frontend.
 *
 * Proxy target resolves via VITE_API_TARGET:
 *   - Docker Compose sets it to `http://backend:8000` (service name).
 *   - Local `npm run dev` falls back to `http://127.0.0.1:8000`.
 */
const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
        secure: false,
      },
      '/health': {
        target: API_TARGET,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: process.env.NODE_ENV === 'production' ? false : true,
  },
});
