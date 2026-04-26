/**
 * AuthContext — Global Authentication State Management.
 *
 * Provides authentication state and methods throughout the app.
 * Handles JWT token persistence, user profile fetching, and auto-login.
 */

import {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useCallback,
  useRef,
} from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { get, post } from '../api/client';

const RETURN_TO_KEY = 'auth.returnTo';

function decodeJWT(token) {
  try {
    const base64 = token.split('.')[1];
    const padded = base64.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

function getTokenExpMs(token) {
  const decoded = decodeJWT(token);
  return decoded?.exp ? decoded.exp * 1000 : null;
}

// Auth state management using useReducer
const initialState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
};

// Action types
const AUTH_ACTIONS = {
  SET_LOADING: 'SET_LOADING',
  SET_USER: 'SET_USER',
  SET_ERROR: 'SET_ERROR',
  LOGOUT: 'LOGOUT',
  CLEAR_ERROR: 'CLEAR_ERROR',
};

// Auth reducer
function authReducer(state, action) {
  switch (action.type) {
    case AUTH_ACTIONS.SET_LOADING:
      return { ...state, isLoading: action.payload, error: null };

    case AUTH_ACTIONS.SET_USER:
      return {
        ...state,
        user: action.payload,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      };

    case AUTH_ACTIONS.SET_ERROR:
      return {
        ...state,
        error: action.payload,
        isLoading: false,
      };

    case AUTH_ACTIONS.LOGOUT:
      return {
        ...state,
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      };

    case AUTH_ACTIONS.CLEAR_ERROR:
      return { ...state, error: null };

    default:
      return state;
  }
}

// Create context
const AuthContext = createContext(null);

/**
 * AuthProvider component that wraps the app with authentication state.
 */
export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialState);
  const expiryTimerRef = useRef(null);

  const clearExpiryTimer = useCallback(() => {
    if (expiryTimerRef.current) {
      clearTimeout(expiryTimerRef.current);
      expiryTimerRef.current = null;
    }
  }, []);

  /**
   * Logout user and clear session.
   */
  const logout = useCallback(() => {
    clearExpiryTimer();
    localStorage.removeItem('access_token');
    dispatch({ type: AUTH_ACTIONS.LOGOUT });
  }, [clearExpiryTimer]);

  const scheduleExpiryLogout = useCallback(
    (token) => {
      clearExpiryTimer();
      const expMs = getTokenExpMs(token);
      if (!expMs) return;
      const delay = expMs - Date.now() + 1000;
      if (delay <= 0) {
        logout();
        return;
      }
      expiryTimerRef.current = setTimeout(() => {
        logout();
      }, delay);
    },
    [clearExpiryTimer, logout]
  );

  /**
   * Initialize authentication by checking for existing token and fetching user profile.
   */
  const initializeAuth = useCallback(async () => {
    const token = localStorage.getItem('access_token');

    if (!token) {
      dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: false });
      return;
    }

    // Proactively reject expired tokens before hitting the server
    const expMs = getTokenExpMs(token);
    if (expMs && expMs <= Date.now()) {
      localStorage.removeItem('access_token');
      dispatch({ type: AUTH_ACTIONS.LOGOUT });
      return;
    }

    try {
      // Validate token by fetching current user profile
      const user = await get('/auth/me');
      dispatch({ type: AUTH_ACTIONS.SET_USER, payload: user });
      scheduleExpiryLogout(token);
    } catch {
      // Token is invalid, clear it
      localStorage.removeItem('access_token');
      dispatch({ type: AUTH_ACTIONS.LOGOUT });
    }
  }, [scheduleExpiryLogout]);

  // Initialize authentication on app load
  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  // Listen for global auth:logout dispatched from the API client (e.g. on 401).
  useEffect(() => {
    const handler = (event) => {
      const returnTo = event?.detail?.returnTo;
      if (returnTo && returnTo !== '/login') {
        sessionStorage.setItem(RETURN_TO_KEY, returnTo);
      }
      logout();
    };
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, [logout]);

  // Clear timer on unmount
  useEffect(() => clearExpiryTimer, [clearExpiryTimer]);

  /**
   * Login with email and password.
   */
  const login = useCallback(
    async (email, password) => {
      dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: true });

      try {
        // Authenticate user
        const { access_token } = await post('/auth/login', { email, password });

        // Store token
        localStorage.setItem('access_token', access_token);

        // Fetch user profile
        const user = await get('/auth/me');
        dispatch({ type: AUTH_ACTIONS.SET_USER, payload: user });
        scheduleExpiryLogout(access_token);

        return { success: true, user };
      } catch (error) {
        dispatch({ type: AUTH_ACTIONS.SET_ERROR, payload: error.message });
        throw error;
      }
    },
    [scheduleExpiryLogout]
  );

  /**
   * Register new user account.
   */
  const register = useCallback(
    async (userData) => {
      dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: true });

      try {
        // Create user account
        const user = await post('/auth/register', userData);

        // Auto-login after registration
        const { access_token } = await post('/auth/login', {
          email: userData.email,
          password: userData.password,
        });

        // Store token and set user
        localStorage.setItem('access_token', access_token);
        dispatch({ type: AUTH_ACTIONS.SET_USER, payload: user });
        scheduleExpiryLogout(access_token);

        return { success: true, user };
      } catch (error) {
        dispatch({ type: AUTH_ACTIONS.SET_ERROR, payload: error.message });
        throw error;
      }
    },
    [scheduleExpiryLogout]
  );

  /**
   * Clear error state.
   */
  const clearError = useCallback(() => {
    dispatch({ type: AUTH_ACTIONS.CLEAR_ERROR });
  }, []);

  /**
   * Update user profile in context (after profile changes).
   */
  const updateUser = useCallback(
    (userData) => {
      dispatch({
        type: AUTH_ACTIONS.SET_USER,
        payload: { ...state.user, ...userData },
      });
    },
    [state.user]
  );

  const value = {
    // State
    user: state.user,
    isAuthenticated: state.isAuthenticated,
    isLoading: state.isLoading,
    error: state.error,

    // Actions
    login,
    register,
    logout,
    clearError,
    updateUser,
    initializeAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Custom hook to use the AuthContext.
 *
 * @returns {Object} Authentication state and methods.
 * @throws {Error} If used outside of AuthProvider.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}

/**
 * Read and clear the pending returnTo path stored from a 401-triggered logout.
 *
 * @returns {string|null}
 */
// eslint-disable-next-line react-refresh/only-export-components
export function consumeReturnTo() {
  const value = sessionStorage.getItem(RETURN_TO_KEY);
  if (value) sessionStorage.removeItem(RETURN_TO_KEY);
  return value;
}

/**
 * ProtectedRoute component that requires authentication.
 */
export function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking authentication
  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          background: 'var(--color-bg-primary)',
        }}
      >
        <div
          style={{
            width: '40px',
            height: '40px',
            border: '4px solid var(--color-border)',
            borderTop: '4px solid var(--color-accent)',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
          }}
        />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

export default AuthContext;
