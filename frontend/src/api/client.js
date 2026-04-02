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
  const { method = 'GET', body, headers = {} } = options;

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

  const response = await fetch(`${API_BASE}${endpoint}`, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: 'An unexpected error occurred.',
    }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Shorthand for GET requests.
 * @param {string} endpoint - API path.
 * @returns {Promise<Object>} Parsed response.
 */
export const get = (endpoint) => apiRequest(endpoint);

/**
 * Shorthand for POST requests.
 * @param {string} endpoint - API path.
 * @param {Object} body - Request body.
 * @returns {Promise<Object>} Parsed response.
 */
export const post = (endpoint, body) =>
  apiRequest(endpoint, { method: 'POST', body });

/**
 * Shorthand for PATCH requests.
 * @param {string} endpoint - API path.
 * @param {Object} body - Request body.
 * @returns {Promise<Object>} Parsed response.
 */
export const patch = (endpoint, body) =>
  apiRequest(endpoint, { method: 'PATCH', body });

/**
 * Shorthand for DELETE requests.
 * @param {string} endpoint - API path.
 * @returns {Promise<Object>} Parsed response.
 */
export const del = (endpoint) => apiRequest(endpoint, { method: 'DELETE' });
