/**
 * GDPR Consent Modal — Phase 6 / Epic 5 / US 5.1.
 *
 * Shown the first time a user lands on the Benchmarks page without
 * having made an explicit opt-in / opt-out decision. The component is
 * purely presentational — the parent owns the persisted state and decides
 * when to show it (e.g. when `opt_in_status === null` or the user has
 * never dismissed the notice).
 *
 * Requirements covered:
 *   - Explicit consent required before any personal data enters the
 *     benchmarking pool.
 *   - Equal visual weight for Opt-in and Opt-out actions so the user
 *     isn't nudged one way (GDPR "freely given").
 *   - Spells out exactly which fields are extracted post-consent.
 */

import { useEffect } from 'react';

/**
 * Props
 *   - open: boolean — whether the modal is visible.
 *   - onOptIn: () => void — user clicks "Join benchmarking".
 *   - onOptOut: () => void — user clicks "Not now".
 *   - onDismiss: () => void — backdrop click / ESC. Treated as dismiss,
 *                             NOT consent. The parent should remember the
 *                             dismissal so we don't pester on every load.
 *   - submitting: boolean — disables buttons while the backend call is in
 *                           flight to prevent duplicate submissions.
 */
function GdprConsentModal({
  open,
  onOptIn,
  onOptOut,
  onDismiss,
  submitting = false,
}) {
  useEffect(() => {
    if (!open) return undefined;
    const handleKey = (event) => {
      if (event.key === 'Escape') onDismiss?.();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onDismiss]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="gdpr-consent-title"
      onClick={onDismiss}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        padding: 'var(--space-4)',
      }}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          background: 'var(--color-bg-primary)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)',
          maxWidth: '560px',
          width: '100%',
          padding: 'var(--space-6)',
          boxShadow: 'var(--shadow-lg, 0 8px 24px rgba(0,0,0,0.25))',
        }}
      >
        <header style={{ marginBottom: 'var(--space-4)' }}>
          <p
            style={{
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-accent)',
              fontWeight: 'var(--font-weight-semibold)',
              marginBottom: 'var(--space-2)',
            }}
          >
            🔒 Privacy notice · GDPR
          </p>
          <h2
            id="gdpr-consent-title"
            style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-bold)',
              marginBottom: 'var(--space-2)',
            }}
          >
            Join competitive benchmarking?
          </h2>
          <p style={{ color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
            Benchmarking compares your CV against other candidates at the same
            seniority level (and niche, for Mid/Senior). It's the only way to
            see where you sit in the market — and it's optional.
          </p>
        </header>

        <section
          style={{
            background: 'var(--color-bg-secondary)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-4)',
            marginBottom: 'var(--space-4)',
            fontSize: 'var(--font-size-sm)',
          }}
        >
          <p
            style={{
              fontWeight: 'var(--font-weight-semibold)',
              marginBottom: 'var(--space-2)',
            }}
          >
            If you opt in, we extract only:
          </p>
          <ul
            style={{
              paddingLeft: 'var(--space-5)',
              display: 'grid',
              gap: 'var(--space-1)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-3)',
            }}
          >
            <li>Your seniority level (Intern / Junior / Mid / Senior)</li>
            <li>Your niche (Frontend / Backend / DevOps / Data …)</li>
            <li>Your total years of experience</li>
            <li>The list of technical skills on your CV</li>
          </ul>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            This subset is decoupled from your user account before it reaches
            any peer calculation. Name, email, company names, roles, and free
            text never leave your profile.
          </p>
        </section>

        <section
          style={{
            fontSize: 'var(--font-size-sm)',
            color: 'var(--color-text-muted)',
            marginBottom: 'var(--space-5)',
            lineHeight: 1.5,
          }}
        >
          You can opt out at any time from this page — opting out deletes your
          anonymised contribution from future aggregations and does not affect
          the rest of the platform.
        </section>

        <footer
          style={{
            display: 'flex',
            gap: 'var(--space-3)',
            justifyContent: 'flex-end',
            flexWrap: 'wrap',
          }}
        >
          <button
            type="button"
            onClick={onOptOut}
            disabled={submitting}
            className="btn btn-secondary"
            style={{ minWidth: '140px', opacity: submitting ? 0.6 : 1 }}
          >
            Not now
          </button>
          <button
            type="button"
            onClick={onOptIn}
            disabled={submitting}
            className="btn btn-primary"
            style={{ minWidth: '180px', opacity: submitting ? 0.6 : 1 }}
          >
            {submitting ? 'Saving…' : 'Join benchmarking'}
          </button>
        </footer>
      </div>
    </div>
  );
}

export default GdprConsentModal;
