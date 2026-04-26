/**
 * @vitest-environment jsdom
 *
 * Tests for the 404 NotFound page.
 *
 * Wrapped in a MemoryRouter so the <Link> renders the correct anchor
 * without needing the full app router.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NotFound from '../pages/NotFound';

describe('NotFound', () => {
  it('renders the 404 message', () => {
    render(
      <MemoryRouter>
        <NotFound />
      </MemoryRouter>
    );

    expect(screen.getByText(/404 — Page not found/i)).toBeInTheDocument();
    expect(
      screen.getByText(/the page you're looking for doesn't exist/i)
    ).toBeInTheDocument();
  });

  it('exposes a link back to /dashboard', () => {
    render(
      <MemoryRouter>
        <NotFound />
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: /go to dashboard/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/dashboard');
  });
});
