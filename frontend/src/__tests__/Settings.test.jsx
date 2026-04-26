/**
 * @vitest-environment jsdom
 *
 * Tests for the Settings page profile-edit form.
 *
 * AuthContext + the API client are mocked so we can assert the exact
 * payload sent to PATCH /auth/me (only changed fields) and that
 * updateUser() is invoked with the server's response.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const updateUserMock = vi.fn();
const logoutMock = vi.fn();
const patchMock = vi.fn();
const apiRequestMock = vi.fn();

const fakeUser = {
  id: 'u-1',
  email: 'me@example.com',
  full_name: 'Original Name',
  seniority_level: 'mid',
  niche: 'Backend',
  benchmark_opt_in: false,
};

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: fakeUser,
    logout: logoutMock,
    updateUser: updateUserMock,
  }),
}));

vi.mock('../api/client', () => ({
  patch: (...args) => patchMock(...args),
  apiRequest: (...args) => apiRequestMock(...args),
}));

import Settings from '../pages/Settings';

function renderSettings() {
  return render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>
  );
}

describe('Settings page — profile form', () => {
  beforeEach(() => {
    updateUserMock.mockReset();
    logoutMock.mockReset();
    patchMock.mockReset();
    apiRequestMock.mockReset();
  });

  it('pre-populates the form from the user context', () => {
    renderSettings();

    expect(screen.getByLabelText(/full name/i)).toHaveValue('Original Name');
    expect(screen.getByLabelText(/^email$/i)).toHaveValue('me@example.com');
    expect(screen.getByLabelText(/seniority level/i)).toHaveValue('mid');
    expect(screen.getByLabelText(/niche/i)).toHaveValue('Backend');
  });

  it('submits only the changed fields to PATCH /auth/me', async () => {
    patchMock.mockResolvedValueOnce({ ...fakeUser, full_name: 'Updated Name' });
    renderSettings();

    fireEvent.change(screen.getByLabelText(/full name/i), {
      target: { value: 'Updated Name' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledTimes(1);
    });
    expect(patchMock).toHaveBeenCalledWith('/auth/me', {
      full_name: 'Updated Name',
    });
  });

  it('shows a confirmation message and calls updateUser on success', async () => {
    const updated = { ...fakeUser, niche: 'Frontend' };
    patchMock.mockResolvedValueOnce(updated);
    renderSettings();

    fireEvent.change(screen.getByLabelText(/niche/i), {
      target: { value: 'Frontend' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(updateUserMock).toHaveBeenCalledWith(updated);
    });
    expect(await screen.findByText(/profile updated/i)).toBeInTheDocument();
  });

  it('shows an error message when the server returns 409', async () => {
    const err = new Error('User with this email already exists.');
    err.status = 409;
    patchMock.mockRejectedValueOnce(err);

    renderSettings();

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: 'taken@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /that email is already in use/i
      );
    });
    expect(updateUserMock).not.toHaveBeenCalled();
  });

  it('shows an inline error and skips PATCH when nothing changed', async () => {
    renderSettings();

    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/no changes to save/i);
    });
    expect(patchMock).not.toHaveBeenCalled();
  });
});
