import { Link } from 'react-router-dom';

function NotFound() {
  return (
    <div
      className="animate-fade-in"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        padding: 'var(--space-6)',
      }}
    >
      <div
        className="card"
        style={{ maxWidth: '500px', width: '100%', textAlign: 'center' }}
      >
        <h2 style={{ marginBottom: 'var(--space-4)' }}>
          404 — Page not found
        </h2>
        <p style={{ marginBottom: 'var(--space-6)' }}>
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <Link to="/dashboard" className="btn btn-primary">
          Go to dashboard
        </Link>
      </div>
    </div>
  );
}

export default NotFound;
