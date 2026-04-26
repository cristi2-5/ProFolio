function Terms() {
  return (
    <div
      className="animate-fade-in card"
      style={{ maxWidth: '800px', margin: '0 auto' }}
    >
      <h2 style={{ marginBottom: 'var(--space-6)' }}>Terms of Service</h2>
      <p style={{ marginBottom: 'var(--space-4)' }}>
        By using this service, you agree to these terms. The service is
        provided on an &quot;as is&quot; basis without warranties of any kind.
      </p>
      <p style={{ marginBottom: 'var(--space-4)' }}>
        We collect: account email, hashed password, uploaded CV files, your job
        preferences. We use this data to provide the service. We do not share.
      </p>
      <p style={{ marginBottom: 'var(--space-4)' }}>
        You are responsible for the accuracy of the information you provide,
        including CV content and job preferences. You may delete your account
        at any time via Settings → Delete account.
      </p>
      <p>
        We reserve the right to suspend accounts that violate these terms or
        misuse the service.
      </p>
    </div>
  );
}

export default Terms;
