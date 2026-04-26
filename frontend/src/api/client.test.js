/**
 * @vitest-environment jsdom
 *
 * Tests for the centralized API client.
 *
 * The 401 handling path is the most important contract: it MUST clear the
 * stored access token and dispatch an `auth:logout` event so AuthContext can
 * react and redirect the user. A regression here would silently leave a stale
 * token in localStorage and skip the redirect.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { apiRequest } from './client';

/**
 * Build a minimal Response-like object that satisfies what `apiRequest` reads.
 * Using a plain object (rather than the real Response constructor) keeps the
 * test focused on the branches we care about.
 */
function makeResponse({ status = 200, body = {} } = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: () => Promise.resolve(body),
  };
}

describe('apiRequest', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('returns parsed JSON on a 2xx response', async () => {
    fetch.mockResolvedValueOnce(
      makeResponse({ status: 200, body: { ok: true } })
    );

    const result = await apiRequest('/health');

    expect(result).toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledWith(
      '/api/health',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('clears the access token and dispatches auth:logout on 401', async () => {
    localStorage.setItem('access_token', 'stale-token');
    fetch.mockResolvedValueOnce(
      makeResponse({ status: 401, body: { detail: 'Not authenticated' } })
    );

    const listener = vi.fn();
    window.addEventListener('auth:logout', listener);

    try {
      await expect(apiRequest('/jobs')).rejects.toThrow('Not authenticated');
    } finally {
      window.removeEventListener('auth:logout', listener);
    }

    // Token must be wiped so subsequent requests don't keep sending it.
    expect(localStorage.getItem('access_token')).toBeNull();

    // Event must fire exactly once and carry a returnTo path so AuthContext
    // can route the user back after re-login.
    expect(listener).toHaveBeenCalledTimes(1);
    const event = listener.mock.calls[0][0];
    expect(event.type).toBe('auth:logout');
    expect(event.detail).toHaveProperty('returnTo');
    expect(typeof event.detail.returnTo).toBe('string');
  });
});
