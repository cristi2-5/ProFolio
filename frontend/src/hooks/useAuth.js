/**
 * useAuth Hook — Authentication state management.
 *
 * Provides login/logout/register functions and current user state.
 * Stores JWT token in localStorage for session persistence.
 *
 * TODO: Migrate to React Context in Phase 2 for global state.
 */

import { useCallback, useState } from 'react';
import { post } from '../api/client';

/**
 * Authentication hook for managing user sessions.
 *
 * @returns {Object} Auth state and methods.
 * @returns {Object|null} .user - Current user data or null.
 * @returns {boolean} .isAuthenticated - Whether user is logged in.
 * @returns {boolean} .isLoading - Whether an auth operation is in progress.
 * @returns {string|null} .error - Current error message or null.
 * @returns {Function} .login - Login function(email, password).
 * @returns {Function} .register - Register function(userData).
 * @returns {Function} .logout - Logout function().
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const login = useCallback(async (email, password) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await post('/auth/login', { email, password });
      localStorage.setItem('access_token', data.access_token);
      setUser({ email }); // TODO: Fetch full user profile in Phase 2
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (userData) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await post('/auth/register', userData);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    setUser(null);
  }, []);

  return {
    user,
    isAuthenticated: !!user,
    isLoading,
    error,
    login,
    register,
    logout,
  };
}
