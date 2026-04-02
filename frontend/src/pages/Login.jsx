/**
 * Login Page — Authentication view.
 *
 * Provides email/password login form with a registration link.
 * OAuth buttons (Google, LinkedIn) are stubbed for Phase 2.
 */

import { useState } from 'react';

/**
 * Login/Registration page component.
 *
 * Features:
 * - Email + password form with client-side validation.
 * - Toggle between login and registration modes.
 * - OAuth provider buttons (Google, LinkedIn) — Phase 2.
 *
 * @returns {JSX.Element} The login page.
 */
function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  /**
   * Handle form submission.
   * @param {Event} e - Form submit event.
   */
  const handleSubmit = (e) => {
    e.preventDefault();
    // TODO: Implement auth API call in Phase 2
    console.log(isRegister ? 'Register' : 'Login', { email, password });
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--color-bg-primary)',
        padding: 'var(--space-4)',
      }}
    >
      <div
        className="card animate-fade-in"
        style={{
          width: '100%',
          maxWidth: 420,
          padding: 'var(--space-10)',
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-8)' }}>
          <h1
            style={{
              fontSize: 'var(--font-size-3xl)',
              fontWeight: 'var(--font-weight-extrabold)',
              marginBottom: 'var(--space-2)',
            }}
          >
            <span className="text-gradient">Auto</span>Apply
          </h1>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            {isRegister
              ? 'Create your account to get started'
              : 'Sign in to your job hunting dashboard'}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {isRegister && (
            <div style={{ marginBottom: 'var(--space-4)' }}>
              <label
                htmlFor="fullname"
                style={{
                  display: 'block',
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 'var(--font-weight-medium)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-2)',
                }}
              >
                Full Name
              </label>
              <input
                type="text"
                id="fullname"
                placeholder="Enter your full name"
                style={inputStyle}
              />
            </div>
          )}
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <label
              htmlFor="email"
              style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-medium)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-2)',
              }}
            >
              Email
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              required
              style={inputStyle}
            />
          </div>
          <div style={{ marginBottom: 'var(--space-6)' }}>
            <label
              htmlFor="password"
              style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-medium)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-2)',
              }}
            >
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min. 8 characters"
              required
              minLength={8}
              style={inputStyle}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            id="auth-submit-btn"
            style={{ width: '100%', padding: 'var(--space-4)' }}
          >
            {isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        {/* Divider */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-4)',
            margin: 'var(--space-6) 0',
          }}
        >
          <hr style={{ flex: 1, border: 'none', borderTop: '1px solid var(--color-border)' }} />
          <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-sm)' }}>
            or continue with
          </span>
          <hr style={{ flex: 1, border: 'none', borderTop: '1px solid var(--color-border)' }} />
        </div>

        {/* OAuth Buttons — Phase 2 */}
        <div style={{ display: 'flex', gap: 'var(--space-4)' }}>
          <button
            className="btn btn-secondary"
            style={{ flex: 1 }}
            id="google-oauth-btn"
            disabled
            title="Coming in Phase 2"
          >
            🔵 Google
          </button>
          <button
            className="btn btn-secondary"
            style={{ flex: 1 }}
            id="linkedin-oauth-btn"
            disabled
            title="Coming in Phase 2"
          >
            🔗 LinkedIn
          </button>
        </div>

        {/* Toggle */}
        <p
          style={{
            textAlign: 'center',
            marginTop: 'var(--space-6)',
            color: 'var(--color-text-secondary)',
            fontSize: 'var(--font-size-sm)',
          }}
        >
          {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
          <button
            type="button"
            onClick={() => setIsRegister(!isRegister)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-accent)',
              cursor: 'pointer',
              fontWeight: 'var(--font-weight-semibold)',
              fontSize: 'inherit',
              fontFamily: 'inherit',
            }}
            id="toggle-auth-mode-btn"
          >
            {isRegister ? 'Sign in' : 'Create one'}
          </button>
        </p>
      </div>
    </div>
  );
}

/** @type {React.CSSProperties} Shared input field styles. */
const inputStyle = {
  width: '100%',
  padding: 'var(--space-3) var(--space-4)',
  background: 'var(--color-bg-primary)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--color-text-primary)',
  fontSize: 'var(--font-size-base)',
  fontFamily: 'var(--font-family)',
  outline: 'none',
  transition: 'border-color var(--transition-fast)',
};

export default Login;
