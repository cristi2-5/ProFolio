import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest, patch } from '../api/client';

const PROFILE_FIELDS = ['full_name', 'email', 'seniority_level', 'niche'];

function buildProfileForm(user) {
  return {
    full_name: user?.full_name ?? '',
    email: user?.email ?? '',
    seniority_level: user?.seniority_level ?? '',
    niche: user?.niche ?? '',
  };
}

function diffProfile(form, user) {
  const payload = {};
  for (const field of PROFILE_FIELDS) {
    const current = user?.[field] ?? '';
    const next = form[field] ?? '';
    if (current !== next) {
      // Send empty string as null for nullable fields except email/full_name
      if (next === '' && (field === 'seniority_level' || field === 'niche')) {
        payload[field] = null;
      } else {
        payload[field] = next;
      }
    }
  }
  return payload;
}

function Settings() {
  const { user, logout, updateUser } = useAuth();
  const navigate = useNavigate();

  // Profile form state
  const [profileForm, setProfileForm] = useState(() => buildProfileForm(user));
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [profileSuccess, setProfileSuccess] = useState(false);
  const firstProfileInputRef = useRef(null);

  // Delete-account state
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const passwordRef = useRef(null);

  // Auto-focus the first profile input on initial mount.
  useEffect(() => {
    firstProfileInputRef.current?.focus();
  }, []);

  // Re-sync the profile form when the user object changes (e.g. on initial
  // load when user is null and then populated).
  useEffect(() => {
    setProfileForm(buildProfileForm(user));
  }, [user]);

  // Auto-dismiss success toast after 3s.
  useEffect(() => {
    if (!profileSuccess) return undefined;
    const timer = setTimeout(() => setProfileSuccess(false), 3000);
    return () => clearTimeout(timer);
  }, [profileSuccess]);

  // Auto-focus the password input when the confirmation form opens so a
  // keyboard user can type immediately without an extra Tab.
  useEffect(() => {
    if (confirming) {
      passwordRef.current?.focus();
    }
  }, [confirming]);

  const handleProfileChange = (field) => (event) => {
    setProfileForm((prev) => ({ ...prev, [field]: event.target.value }));
  };

  const handleProfileSubmit = async (event) => {
    event.preventDefault();
    if (profileSaving) return;
    setProfileError(null);
    setProfileSuccess(false);

    const payload = diffProfile(profileForm, user);
    if (Object.keys(payload).length === 0) {
      setProfileError('No changes to save.');
      return;
    }

    setProfileSaving(true);
    try {
      const updated = await patch('/auth/me', payload);
      updateUser(updated);
      setProfileSuccess(true);
    } catch (err) {
      if (err.status === 409) {
        setProfileError('That email is already in use.');
      } else {
        setProfileError(err.message || 'Failed to update profile.');
      }
    } finally {
      setProfileSaving(false);
    }
  };

  const handleDelete = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await apiRequest('/auth/me', {
        method: 'DELETE',
        body: { password },
      });
      setSuccess(true);
      setTimeout(() => {
        logout();
        navigate('/login', { replace: true });
      }, 1200);
    } catch (err) {
      if (err.status === 401) {
        setError('Password incorrect');
      } else {
        setError(err.message || 'Failed to delete account.');
      }
      setSubmitting(false);
    }
  };

  const inputStyle = {
    padding: 'var(--space-3)',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--color-border)',
    background: 'var(--color-bg-card)',
    color: 'var(--color-text-primary)',
    width: '100%',
  };

  const formGroupStyle = {
    display: 'grid',
    gridTemplateColumns: '180px 1fr',
    alignItems: 'center',
    gap: 'var(--space-3)',
  };

  return (
    <div
      className="animate-fade-in"
      style={{
        maxWidth: '800px',
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-6)',
      }}
    >
      <div className="card">
        <h2 style={{ marginBottom: 'var(--space-4)' }}>Account Settings</h2>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          Logged in as: <strong>{user?.email}</strong>
        </p>
      </div>

      <section className="card" aria-labelledby="profile-heading">
        <h3 id="profile-heading" style={{ marginBottom: 'var(--space-3)' }}>
          Profile
        </h3>
        <p
          style={{
            marginBottom: 'var(--space-4)',
            color: 'var(--color-text-secondary)',
          }}
        >
          Update your display information. Email changes take effect
          immediately (verification is disabled in local development).
        </p>

        <form
          onSubmit={handleProfileSubmit}
          aria-busy={profileSaving}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-3)',
          }}
        >
          <div className="form-group" style={formGroupStyle}>
            <label
              htmlFor="full_name"
              style={{ fontSize: 'var(--font-size-sm)' }}
            >
              Full name
            </label>
            <input
              ref={firstProfileInputRef}
              id="full_name"
              type="text"
              autoComplete="name"
              value={profileForm.full_name}
              onChange={handleProfileChange('full_name')}
              aria-describedby={
                profileError ? 'full_name-error' : undefined
              }
              disabled={profileSaving}
              style={inputStyle}
            />
          </div>

          <div className="form-group" style={formGroupStyle}>
            <label htmlFor="email" style={{ fontSize: 'var(--font-size-sm)' }}>
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={profileForm.email}
              onChange={handleProfileChange('email')}
              aria-describedby={profileError ? 'email-error' : undefined}
              disabled={profileSaving}
              style={inputStyle}
            />
          </div>

          <div className="form-group" style={formGroupStyle}>
            <label
              htmlFor="seniority_level"
              style={{ fontSize: 'var(--font-size-sm)' }}
            >
              Seniority level
            </label>
            <select
              id="seniority_level"
              value={profileForm.seniority_level}
              onChange={handleProfileChange('seniority_level')}
              aria-describedby={
                profileError ? 'seniority_level-error' : undefined
              }
              disabled={profileSaving}
              style={inputStyle}
            >
              <option value="">— Not specified —</option>
              <option value="intern">Intern</option>
              <option value="junior">Junior</option>
              <option value="mid">Mid</option>
              <option value="senior">Senior</option>
            </select>
          </div>

          <div className="form-group" style={formGroupStyle}>
            <label htmlFor="niche" style={{ fontSize: 'var(--font-size-sm)' }}>
              Niche
            </label>
            <input
              id="niche"
              type="text"
              value={profileForm.niche}
              onChange={handleProfileChange('niche')}
              aria-describedby={profileError ? 'niche-error' : undefined}
              disabled={profileSaving}
              style={inputStyle}
            />
          </div>

          {profileError && (
            <div
              id="profile-error"
              role="alert"
              className="error-message"
              style={{
                padding: 'var(--space-3)',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#ef4444',
              }}
            >
              {profileError}
            </div>
          )}

          {profileSuccess && (
            <div
              role="status"
              className="success-message"
              style={{
                padding: 'var(--space-3)',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#10b981',
              }}
            >
              Profile updated
            </div>
          )}

          <div>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={profileSaving}
            >
              {profileSaving ? 'Saving...' : 'Save changes'}
            </button>
          </div>
        </form>
      </section>

      <div
        className="card"
        style={{ borderColor: 'var(--color-error, #ef4444)' }}
      >
        <h3 style={{ marginBottom: 'var(--space-3)' }}>Danger zone</h3>
        <h4 style={{ marginBottom: 'var(--space-3)' }}>Delete account</h4>
        <p style={{ marginBottom: 'var(--space-4)' }}>
          Permanently delete your account. This cannot be undone. All resumes,
          jobs, and benchmarks will be erased.
        </p>

        {success && (
          <div
            role="status"
            style={{
              padding: 'var(--space-3)',
              marginBottom: 'var(--space-4)',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#10b981',
            }}
          >
            Account deleted. Signing you out...
          </div>
        )}

        {!confirming && !success && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setConfirming(true)}
          >
            Delete my account
          </button>
        )}

        {confirming && !success && (
          <form
            onSubmit={handleDelete}
            aria-busy={submitting}
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-3)',
            }}
          >
            <label
              htmlFor="confirm-password"
              style={{ fontSize: 'var(--font-size-sm)' }}
            >
              Enter your password to confirm:
            </label>
            <input
              ref={passwordRef}
              id="confirm-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              aria-describedby={error ? 'confirm-password-error' : undefined}
              style={{
                padding: 'var(--space-3)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
                background: 'var(--color-bg-card)',
                color: 'var(--color-text-primary)',
              }}
            />
            {error && (
              <div
                id="confirm-password-error"
                role="alert"
                style={{
                  padding: 'var(--space-3)',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(239, 68, 68, 0.15)',
                  color: '#ef4444',
                }}
              >
                {error}
              </div>
            )}
            <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting || !password}
              >
                {submitting ? 'Deleting...' : 'Confirm delete'}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setConfirming(false);
                  setPassword('');
                  setError(null);
                }}
                disabled={submitting}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default Settings;
