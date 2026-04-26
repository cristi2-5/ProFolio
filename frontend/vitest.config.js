import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/**
 * Vitest configuration.
 *
 * - jsdom environment for DOM-dependent tests (React components, fetch mocks).
 * - Global APIs (`describe`, `it`, `expect`, `vi`) so test files don't need imports.
 * - `src/test/setup.js` extends Vitest's `expect` with jest-dom matchers and
 *   provides per-test cleanup hooks.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    // jsdom rejects localStorage on "opaque origins" — give it a real URL so
    // the Storage prototype gets attached and clear()/setItem()/etc. exist.
    environmentOptions: {
      jsdom: {
        url: 'http://localhost/',
      },
    },
    setupFiles: ['./src/test/setup.js'],
    css: false,
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
    },
  },
});
