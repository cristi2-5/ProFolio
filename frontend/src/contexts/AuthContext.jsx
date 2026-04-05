/**
 * AuthContext — Global Authentication State Management.
 *
 * Provides authentication state and methods throughout the app.
 * Handles JWT token persistence, user profile fetching, and auto-login.
 */

import { createContext, useContext, useEffect, useReducer } from 'react';
import { get, post } from '../api/client';

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

  // Initialize authentication on app load
  useEffect(() => {
    initializeAuth();
  }, []);

  /**
   * Initialize authentication by checking for existing token and fetching user profile.
   */
  const initializeAuth = async () => {
    const token = localStorage.getItem('access_token');

    if (!token) {
      dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: false });
      return;
    }

    try {
      // Validate token by fetching current user profile
      const user = await get('/auth/me');
      dispatch({ type: AUTH_ACTIONS.SET_USER, payload: user });
    } catch (error) {
      // Token is invalid, clear it
      localStorage.removeItem('access_token');
      dispatch({ type: AUTH_ACTIONS.LOGOUT });
    }
  };

  /**
   * Login with email and password.
   */
  const login = async (email, password) => {
    dispatch({ type: AUTH_ACTIONS.SET_LOADING, payload: true });

    try {
      // Authenticate user
      const { access_token } = await post('/auth/login', { email, password });

      // Store token
      localStorage.setItem('access_token', access_token);

      // Fetch user profile
      const user = await get('/auth/me');
      dispatch({ type: AUTH_ACTIONS.SET_USER, payload: user });

      return { success: true, user };
    } catch (error) {
      dispatch({ type: AUTH_ACTIONS.SET_ERROR, payload: error.message });
      throw error;
    }
  };

  /**
   * Register new user account.
   */
  const register = async (userData) => {
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

      return { success: true, user };
    } catch (error) {
      dispatch({ type: AUTH_ACTIONS.SET_ERROR, payload: error.message });
      throw error;
    }
  };

  /**
   * Logout user and clear session.
   */
  const logout = () => {
    localStorage.removeItem('access_token');
    dispatch({ type: AUTH_ACTIONS.LOGOUT });
  };

  /**
   * Clear error state.
   */
  const clearError = () => {
    dispatch({ type: AUTH_ACTIONS.CLEAR_ERROR });
  };

  /**
   * Update user profile in context (after profile changes).
   */
  const updateUser = (userData) => {
    dispatch({ type: AUTH_ACTIONS.SET_USER, payload: { ...state.user, ...userData } });
  };

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

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Custom hook to use the AuthContext.
 *
 * @returns {Object} Authentication state and methods.
 * @throws {Error} If used outside of AuthProvider.
 */
export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}

/**
 * ProtectedRoute component that requires authentication.
 */
export function ProtectedRoute({ children, redirectTo = '/login' }) {
  const { isAuthenticated, isLoading } = useAuth();

  // Show loading spinner while checking authentication
  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        background: 'var(--color-bg-primary)',
      }}>
        <div style={{
          width: '40px',
          height: '40px',
          border: '4px solid var(--color-border)',
          borderTop: '4px solid var(--color-accent)',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
        }} />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    window.location.href = redirectTo;
    return null;
  }

  return children;
}

export default AuthContext;