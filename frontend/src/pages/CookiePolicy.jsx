function CookiePolicy() {
  return (
    <div
      className="animate-fade-in card"
      style={{ maxWidth: '800px', margin: '0 auto' }}
    >
      <h2 style={{ marginBottom: 'var(--space-6)' }}>Cookie Policy</h2>
      <p style={{ marginBottom: 'var(--space-4)' }}>
        We use functional cookies and local storage to keep you logged in
        across sessions. These are essential to provide the service.
      </p>
      <p style={{ marginBottom: 'var(--space-4)' }}>
        We do not currently run analytics or advertising trackers. If we add
        analytics in the future, you will be able to opt out via the cookie
        banner.
      </p>
      <p style={{ marginBottom: 'var(--space-4)' }}>
        We collect: account email, hashed password, uploaded CV files, your job
        preferences. We use this data to provide the service. We do not share.
      </p>
      <p>
        You may delete your account at any time via Settings → Delete account,
        which will remove all associated cookie and storage data.
      </p>
    </div>
  );
}

export default CookiePolicy;
