import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Vite Configuration for Auto-Apply Frontend.
 *
 * Features:
 * - React plugin with Fast Refresh for HMR.
 * - API proxy to FastAPI backend (avoids CORS issues in dev).
 * - Build output to 'dist/' for production.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0', // Allow external connections
    proxy: {
      '/api': {
        target: 'http://backend:8000', // Use Docker service name
        changeOrigin: true,
        secure: false,
      },
      '/health': {
        target: 'http://backend:8000', // Use Docker service name
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
