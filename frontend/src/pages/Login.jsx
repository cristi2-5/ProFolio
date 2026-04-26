/**
 * Login Page — Integrated Authentication View.
 *
 * Provides real email/password authentication with backend integration.
 * Handles login, registration, and validation with proper error display.
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth, consumeReturnTo } from '../contexts/AuthContext';

/**
 * Login/Registration page component with full backend integration.
 *
 * Features:
 * - Real authentication via AuthContext
 * - Form validation and error display
 * - Auto-redirect to dashboard on success
 * - Password strength validation for registration
 * - Responsive design with loading states
 *
 * @returns {JSX.Element} The login page.
 */
function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register, isLoading, error, clearError, isAuthenticated } =
    useAuth();

  const resolveRedirectTarget = () => {
    const fromState = location.state?.from?.pathname;
    if (fromState && fromState !== '/login') {
      const search = location.state?.from?.search || '';
      return fromState + search;
    }
    const stored = consumeReturnTo();
    if (stored && stored !== '/login') return stored;
    return '/dashboard';
  };

  // Ref used to auto-focus the email field on mount for keyboard users.
  const emailRef = useRef(null);

  // Form state
  const [isRegister, setIsRegister] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    seniority_level: 'junior',
    niche: '',
  });
  const [validationErrors, setValidationErrors] = useState({});

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(resolveRedirectTarget(), { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, navigate]);

  // Clear errors when switching modes
  useEffect(() => {
    clearError();
    setValidationErrors({});
  }, [isRegister, clearError]);

  // Auto-focus email on mount so keyboard users can start typing immediately.
  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  /**
   * Handle form field changes.
   */
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Clear field-specific validation error
    if (validationErrors[name]) {
      setValidationErrors((prev) => ({ ...prev, [name]: null }));
    }
  };

  /**
   * Validate form fields client-side.
   */
  const validateForm = (trimmedEmail) => {
    const errors = {};

    // Email validation (against the trimmed value the server will see)
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!trimmedEmail) {
      errors.email = 'Email is required';
    } else if (!emailRegex.test(trimmedEmail)) {
      errors.email = 'Please enter a valid email address';
    }

    // Password validation — never trim the password value, but reject all-whitespace
    if (!formData.password) {
      errors.password = 'Password is required';
    } else if (formData.password.trim().length === 0) {
      errors.password = 'Password cannot be only whitespace';
    } else if (formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters';
    }

    // Registration-specific validation
    if (isRegister) {
      if (!formData.full_name.trim()) {
        errors.full_name = 'Full name is required';
      }

      // Password strength for registration
      if (formData.password && !errors.password) {
        const passwordErrors = [];
        if (!/[A-Z]/.test(formData.password)) {
          passwordErrors.push('one uppercase letter');
        }
        if (!/[0-9]/.test(formData.password)) {
          passwordErrors.push('one number');
        }
        if (passwordErrors.length > 0) {
          errors.password = `Password must contain ${passwordErrors.join(' and ')}`;
        }
      }

      // Niche required for mid/senior levels
      if (
        ['mid', 'senior'].includes(formData.seniority_level) &&
        !formData.niche.trim()
      ) {
        errors.niche = 'Specialization is required for mid/senior levels';
      }
    }

    return errors;
  };

  /**
   * Handle form submission.
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;
    clearError();

    const trimmedEmail = formData.email.trim();
    const trimmedFullName = formData.full_name.trim();
    const trimmedNiche = formData.niche.trim();

    // Validate form
    const errors = validateForm(trimmedEmail);
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    try {
      if (isRegister) {
        // Registration
        await register({
          email: trimmedEmail,
          password: formData.password,
          full_name: trimmedFullName,
          seniority_level: formData.seniority_level,
          niche: trimmedNiche || null,
        });
      } else {
        // Login
        await login(trimmedEmail, formData.password);
      }

      // Success - AuthContext will handle redirect via useEffect
    } catch (err) {
      // Error is handled by AuthContext and displayed via error state
      if (import.meta.env.DEV) {
        console.error('Auth error:', err);
      }
    }
  };

  /**
   * Toggle between login and register modes.
   */
  const toggleMode = () => {
    setIsRegister(!isRegister);
    setFormData({
      email: '',
      password: '',
      full_name: '',
      seniority_level: 'junior',
      niche: '',
    });
    setValidationErrors({});
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

        {/* Global Error */}
        {error && (
          <div
            style={{
              background: 'var(--color-error-bg)',
              border: '1px solid var(--color-error)',
              borderRadius: 'var(--radius-md)',
              padding: 'var(--space-3)',
              marginBottom: 'var(--space-4)',
              color: 'var(--color-error)',
              fontSize: 'var(--font-size-sm)',
            }}
          >
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} aria-busy={isLoading}>
          {isRegister && (
            <>
              <div style={{ marginBottom: 'var(--space-4)' }}>
                <label htmlFor="full_name" style={labelStyle}>
                  Full Name
                </label>
                <input
                  type="text"
                  id="full_name"
                  name="full_name"
                  value={formData.full_name}
                  onChange={handleChange}
                  placeholder="Enter your full name"
                  aria-describedby={
                    validationErrors.full_name ? 'full_name-error' : undefined
                  }
                  style={{
                    ...inputStyle,
                    ...(validationErrors.full_name && errorInputStyle),
                  }}
                />
                {validationErrors.full_name && (
                  <div id="full_name-error" style={errorStyle}>
                    {validationErrors.full_name}
                  </div>
                )}
              </div>

              <div style={{ marginBottom: 'var(--space-4)' }}>
                <label htmlFor="seniority_level" style={labelStyle}>
                  Experience Level
                </label>
                <select
                  id="seniority_level"
                  name="seniority_level"
                  value={formData.seniority_level}
                  onChange={handleChange}
                  style={inputStyle}
                >
                  <option value="intern">Intern</option>
                  <option value="junior">Junior</option>
                  <option value="mid">Mid-level</option>
                  <option value="senior">Senior</option>
                </select>
              </div>

              {['mid', 'senior'].includes(formData.seniority_level) && (
                <div style={{ marginBottom: 'var(--space-4)' }}>
                  <label htmlFor="niche" style={labelStyle}>
                    Specialization
                  </label>
                  <input
                    type="text"
                    id="niche"
                    name="niche"
                    value={formData.niche}
                    onChange={handleChange}
                    placeholder="e.g., Frontend Development, DevOps"
                    aria-describedby={
                      validationErrors.niche ? 'niche-error' : undefined
                    }
                    style={{
                      ...inputStyle,
                      ...(validationErrors.niche && errorInputStyle),
                    }}
                  />
                  {validationErrors.niche && (
                    <div id="niche-error" style={errorStyle}>
                      {validationErrors.niche}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          <div style={{ marginBottom: 'var(--space-4)' }}>
            <label htmlFor="email" style={labelStyle}>
              Email
            </label>
            <input
              ref={emailRef}
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="your@email.com"
              required
              aria-describedby={
                validationErrors.email ? 'email-error' : undefined
              }
              style={{
                ...inputStyle,
                ...(validationErrors.email && errorInputStyle),
              }}
            />
            {validationErrors.email && (
              <div id="email-error" style={errorStyle}>
                {validationErrors.email}
              </div>
            )}
          </div>

          <div style={{ marginBottom: 'var(--space-6)' }}>
            <label htmlFor="password" style={labelStyle}>
              Password
            </label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder={
                isRegister
                  ? 'Min. 8 chars, 1 upper, 1 number'
                  : 'Enter your password'
              }
              required
              minLength={8}
              aria-describedby={
                validationErrors.password ? 'password-error' : undefined
              }
              style={{
                ...inputStyle,
                ...(validationErrors.password && errorInputStyle),
              }}
            />
            {validationErrors.password && (
              <div id="password-error" style={errorStyle}>
                {validationErrors.password}
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="btn btn-primary"
            id="auth-submit-btn"
            style={{
              width: '100%',
              padding: 'var(--space-4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 'var(--space-2)',
              opacity: isLoading ? 0.7 : 1,
              cursor: isLoading ? 'not-allowed' : 'pointer',
            }}
          >
            {isLoading && (
              <div
                style={{
                  width: '16px',
                  height: '16px',
                  border: '2px solid transparent',
                  borderTop: '2px solid currentColor',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                }}
              />
            )}
            {isLoading
              ? isRegister
                ? 'Creating Account...'
                : 'Signing In...'
              : isRegister
                ? 'Create Account'
                : 'Sign In'}
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
          <hr
            style={{
              flex: 1,
              border: 'none',
              borderTop: '1px solid var(--color-border)',
            }}
          />
          <span
            style={{
              color: 'var(--color-text-muted)',
              fontSize: 'var(--font-size-sm)',
            }}
          >
            or continue with
          </span>
          <hr
            style={{
              flex: 1,
              border: 'none',
              borderTop: '1px solid var(--color-border)',
            }}
          />
        </div>

        {/* OAuth Buttons — Phase 3 */}
        <div style={{ display: 'flex', gap: 'var(--space-4)' }}>
          <button
            className="btn btn-secondary"
            style={{ flex: 1 }}
            id="google-oauth-btn"
            disabled
            title="Coming in Phase 3"
          >
            🔵 Google
          </button>
          <button
            className="btn btn-secondary"
            style={{ flex: 1 }}
            id="linkedin-oauth-btn"
            disabled
            title="Coming in Phase 3"
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
            onClick={toggleMode}
            disabled={isLoading}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-accent)',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              fontWeight: 'var(--font-weight-semibold)',
              fontSize: 'inherit',
              fontFamily: 'inherit',
              opacity: isLoading ? 0.5 : 1,
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

// Styles
const labelStyle = {
  display: 'block',
  fontSize: 'var(--font-size-sm)',
  fontWeight: 'var(--font-weight-medium)',
  color: 'var(--color-text-secondary)',
  marginBottom: 'var(--space-2)',
};

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

const errorInputStyle = {
  borderColor: 'var(--color-error)',
};

const errorStyle = {
  color: 'var(--color-error)',
  fontSize: 'var(--font-size-sm)',
  marginTop: 'var(--space-1)',
};

export default Login;
