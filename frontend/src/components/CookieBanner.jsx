import { useState } from 'react';
import { Link } from 'react-router-dom';

const STORAGE_KEY = 'cookie_consent';

function CookieBanner() {
  const [visible, setVisible] = useState(
    () => !localStorage.getItem(STORAGE_KEY)
  );

  const persist = (analytics) => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        analytics,
        functional: true,
        timestamp: new Date().toISOString(),
      })
    );
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-label="Cookie consent"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        background: 'rgba(10, 14, 30, 0.95)',
        borderTop: '1px solid var(--color-border)',
        padding: 'var(--space-4) var(--space-6)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        flexWrap: 'wrap',
        gap: 'var(--space-4)',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      <p
        style={{
          margin: 0,
          flex: '1 1 320px',
          fontSize: 'var(--font-size-sm)',
          color: 'var(--color-text-secondary)',
        }}
      >
        We use cookies to keep you logged in. We don&apos;t run analytics yet,
        but when we do, you&apos;ll be able to opt out.{' '}
        <Link to="/cookies">Cookie policy</Link>
      </p>
      <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => persist(false)}
        >
          Functional only
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => persist(true)}
        >
          Accept all
        </button>
      </div>
    </div>
  );
}

export default CookieBanner;
