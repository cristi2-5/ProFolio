/**
 * @vitest-environment jsdom
 *
 * Tests for AuthContext / AuthProvider / ProtectedRoute.
 *
 * We mock the API client (`get`/`post`) so login + initial /auth/me calls
 * never touch a real backend. A tiny consumer component renders the
 * context's exposed state into the DOM, where Testing Library can
 * assert on it.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

// Mock BEFORE importing the provider so its useCallback closures pick
// up the mocked functions.
vi.mock('../api/client', () => ({
  get: vi.fn(),
  post: vi.fn(),
  apiRequest: vi.fn(),
}));

import { get, post } from '../api/client';
import {
  AuthProvider,
  ProtectedRoute,
  useAuth,
} from '../contexts/AuthContext';

/** Renders the auth state in a way the test can read back. */
function Consumer() {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{isLoading ? 'loading' : 'ready'}</span>
      <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
      <span data-testid="email">{user?.email ?? ''}</span>
      <button
        type="button"
        onClick={() => login('alice@example.com', 'pw12345678')}
      >
        do-login
      </button>
      <button type="button" onClick={logout}>
        do-logout
      </button>
    </div>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('renders children once the initial loading check completes', async () => {
    // No token → initializeAuth short-circuits to "not loading, not authed".
    render(
      <MemoryRouter>
        <AuthProvider>
          <Consumer />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('ready');
    });
    expect(screen.getByTestId('auth')).toHaveTextContent('no');
    expect(get).not.toHaveBeenCalled();
  });

  it('login() populates the user in context', async () => {
    post.mockResolvedValueOnce({ access_token: 'tkn' }); // /auth/login
    get.mockResolvedValueOnce({ email: 'alice@example.com', id: 1 }); // /auth/me

    render(
      <MemoryRouter>
        <AuthProvider>
          <Consumer />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByTestId('loading')).toHaveTextContent('ready')
    );

    await act(async () => {
      screen.getByRole('button', { name: 'do-login' }).click();
    });

    await waitFor(() => {
      expect(screen.getByTestId('auth')).toHaveTextContent('yes');
    });
    expect(screen.getByTestId('email')).toHaveTextContent('alice@example.com');
    expect(post).toHaveBeenCalledWith('/auth/login', {
      email: 'alice@example.com',
      password: 'pw12345678',
    });
    expect(localStorage.getItem('access_token')).toBe('tkn');
  });

  it('ProtectedRoute redirects unauthenticated users to /login', async () => {
    render(
      <MemoryRouter initialEntries={['/secret']}>
        <AuthProvider>
          <Routes>
            <Route
              path="/secret"
              element={
                <ProtectedRoute>
                  <p>secret content</p>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<p>login page</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('login page')).toBeInTheDocument();
    });
    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });

  it('window-level auth:logout event clears the user', async () => {
    // Seed an authed session, then dispatch the global event the API
    // client fires on a 401, and assert state resets.
    localStorage.setItem('access_token', 'tkn');
    get.mockResolvedValueOnce({ email: 'alice@example.com', id: 1 });

    render(
      <MemoryRouter>
        <AuthProvider>
          <Consumer />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth')).toHaveTextContent('yes');
    });

    await act(async () => {
      window.dispatchEvent(
        new CustomEvent('auth:logout', { detail: { returnTo: '/jobs' } })
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('auth')).toHaveTextContent('no');
    });
    expect(localStorage.getItem('access_token')).toBeNull();
  });
});
