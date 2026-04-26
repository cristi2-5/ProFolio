/**
 * @vitest-environment jsdom
 *
 * Tests for the top-level ErrorBoundary.
 *
 * The boundary is the last line of defense against an unrecoverable render
 * crash — if a child throws during render, the user must still see a
 * helpful fallback (and the app must not white-screen). These tests pin
 * that contract: throwing children render the fallback, healthy children
 * pass through unchanged.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import ErrorBoundary from '../components/ErrorBoundary';

/** A component that always throws — used to trigger the boundary. */
function Throw() {
  throw new Error('boom');
}

/** A component that renders cleanly — used to assert pass-through. */
function Ok() {
  return <p>healthy child</p>;
}

describe('ErrorBoundary', () => {
  // React logs caught render errors to console.error; silence it so the
  // test output stays clean and we still see real failures.
  let consoleSpy;
  afterEach(() => {
    consoleSpy?.mockRestore();
  });

  it('renders the fallback UI when a child throws', () => {
    consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Throw />
      </ErrorBoundary>
    );

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /reload page/i })
    ).toBeInTheDocument();
  });

  it('renders children unchanged when nothing throws', () => {
    render(
      <ErrorBoundary>
        <Ok />
      </ErrorBoundary>
    );

    expect(screen.getByText('healthy child')).toBeInTheDocument();
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
  });
});
