/**
 * API Client — Centralized HTTP client for backend communication.
 *
 * Uses the native Fetch API with a base URL configured
 * for the Vite proxy (/api → localhost:8000).
 *
 * All methods automatically:
 * - Set Content-Type to application/json.
 * - Attach JWT token from localStorage if available.
 * - Parse JSON responses.
 * - Throw structured errors on non-2xx responses.
 */

const API_BASE = '/api';

/**
 * Make an authenticated API request.
 *
 * @param {string} endpoint - API path (e.g., '/auth/login').
 * @param {Object} [options={}] - Fetch options.
 * @param {string} [options.method='GET'] - HTTP method.
 * @param {Object} [options.body] - Request body (auto-stringified).
 * @param {Object} [options.headers] - Additional headers.
 * @returns {Promise<Object>} Parsed JSON response.
 * @throws {Error} On non-2xx responses with server error detail.
 */
export async function apiRequest(endpoint, options = {}) {
  const { method = 'GET', body, headers = {}, signal } = options;

  const token = localStorage.getItem('access_token');

  const config = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...headers,
    },
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  if (signal) {
    config.signal = signal;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, config);

  if (response.status === 401) {
    localStorage.removeItem('access_token');
    if (typeof window !== 'undefined') {
      const returnTo = window.location.pathname + window.location.search;
      window.dispatchEvent(
        new CustomEvent('auth:logout', { detail: { returnTo } })
      );
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: 'An unexpected error occurred.',
    }));

    // Handle validation errors (arrays) vs single error messages
    let errorMessage = 'An unexpected error occurred.';

    if (error.detail) {
      if (Array.isArray(error.detail)) {
        // FastAPI validation errors - extract user-friendly messages
        errorMessage = error.detail
          .map((err) => err.msg || err.message || 'Validation error')
          .join(', ');
      } else {
        // Single error message
        errorMessage = error.detail;
      }
    }

    const errObj = new Error(errorMessage);
    errObj.status = response.status;
    throw errObj;
  }

  return response.json();
}

/**
 * Shorthand for GET requests.
 * @param {string} endpoint - API path.
 * @param {Object} [options] - Additional options (e.g., { signal }).
 * @returns {Promise<Object>} Parsed response.
 */
export const get = (endpoint, options = {}) => apiRequest(endpoint, options);

/**
 * Shorthand for POST requests.
 * @param {string} endpoint - API path.
 * @param {Object} body - Request body.
 * @param {Object} [options] - Additional options (e.g., { signal }).
 * @returns {Promise<Object>} Parsed response.
 */
export const post = (endpoint, body, options = {}) =>
  apiRequest(endpoint, { ...options, method: 'POST', body });

/**
 * Shorthand for PATCH requests.
 * @param {string} endpoint - API path.
 * @param {Object} body - Request body.
 * @param {Object} [options] - Additional options (e.g., { signal }).
 * @returns {Promise<Object>} Parsed response.
 */
export const patch = (endpoint, body, options = {}) =>
  apiRequest(endpoint, { ...options, method: 'PATCH', body });

/**
 * Shorthand for DELETE requests.
 * @param {string} endpoint - API path.
 * @param {Object} [options] - Additional options (e.g., { signal }).
 * @returns {Promise<Object>} Parsed response.
 */
export const del = (endpoint, options = {}) =>
  apiRequest(endpoint, { ...options, method: 'DELETE' });
