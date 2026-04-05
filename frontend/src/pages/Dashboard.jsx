/**
 * Dashboard Page — Main application view with real data integration.
 *
 * Displays job matches, match scores, job preferences, and quick actions.
 * Serves as the landing page after authentication with live API integration.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import JobPreferences from '../components/JobPreferences';
import { get, post } from '../api/client';

/**
 * Dashboard page component with real backend integration.
 *
 * Features:
 * - Real-time stats from backend APIs
 * - Job preferences configuration
 * - Resume upload integration
 * - Job scanning trigger
 * - Dynamic content based on user profile completion
 *
 * @returns {JSX.Element} The dashboard page.
 */
function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    jobsFound: 0,
    avgMatchScore: 0,
    cvsOptimized: 0,
    interviewsPrepped: 0,
    resumeUploaded: false,
    preferencesSet: false,
  });
  const [showPreferences, setShowPreferences] = useState(false);
  const [scanning, setScanning] = useState(false);

  /**
   * Fetch dashboard statistics.
   */
  const fetchStats = async () => {
    try {
      setLoading(true);

      // Fetch resumes count
      const resumeData = await get('/resumes');
      const resumeCount = resumeData.resumes?.length || 0;

      // Try to fetch job preferences
      let preferencesSet = false;
      try {
        const prefsData = await get('/jobs/preferences');
        preferencesSet = !!prefsData.preferences;
      } catch (err) {
        // 404 expected for users without preferences
        preferencesSet = false;
      }

      // Try to fetch jobs count
      let jobsData = { total_count: 0, jobs: [] };
      try {
        jobsData = await get('/jobs');
      } catch (err) {
        // Might fail if no preferences set
        jobsData = { total_count: 0, jobs: [] };
      }

      // Calculate average match score
      const avgScore = jobsData.jobs?.length > 0
        ? jobsData.jobs.reduce((sum, job) => sum + (job.match_score || 0), 0) / jobsData.jobs.length
        : 0;

      // Count optimized CVs and interview prep
      const optimizedCount = jobsData.jobs?.filter(job => job.optimized_cv).length || 0;
      const interviewCount = jobsData.jobs?.filter(job => job.interview_prep).length || 0;

      setStats({
        jobsFound: jobsData.total_count || 0,
        avgMatchScore: Math.round(avgScore),
        cvsOptimized: optimizedCount,
        interviewsPrepped: interviewCount,
        resumeUploaded: resumeCount > 0,
        preferencesSet,
      });

      // Show preferences if not set and resume is uploaded
      if (resumeCount > 0 && !preferencesSet) {
        setShowPreferences(true);
      }

    } catch (err) {
      console.error('Failed to fetch dashboard stats:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Trigger job scanning manually.
   */
  const triggerJobScan = async () => {
    if (!stats.resumeUploaded || !stats.preferencesSet) {
      return;
    }

    try {
      setScanning(true);
      await post('/jobs/scan');

      // Refresh stats after scan
      setTimeout(() => {
        fetchStats();
      }, 2000);

    } catch (err) {
      console.error('Failed to trigger job scan:', err);
    } finally {
      setScanning(false);
    }
  };

  /**
   * Handle successful preferences save.
   */
  const handlePreferencesSaved = () => {
    setShowPreferences(false);
    fetchStats();

    // Automatically trigger job scan after preferences are set
    if (stats.resumeUploaded) {
      setTimeout(() => {
        triggerJobScan();
      }, 1000);
    }
  };

  /**
   * Load dashboard data on mount.
   */
  useEffect(() => {
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '50vh',
      }}>
        <div
          style={{
            width: '40px',
            height: '40px',
            border: '4px solid var(--color-border)',
            borderTop: '4px solid var(--color-accent)',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
          }}
        />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="header-bar">
        <div>
          <h2>Welcome back, {user?.full_name?.split(' ')[0] || 'User'}!</h2>
          <p
            style={{
              color: 'var(--color-text-secondary)',
              marginTop: 'var(--space-1)',
            }}
          >
            Your AI-powered job hunting command center
          </p>
        </div>
        <div className="header-actions" style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button
            className="btn btn-secondary"
            onClick={() => navigate('/resumes')}
          >
            📄 Manage Resumes
          </button>
          <button
            className="btn btn-primary"
            onClick={triggerJobScan}
            disabled={!stats.resumeUploaded || !stats.preferencesSet || scanning}
            title={
              !stats.resumeUploaded
                ? 'Upload a resume first'
                : !stats.preferencesSet
                ? 'Set job preferences first'
                : 'Scan for new jobs'
            }
          >
            {scanning ? '⏳ Scanning...' : '🔍 Find Jobs'}
          </button>
        </div>
      </div>

      {/* Profile Completion Alert */}
      {(!stats.resumeUploaded || !stats.preferencesSet) && (
        <div
          style={{
            background: 'var(--color-info-bg)',
            border: '1px solid var(--color-info)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-4)',
            marginBottom: 'var(--space-6)',
            color: 'var(--color-info)',
          }}
        >
          <h4 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-medium)', marginBottom: 'var(--space-2)' }}>
            Complete Your Profile
          </h4>
          <div style={{ display: 'grid', gap: 'var(--space-2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <span style={{ fontSize: 'var(--font-size-lg)' }}>
                {stats.resumeUploaded ? '✅' : '⭕'}
              </span>
              <span>Upload and parse your resume</span>
              {!stats.resumeUploaded && (
                <button
                  onClick={() => navigate('/resumes')}
                  style={{
                    marginLeft: 'auto',
                    background: 'none',
                    border: 'none',
                    color: 'var(--color-accent)',
                    cursor: 'pointer',
                    fontSize: 'var(--font-size-sm)',
                    textDecoration: 'underline',
                  }}
                >
                  Go to Resumes
                </button>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <span style={{ fontSize: 'var(--font-size-lg)' }}>
                {stats.preferencesSet ? '✅' : '⭕'}
              </span>
              <span>Set job search preferences</span>
              {!stats.preferencesSet && (
                <button
                  onClick={() => setShowPreferences(true)}
                  style={{
                    marginLeft: 'auto',
                    background: 'none',
                    border: 'none',
                    color: 'var(--color-accent)',
                    cursor: 'pointer',
                    fontSize: 'var(--font-size-sm)',
                    textDecoration: 'underline',
                  }}
                >
                  Set Now
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Job Preferences Section */}
      {showPreferences && (
        <div style={{ marginBottom: 'var(--space-8)' }}>
          <JobPreferences onPreferencesSaved={handlePreferencesSaved} />
        </div>
      )}

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
          value={stats.jobsFound.toString()}
          subtext={stats.jobsFound > 0 ? "Jobs matched to your profile" : "Set preferences to find jobs"}
          color="var(--color-info)"
        />
        <StatsCard
          icon="🎯"
          label="Avg. Match Score"
          value={stats.avgMatchScore > 0 ? `${stats.avgMatchScore}%` : "—"}
          subtext={stats.avgMatchScore > 0 ? "Your profile compatibility" : "Upload CV to begin"}
          color="var(--color-accent)"
        />
        <StatsCard
          icon="📝"
          label="CVs Optimized"
          value={stats.cvsOptimized.toString()}
          subtext="Per-job tailored CVs"
          color="var(--color-success)"
        />
        <StatsCard
          icon="🎤"
          label="Interviews Prepped"
          value={stats.interviewsPrepped.toString()}
          subtext="Questions & cheat sheets"
          color="var(--color-warning)"
        />
      </div>

      {/* Job Listings or Setup Guide */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
          <h3
            style={{
              fontSize: 'var(--font-size-lg)',
              fontWeight: 'var(--font-weight-semibold)',
            }}
          >
            Recent Job Matches
          </h3>
          {stats.jobsFound > 0 && (
            <button
              className="btn btn-secondary"
              onClick={() => navigate('/jobs')}
              style={{ padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--font-size-sm)' }}
            >
              View All Jobs
            </button>
          )}
        </div>

        {stats.jobsFound === 0 ? (
          <div
            style={{
              textAlign: 'center',
              padding: 'var(--space-16) 0',
              color: 'var(--color-text-muted)',
            }}
          >
            <p
              style={{
                fontSize: 'var(--font-size-3xl)',
                marginBottom: 'var(--space-4)',
              }}
            >
              🚀
            </p>
            <p
              style={{
                fontSize: 'var(--font-size-lg)',
                fontWeight: 'var(--font-weight-medium)',
              }}
            >
              {!stats.resumeUploaded
                ? 'Upload your resume to get started'
                : !stats.preferencesSet
                ? 'Set your job preferences to find matches'
                : 'No jobs found yet'}
            </p>
            <p style={{ marginTop: 'var(--space-2)' }}>
              {!stats.resumeUploaded || !stats.preferencesSet
                ? 'Complete your profile setup above to activate the Job Scanner agent.'
                : 'The Job Scanner will run daily to find new matches. Click "Find Jobs" to scan now.'}
            </p>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
            <p style={{ color: 'var(--color-text-secondary)' }}>
              {stats.jobsFound} job{stats.jobsFound !== 1 ? 's' : ''} found and ready for review!
            </p>
          </div>
        )}
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
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}
      >
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
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}
      >
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
