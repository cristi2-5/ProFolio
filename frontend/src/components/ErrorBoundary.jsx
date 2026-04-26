import { Component } from 'react';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    if (import.meta.env.DEV) {
      console.error('ErrorBoundary caught:', error, errorInfo);
    }
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 'var(--space-6)',
            background: 'var(--color-bg-primary)',
          }}
        >
          <div className="card" style={{ maxWidth: '600px', width: '100%' }}>
            <h2 style={{ marginBottom: 'var(--space-4)' }}>
              Something went wrong
            </h2>
            <p style={{ marginBottom: 'var(--space-6)' }}>
              An unexpected error occurred. Try reloading.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={this.handleReload}
            >
              Reload page
            </button>
            {import.meta.env.DEV && (
              <details style={{ marginTop: 'var(--space-6)' }}>
                <summary style={{ cursor: 'pointer' }}>Error details</summary>
                <pre
                  style={{
                    marginTop: 'var(--space-3)',
                    padding: 'var(--space-3)',
                    background: 'var(--color-bg-card)',
                    borderRadius: 'var(--radius-md)',
                    overflow: 'auto',
                    fontSize: 'var(--font-size-xs)',
                  }}
                >
                  {this.state.error?.stack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
