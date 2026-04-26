/**
 * @vitest-environment jsdom
 *
 * Tests for the Login page form behavior.
 *
 * AuthContext is mocked so we can assert exactly what arguments the
 * page passes into `login()` (this catches regressions like "we forgot
 * to trim the email" or "we send whitespace passwords through").
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const loginMock = vi.fn();
const registerMock = vi.fn();
const clearErrorMock = vi.fn();

vi.mock('../contexts/AuthContext', () => ({
  // Page imports useAuth + consumeReturnTo from this module.
  useAuth: () => ({
    login: loginMock,
    register: registerMock,
    isLoading: false,
    error: null,
    clearError: clearErrorMock,
    isAuthenticated: false,
  }),
  consumeReturnTo: () => null,
}));

import Login from '../pages/Login';

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  );
}

describe('Login page', () => {
  beforeEach(() => {
    loginMock.mockReset();
    registerMock.mockReset();
    clearErrorMock.mockReset();
  });

  it('shows validation errors for whitespace-only email and short password', async () => {
    const { container } = renderLogin();

    // Whitespace-only email (passes the HTML `required` check because
    // it has length, but trims to empty so our app-level validator
    // rejects it). Bypass HTML5 constraint validation by dispatching
    // submit on the form directly — type=email + minLength would
    // otherwise block fireEvent.click on the submit button in jsdom.
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: '   ' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'short' },
    });

    const form = container.querySelector('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });
    expect(loginMock).not.toHaveBeenCalled();
  });

  it('rejects whitespace-only password', async () => {
    const { container } = renderLogin();

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: 'alice@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: '        ' },
    });

    fireEvent.submit(container.querySelector('form'));

    await waitFor(() => {
      expect(
        screen.getByText(/password cannot be only whitespace/i)
      ).toBeInTheDocument();
    });
    expect(loginMock).not.toHaveBeenCalled();
  });

  it('calls login() with trimmed email and untrimmed password on valid submit', async () => {
    loginMock.mockResolvedValueOnce({ success: true });
    const { container } = renderLogin();

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: '  alice@example.com  ' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'pw12345678' },
    });

    fireEvent.submit(container.querySelector('form'));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledTimes(1);
    });
    expect(loginMock).toHaveBeenCalledWith('alice@example.com', 'pw12345678');
  });

  it('disables the submit button while isLoading', async () => {
    // Re-mock the module for this case so isLoading=true.
    vi.resetModules();
    vi.doMock('../contexts/AuthContext', () => ({
      useAuth: () => ({
        login: loginMock,
        register: registerMock,
        isLoading: true,
        error: null,
        clearError: clearErrorMock,
        isAuthenticated: false,
      }),
      consumeReturnTo: () => null,
    }));

    const { default: LoginReloaded } = await import('../pages/Login');
    render(
      <MemoryRouter>
        <LoginReloaded />
      </MemoryRouter>
    );

    const submit = screen.getByRole('button', { name: /signing in/i });
    expect(submit).toBeDisabled();
  });
});
