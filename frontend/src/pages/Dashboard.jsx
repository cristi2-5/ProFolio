/**
 * Dashboard Page — Main application view.
 *
 * Displays job matches, match scores, and quick actions.
 * Serves as the landing page after authentication.
 */

/**
 * Dashboard page component.
 *
 * Renders:
 * - Welcome header with user context.
 * - Stats cards (jobs found, match score, interviews prepped).
 * - Placeholder for job listings table.
 *
 * @returns {JSX.Element} The dashboard page.
 */
function Dashboard() {
  return (
    <div className="animate-fade-in">
      <div className="header-bar">
        <div>
          <h2>Dashboard</h2>
          <p style={{ color: 'var(--color-text-secondary)', marginTop: 'var(--space-1)' }}>
            Your AI-powered job hunting command center
          </p>
        </div>
        <div className="header-actions">
          <button className="btn btn-primary" id="upload-cv-btn">
            📄 Upload CV
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 'var(--space-6)',
          marginBottom: 'var(--space-8)',
        }}
      >
        <StatsCard
          icon="🔍"
          label="Jobs Found"
          value="—"
          subtext="Job Scanner is ready"
          color="var(--color-info)"
        />
        <StatsCard
          icon="🎯"
          label="Avg. Match Score"
          value="—"
          subtext="Upload a CV to begin"
          color="var(--color-accent)"
        />
        <StatsCard
          icon="📝"
          label="CVs Optimized"
          value="0"
          subtext="Per-job tailored CVs"
          color="var(--color-success)"
        />
        <StatsCard
          icon="🎤"
          label="Interviews Prepped"
          value="0"
          subtext="Questions & cheat sheets"
          color="var(--color-warning)"
        />
      </div>

      {/* Job Listings Placeholder */}
      <div className="card">
        <h3
          style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-semibold)',
            marginBottom: 'var(--space-4)',
          }}
        >
          Recent Job Matches
        </h3>
        <div
          style={{
            textAlign: 'center',
            padding: 'var(--space-16) 0',
            color: 'var(--color-text-muted)',
          }}
        >
          <p style={{ fontSize: 'var(--font-size-3xl)', marginBottom: 'var(--space-4)' }}>
            🚀
          </p>
          <p style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-medium)' }}>
            No jobs scanned yet
          </p>
          <p style={{ marginTop: 'var(--space-2)' }}>
            Upload your CV and set job preferences to activate the Job Scanner
            agent.
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * Stats card component for dashboard metrics.
 *
 * @param {Object} props - Component props.
 * @param {string} props.icon - Emoji icon.
 * @param {string} props.label - Metric label.
 * @param {string} props.value - Metric value.
 * @param {string} props.subtext - Description text.
 * @param {string} props.color - Accent color for the icon.
 * @returns {JSX.Element} A styled stat card.
 */
function StatsCard({ icon, label, value, subtext, color }) {
  return (
    <div className="card" style={{ cursor: 'default' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 'var(--radius-lg)',
            background: `${color}15`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 'var(--font-size-xl)',
          }}
        >
          {icon}
        </div>
        <div>
          <p
            style={{
              color: 'var(--color-text-muted)',
              fontSize: 'var(--font-size-xs)',
              fontWeight: 'var(--font-weight-medium)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            {label}
          </p>
          <p
            style={{
              fontSize: 'var(--font-size-2xl)',
              fontWeight: 'var(--font-weight-bold)',
              color: 'var(--color-text-primary)',
            }}
          >
            {value}
          </p>
          <p
            style={{
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-size-xs)',
              marginTop: 'var(--space-1)',
            }}
          >
            {subtext}
          </p>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
