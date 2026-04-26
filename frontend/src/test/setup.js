/**
 * Vitest global setup.
 *
 * - Registers @testing-library/jest-dom matchers (toBeInTheDocument, etc.).
 * - Cleans up the rendered DOM and resets all mocks between tests so state
 *   does not leak across test files.
 * - Patches a working `localStorage`/`sessionStorage`. Under Node 25 + jsdom
 *   29 + Vitest 4, the prototype methods (clear/getItem/setItem/removeItem)
 *   come back as `undefined` because Node's built-in webstorage shim shadows
 *   jsdom's Storage. We replace the storage objects with a tiny in-memory
 *   implementation so production code that uses `localStorage.*` works in
 *   tests without needing per-test stubs.
 */
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

function createMemoryStorage() {
  const store = new Map();
  return {
    get length() {
      return store.size;
    },
    key(i) {
      return Array.from(store.keys())[i] ?? null;
    },
    getItem(k) {
      return store.has(k) ? store.get(k) : null;
    },
    setItem(k, v) {
      store.set(String(k), String(v));
    },
    removeItem(k) {
      store.delete(k);
    },
    clear() {
      store.clear();
    },
  };
}

// Replace on both `globalThis` and `window` so `localStorage.foo()` and
// `window.localStorage.foo()` resolve to the same working object.
const ls = createMemoryStorage();
const ss = createMemoryStorage();
Object.defineProperty(globalThis, 'localStorage', {
  value: ls,
  configurable: true,
});
Object.defineProperty(globalThis, 'sessionStorage', {
  value: ss,
  configurable: true,
});
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'localStorage', {
    value: ls,
    configurable: true,
  });
  Object.defineProperty(window, 'sessionStorage', {
    value: ss,
    configurable: true,
  });
}

afterEach(() => {
  cleanup();
  ls.clear();
  ss.clear();
});
