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

const ONBOARDING_DISMISSED_KEY = 'profolio.onboarding.dismissed';
const ONBOARDING_FIRST_SCAN_KEY = 'profolio.onboarding.first_scan_done';

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
  const [onboardingDismissed, setOnboardingDismissed] = useState(
    () => localStorage.getItem(ONBOARDING_DISMISSED_KEY) === '1'
  );
  const [firstScanDone, setFirstScanDone] = useState(
    () => localStorage.getItem(ONBOARDING_FIRST_SCAN_KEY) === '1'
  );

  /**
   * Fetch dashboard statistics.
   */
  const fetchStats = async (signal) => {
    try {
      setLoading(true);

      // Fetch resumes count (backend returns list directly)
      const resumeData = await get('/resumes/', { signal });
      const resumeCount = Array.isArray(resumeData)
        ? resumeData.length
        : resumeData.resumes?.length || 0;

      // Try to fetch job preferences
      let preferencesSet = false;
      try {
        const prefsData = await get('/jobs/preferences', { signal });
        preferencesSet = prefsData && Object.keys(prefsData).length > 0;
      } catch (err) {
        if (err.name === 'AbortError') throw err;
        // 404 expected for users without preferences
        preferencesSet = false;
      }

      // Try to fetch jobs count
      let jobsData = { total_count: 0, jobs: [] };
      try {
        jobsData = await get('/jobs/', { signal });
      } catch (err) {
        if (err.name === 'AbortError') throw err;
        // Might fail if no preferences set
        jobsData = { total_count: 0, jobs: [] };
      }

      // Calculate average match score
      const avgScore =
        jobsData.jobs?.length > 0
          ? jobsData.jobs.reduce(
              (sum, job) => sum + (job.match_score || 0),
              0
            ) / jobsData.jobs.length
          : 0;

      // Count optimized CVs and interview prep
      const optimizedCount =
        jobsData.jobs?.filter((job) => job.optimized_cv).length || 0;
      const interviewCount =
        jobsData.jobs?.filter((job) => job.interview_prep).length || 0;

      setStats({
        jobsFound: jobsData.total_count || 0,
        avgMatchScore: Math.round(avgScore),
        cvsOptimized: optimizedCount,
        interviewsPrepped: interviewCount,
        resumeUploaded: resumeCount > 0,
        preferencesSet,
      });

      // If the backend already has jobs, treat the first scan as completed —
      // covers users created on a prior device or before this flag existed.
      if ((jobsData.total_count || 0) > 0) {
        localStorage.setItem(ONBOARDING_FIRST_SCAN_KEY, '1');
        setFirstScanDone(true);
      }

      // Show preferences if not set and resume is uploaded
      if (resumeCount > 0 && !preferencesSet) {
        setShowPreferences(true);
      }
    } catch (err) {
      if (err.name === 'AbortError') return;
      if (import.meta.env.DEV) {
        console.error('Failed to fetch dashboard stats:', err);
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  /**
   * Trigger job scanning manually.
   */
  const triggerJobScan = async () => {
    if (scanning) return;
    if (!stats.resumeUploaded || !stats.preferencesSet) {
      return;
    }

    try {
      setScanning(true);
      await post('/jobs/scan');

      localStorage.setItem(ONBOARDING_FIRST_SCAN_KEY, '1');
      setFirstScanDone(true);

      // Refresh stats after scan
      setTimeout(() => {
        fetchStats();
      }, 2000);
    } catch (err) {
      if (import.meta.env.DEV) {
        console.error('Failed to trigger job scan:', err);
      }
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
    const ctrl = new AbortController();
    fetchStats(ctrl.signal);
    return () => ctrl.abort();
  }, []);

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '50vh',
        }}
      >
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
        <div
          className="header-actions"
          style={{ display: 'flex', gap: 'var(--space-3)' }}
        >
          <button
            className="btn btn-secondary"
            onClick={() => navigate('/resumes')}
          >
            📄 Manage Resumes
          </button>
          <button
            className="btn btn-primary"
            onClick={triggerJobScan}
            disabled={
              !stats.resumeUploaded || !stats.preferencesSet || scanning
            }
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

      {/* Onboarding checklist — combined empty-state CTA for first-run users */}
      {(() => {
        const allDone =
          stats.resumeUploaded && stats.preferencesSet && firstScanDone;
        if (allDone || onboardingDismissed) return null;

        const steps = [
          {
            key: 'resume',
            done: stats.resumeUploaded,
            label: 'Upload your CV',
            description:
              'Add a PDF or DOCX so our agents can match jobs and write tailored CVs.',
            actionLabel: 'Go to Resumes',
            onAction: () => navigate('/resumes'),
          },
          {
            key: 'preferences',
            done: stats.preferencesSet,
            label: 'Set your job preferences (recommended)',
            description:
              'Tell us your target role, location, and skills for personalised matching. Optional — you can scan with our default "developer" query first.',
            actionLabel: 'Set preferences',
            onAction: () => setShowPreferences(true),
            // No longer gated on resume — preferences are independent.
            disabled: false,
          },
          {
            key: 'scan',
            done: firstScanDone,
            label: "Run your first job scan",
            description:
              'We pull live openings from Adzuna and rank them against your CV. Works without a CV or preferences (match score will be 0).',
            actionLabel: scanning ? 'Scanning…' : 'Scan jobs',
            onAction: triggerJobScan,
            // Only blocked while a scan is in flight.
            disabled: scanning,
          },
        ];
        const completed = steps.filter((s) => s.done).length;

        return (
          <div
            style={{
              background: 'var(--color-info-bg)',
              border: '1px solid var(--color-info)',
              borderRadius: 'var(--radius-lg)',
              padding: 'var(--space-4)',
              marginBottom: 'var(--space-6)',
              color: 'var(--color-text-primary)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 'var(--space-3)',
                gap: 'var(--space-3)',
              }}
            >
              <h4
                style={{
                  fontSize: 'var(--font-size-lg)',
                  fontWeight: 'var(--font-weight-medium)',
                  color: 'var(--color-info)',
                }}
              >
                Welcome — let's get you set up ({completed}/3)
              </h4>
            </div>
            <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
              {steps.map((step, idx) => (
                <div
                  key={step.key}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 'var(--space-3)',
                    padding: 'var(--space-3)',
                    background: step.done
                      ? 'var(--color-bg-secondary)'
                      : 'var(--color-bg-primary)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border)',
                    opacity: step.disabled && !step.done ? 0.7 : 1,
                  }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      fontSize: 'var(--font-size-lg)',
                      lineHeight: 1,
                      marginTop: '2px',
                    }}
                  >
                    {step.done ? '☑' : '☐'}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontWeight: 'var(--font-weight-medium)',
                        marginBottom: 'var(--space-1)',
                        textDecoration: step.done ? 'line-through' : 'none',
                        color: step.done
                          ? 'var(--color-text-muted)'
                          : 'var(--color-text-primary)',
                      }}
                    >
                      Step {idx + 1} — {step.label}
                    </div>
                    {!step.done && (
                      <p
                        style={{
                          fontSize: 'var(--font-size-sm)',
                          color: 'var(--color-text-secondary)',
                          margin: 0,
                        }}
                      >
                        {step.description}
                      </p>
                    )}
                  </div>
                  {!step.done && (
                    <button
                      type="button"
                      onClick={step.onAction}
                      disabled={step.disabled}
                      className="btn btn-primary"
                      style={{
                        padding: 'var(--space-2) var(--space-3)',
                        fontSize: 'var(--font-size-sm)',
                        whiteSpace: 'nowrap',
                        opacity: step.disabled ? 0.5 : 1,
                      }}
                    >
                      {step.actionLabel}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* "All set!" confirmation — dismissible once */}
      {stats.resumeUploaded &&
        stats.preferencesSet &&
        firstScanDone &&
        !onboardingDismissed && (
          <div
            style={{
              background: 'var(--color-success-bg)',
              border: '1px solid var(--color-success)',
              borderRadius: 'var(--radius-lg)',
              padding: 'var(--space-3) var(--space-4)',
              marginBottom: 'var(--space-6)',
              color: 'var(--color-success)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 'var(--space-3)',
            }}
          >
            <span>✅ All set! Your job hunting workflow is live.</span>
            <button
              type="button"
              onClick={() => {
                localStorage.setItem(ONBOARDING_DISMISSED_KEY, '1');
                setOnboardingDismissed(true);
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'inherit',
                cursor: 'pointer',
                fontSize: 'var(--font-size-lg)',
              }}
              aria-label="Dismiss"
            >
              ×
            </button>
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
          subtext={
            stats.jobsFound > 0
              ? 'Jobs matched to your profile'
              : 'Set preferences to find jobs'
          }
          color="var(--color-info)"
        />
        <StatsCard
          icon="🎯"
          label="Avg. Match Score"
          value={stats.avgMatchScore > 0 ? `${stats.avgMatchScore}%` : '—'}
          subtext={
            stats.avgMatchScore > 0
              ? 'Your profile compatibility'
              : 'Upload CV to begin'
          }
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
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 'var(--space-4)',
          }}
        >
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
              style={{
                padding: 'var(--space-2) var(--space-3)',
                fontSize: 'var(--font-size-sm)',
              }}
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
              {stats.jobsFound} job{stats.jobsFound !== 1 ? 's' : ''} found and
              ready for review!
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
