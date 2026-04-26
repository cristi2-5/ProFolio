function Privacy() {
  return (
    <div
      className="animate-fade-in card"
      style={{ maxWidth: '800px', margin: '0 auto' }}
    >
      <h2 style={{ marginBottom: 'var(--space-6)' }}>Privacy Policy</h2>
      <p style={{ marginBottom: 'var(--space-4)' }}>
        We collect: account email, hashed password, uploaded CV files, your job
        preferences. We use this data to provide the service.
      </p>
      <p style={{ marginBottom: 'var(--space-4)' }}>
        We do not share your data with third parties. Your information is
        stored securely and used solely to power your job search experience.
      </p>
      <p style={{ marginBottom: 'var(--space-4)' }}>
        You may delete your account at any time via Settings → Delete account.
        Deletion is permanent and removes all associated data.
      </p>
      <p>
        For any privacy-related questions or requests, please contact us
        through the support channels.
      </p>
    </div>
  );
}

export default Privacy;
