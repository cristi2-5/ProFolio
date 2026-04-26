/**
 * Benchmarks Page — Competitive Analysis and Peer Comparisons.
 *
 * Displays all user benchmark scores with visualizations and insights.
 * Provides GDPR-compliant competitive analysis and skill development recommendations.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { get, patch } from '../api/client';
import GdprConsentModal from '../components/GdprConsentModal';

const CONSENT_SEEN_STORAGE_KEY = 'profolio.benchmark.consent_seen';

/**
 * Benchmarks page component.
 *
 * Features:
 * - Benchmark scores visualization
 * - Opt-in management for GDPR compliance
 * - Skill gap analysis across all benchmarks
 * - Performance trends over time
 * - Peer group comparisons
 *
 * @returns {JSX.Element} The benchmarks page.
 */
function Benchmarks() {
  const navigate = useNavigate();
  const { user, updateUser } = useAuth();

  const [loading, setLoading] = useState(true);
  const [benchmarks, setBenchmarks] = useState([]);
  const [recommendations, setRecommendations] = useState(null);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState(null);
  const [insufficientPeers, setInsufficientPeers] = useState(false);
  const [showConsentModal, setShowConsentModal] = useState(false);

  // Opt-in status lives in AuthContext (refreshed by login/register/updateUser).
  // Deriving it here instead of holding a duplicate state variable keeps the
  // two views from drifting if the context updates but the page doesn't.
  const optInStatus = user?.benchmark_opt_in ?? false;

  /**
   * Fetch user benchmarks and (if opted in) recommendations.
   */
  const fetchBenchmarks = async (signal) => {
    try {
      setLoading(true);
      setError(null);
      setInsufficientPeers(false);

      const optInData = await get('/auth/benchmark-opt-in', { signal });
      updateUser({ benchmark_opt_in: optInData.benchmark_opt_in });

      const consentSeen =
        localStorage.getItem(CONSENT_SEEN_STORAGE_KEY) === '1';
      if (!optInData.benchmark_opt_in && !consentSeen) {
        setShowConsentModal(true);
      }

      if (optInData.benchmark_opt_in) {
        let benchmarkData = { benchmarks: [] };
        let benchmarkInsufficient = false;
        try {
          benchmarkData = await get('/benchmarks/', { signal });
        } catch (err) {
          if (err.name === 'AbortError') throw err;
          if (err.status === 422) {
            benchmarkInsufficient = true;
            benchmarkData = { benchmarks: [] };
          } else {
            throw err;
          }
        }

        const recommendationData = await get('/benchmarks/recommendations', {
          signal,
        }).catch((err) => {
          if (err.name === 'AbortError') throw err;
          return null;
        });

        setBenchmarks(benchmarkData.benchmarks || []);
        setRecommendations(recommendationData);
        setInsufficientPeers(
          benchmarkInsufficient ||
            Boolean(recommendationData?.insufficient_peers)
        );
      } else {
        setBenchmarks([]);
        setRecommendations(null);
      }
    } catch (err) {
      if (err.name === 'AbortError') return;
      if (import.meta.env.DEV) {
        console.error('Failed to fetch benchmarks:', err);
      }
      setError(err.message || 'Failed to load benchmark data');
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  /**
   * Update benchmark opt-in status.
   */
  const updateOptInStatus = async (nextStatus) => {
    if (updating) return;
    try {
      setUpdating(true);
      setError(null);

      await patch('/auth/benchmark-opt-in', { benchmark_opt_in: nextStatus });
      updateUser({ benchmark_opt_in: nextStatus });
      localStorage.setItem(CONSENT_SEEN_STORAGE_KEY, '1');

      if (nextStatus) {
        await fetchBenchmarks();
      } else {
        setBenchmarks([]);
        setRecommendations(null);
      }
    } catch (err) {
      setError('Failed to update opt-in status: ' + err.message);
    } finally {
      setUpdating(false);
    }
  };

  const handleConsentAccept = async () => {
    setShowConsentModal(false);
    await updateOptInStatus(true);
  };

  const handleConsentDecline = () => {
    setShowConsentModal(false);
    localStorage.setItem(CONSENT_SEEN_STORAGE_KEY, '1');
  };

  /**
   * Calculate aggregate statistics.
   */
  const getAggregateStats = () => {
    if (benchmarks.length === 0) {
      return {
        avgScore: 0,
        highestScore: 0,
        lowestScore: 0,
        totalBenchmarks: 0,
      };
    }

    const scores = benchmarks.map((b) => b.score);
    return {
      avgScore: Math.round(
        scores.reduce((sum, score) => sum + score, 0) / scores.length
      ),
      highestScore: Math.max(...scores),
      lowestScore: Math.min(...scores),
      totalBenchmarks: benchmarks.length,
    };
  };

  /**
   * Load data on mount.
   */
  useEffect(() => {
    const ctrl = new AbortController();
    fetchBenchmarks(ctrl.signal);
    return () => ctrl.abort();
  }, []);

  const stats = getAggregateStats();

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
    <div
      style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: 'var(--space-6)',
      }}
    >
      <GdprConsentModal
        open={showConsentModal}
        submitting={updating}
        onOptIn={handleConsentAccept}
        onOptOut={handleConsentDecline}
        onDismiss={handleConsentDecline}
      />

      {/* Header */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h1
          style={{
            fontSize: 'var(--font-size-3xl)',
            fontWeight: 'var(--font-weight-bold)',
            marginBottom: 'var(--space-2)',
          }}
        >
          Competitive Benchmarks
        </h1>
        <p
          style={{
            color: 'var(--color-text-secondary)',
            fontSize: 'var(--font-size-lg)',
          }}
        >
          See how you compare to other professionals in your field
        </p>
      </div>

      {/* Insufficient peers info banner — friendlier than an error */}
      {insufficientPeers && optInStatus && (
        <div
          style={{
            background: 'var(--color-info-bg)',
            border: '1px solid var(--color-info)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-4)',
            marginBottom: 'var(--space-6)',
            color: 'var(--color-info)',
          }}
        >
          <p style={{ fontWeight: 'var(--font-weight-medium)' }}>
            ℹ️ Benchmark not available yet
          </p>
          <p style={{ marginTop: 'var(--space-1)' }}>
            We need at least 30 peers in your seniority/niche group before we
            can generate a comparison. Check back later as more users join.
          </p>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div
          style={{
            background: 'var(--color-error-bg)',
            border: '1px solid var(--color-error)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-4)',
            marginBottom: 'var(--space-6)',
            color: 'var(--color-error)',
          }}
        >
          <p>{error}</p>
          <button
            onClick={() => setError(null)}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-error)',
              fontSize: 'var(--font-size-sm)',
              cursor: 'pointer',
              marginTop: 'var(--space-2)',
              textDecoration: 'underline',
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Opt-in Management */}
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 'var(--space-4)',
          }}
        >
          <div>
            <h3
              style={{
                fontSize: 'var(--font-size-lg)',
                fontWeight: 'var(--font-weight-medium)',
                marginBottom: 'var(--space-2)',
              }}
            >
              Benchmark Participation
            </h3>
            <p
              style={{
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-3)',
                lineHeight: 1.5,
              }}
            >
              {optInStatus
                ? "You're participating in GDPR-compliant competitive benchmarking. Your data is used only in anonymized aggregations."
                : 'Join competitive benchmarking to see how you compare to peers and get personalized skill recommendations.'}
            </p>
            <div
              style={{
                background: 'var(--color-info-bg)',
                border: '1px solid var(--color-info)',
                borderRadius: 'var(--radius-sm)',
                padding: 'var(--space-2)',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-info)',
              }}
            >
              🔒 Privacy-first: All comparisons use anonymized data. You can opt
              out anytime.
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 'var(--space-2)',
            }}
          >
            <div
              style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: optInStatus
                  ? 'var(--color-success-bg)'
                  : 'var(--color-text-muted)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 'var(--font-size-xl)',
              }}
            >
              {optInStatus ? '✅' : '❌'}
            </div>
            <button
              onClick={() => updateOptInStatus(!optInStatus)}
              disabled={updating}
              className={`btn ${optInStatus ? 'btn-secondary' : 'btn-primary'}`}
              style={{
                opacity: updating ? 0.7 : 1,
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-1)',
              }}
            >
              {updating && (
                <div
                  style={{
                    width: '14px',
                    height: '14px',
                    border: '2px solid transparent',
                    borderTop: '2px solid currentColor',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite',
                  }}
                />
              )}
              {updating ? 'Updating...' : optInStatus ? 'Opt Out' : 'Opt In'}
            </button>
          </div>
        </div>
      </div>

      {/* Opt-in Required State */}
      {!optInStatus ? (
        <div
          className="card"
          style={{ textAlign: 'center', padding: 'var(--space-10)' }}
        >
          <div style={{ fontSize: '4rem', marginBottom: 'var(--space-4)' }}>
            📊
          </div>
          <h3
            style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-medium)',
              marginBottom: 'var(--space-2)',
            }}
          >
            Opt-in Required for Benchmarking
          </h3>
          <p
            style={{
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-4)',
            }}
          >
            Enable competitive benchmarking to see your performance compared to
            other professionals and get personalized skill development
            recommendations.
          </p>
          <button
            onClick={() => updateOptInStatus(true)}
            disabled={updating}
            className="btn btn-primary"
            style={{
              fontSize: 'var(--font-size-lg)',
              padding: 'var(--space-4) var(--space-6)',
              opacity: updating ? 0.7 : 1,
            }}
          >
            {updating ? 'Updating...' : 'Enable Benchmarking'}
          </button>
        </div>
      ) : benchmarks.length === 0 ? (
        /* No Benchmarks State */
        <div
          className="card"
          style={{ textAlign: 'center', padding: 'var(--space-10)' }}
        >
          <div style={{ fontSize: '4rem', marginBottom: 'var(--space-4)' }}>
            🎯
          </div>
          <h3
            style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-medium)',
              marginBottom: 'var(--space-2)',
            }}
          >
            No Benchmarks Yet
          </h3>
          <p
            style={{
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-4)',
            }}
          >
            Apply to jobs and calculate benchmarks to see competitive analysis
            and peer comparisons.
          </p>
          <button onClick={() => navigate('/jobs')} className="btn btn-primary">
            Browse Jobs
          </button>
        </div>
      ) : (
        /* Benchmark Dashboard */
        <>
          {/* Statistics Overview */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: 'var(--space-4)',
              marginBottom: 'var(--space-8)',
            }}
          >
            <StatCard
              icon="📊"
              label="Average Score"
              value={`${stats.avgScore}th`}
              subtext="percentile"
              color="var(--color-accent)"
            />
            <StatCard
              icon="🏆"
              label="Highest Score"
              value={`${stats.highestScore}th`}
              subtext="percentile"
              color="var(--color-success)"
            />
            <StatCard
              icon="📈"
              label="Total Benchmarks"
              value={stats.totalBenchmarks.toString()}
              subtext="job comparisons"
              color="var(--color-info)"
            />
            <StatCard
              icon="🎯"
              label="Top gaps"
              value={
                recommendations?.top_missing_skills?.length?.toString() || '0'
              }
              subtext="across saved jobs"
              color="var(--color-warning)"
            />
          </div>

          {/* Recommendations (US 5.3) */}
          {recommendations && (
            <RecommendationsPanel recommendations={recommendations} />
          )}

          {/* Individual Benchmarks */}
          <div className="card">
            <h3
              style={{
                fontSize: 'var(--font-size-xl)',
                fontWeight: 'var(--font-weight-bold)',
                marginBottom: 'var(--space-4)',
              }}
            >
              Individual Job Benchmarks
            </h3>
            <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
              {benchmarks.map((benchmark) => (
                <BenchmarkCard
                  key={benchmark.id}
                  benchmark={benchmark}
                  onClick={() => navigate(`/jobs/${benchmark.job_id}`)}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Stat card component for benchmark metrics.
 */
function StatCard({ icon, label, value, subtext, color }) {
  return (
    <div className="card" style={{ cursor: 'default' }}>
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}
      >
        <div
          style={{
            width: '48px',
            height: '48px',
            borderRadius: 'var(--radius-lg)',
            background: `${color}15`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 'var(--font-size-lg)',
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
              marginBottom: 'var(--space-1)',
            }}
          >
            {label}
          </p>
          <p
            style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-bold)',
              color: 'var(--color-text-primary)',
              marginBottom: 'var(--space-1)',
            }}
          >
            {value}
          </p>
          <p
            style={{
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-size-xs)',
            }}
          >
            {subtext}
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * Individual benchmark card component.
 */
function BenchmarkCard({ benchmark, onClick }) {
  const getScoreColor = (score) => {
    if (score >= 80) return 'var(--color-success)';
    if (score >= 60) return 'var(--color-warning)';
    return 'var(--color-error)';
  };

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: 'var(--space-4)',
        background: 'var(--color-bg-secondary)',
        borderRadius: 'var(--radius-lg)',
        cursor: 'pointer',
        transition: 'all var(--transition-fast)',
        border: '1px solid var(--color-border)',
      }}
      onMouseEnter={(e) => {
        e.target.style.borderColor = 'var(--color-accent)';
        e.target.style.transform = 'translateY(-2px)';
      }}
      onMouseLeave={(e) => {
        e.target.style.borderColor = 'var(--color-border)';
        e.target.style.transform = 'translateY(0)';
      }}
    >
      <div style={{ flex: 1 }}>
        <h4
          style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-medium)',
            marginBottom: 'var(--space-1)',
          }}
        >
          {benchmark.job_title}
        </h4>
        <p
          style={{
            fontSize: 'var(--font-size-sm)',
            color: 'var(--color-text-secondary)',
            marginBottom: 'var(--space-2)',
          }}
        >
          {benchmark.company_name}
        </p>
        <div
          style={{
            display: 'flex',
            gap: 'var(--space-4)',
            fontSize: 'var(--font-size-xs)',
            color: 'var(--color-text-muted)',
          }}
        >
          <span>👥 {benchmark.peer_group_size} peers</span>
          <span>🎯 {benchmark.skill_gaps_count} gaps</span>
          <span>
            📅 {new Date(benchmark.calculated_at).toLocaleDateString()}
          </span>
        </div>
      </div>

      {/* Score Visualization */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 'var(--space-1)',
        }}
      >
        <div
          style={{
            width: '60px',
            height: '60px',
            borderRadius: '50%',
            background: `conic-gradient(${getScoreColor(benchmark.score)} ${benchmark.score * 3.6}deg, var(--color-border) 0deg)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              width: '46px',
              height: '46px',
              borderRadius: '50%',
              background: 'var(--color-bg-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 'var(--font-size-sm)',
              fontWeight: 'var(--font-weight-bold)',
              color: getScoreColor(benchmark.score),
            }}
          >
            {benchmark.score}
          </div>
        </div>
        <span
          style={{
            fontSize: 'var(--font-size-xs)',
            color: 'var(--color-text-muted)',
            textAlign: 'center',
          }}
        >
          percentile
        </span>
      </div>
    </div>
  );
}

/**
 * Recommendations Panel — Top 3 missing skills + recommended ATS keywords.
 * Powered by GET /api/benchmarks/recommendations (US 5.3).
 */
function RecommendationsPanel({ recommendations }) {
  const {
    top_missing_skills: missingSkills = [],
    recommended_keywords: keywords = [],
    jobs_analyzed: jobsAnalyzed = 0,
    peer_group_size: peerGroupSize = 0,
    insufficient_peers: insufficientPeers = false,
  } = recommendations || {};

  if (jobsAnalyzed === 0) {
    return (
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <h3
          style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 'var(--font-weight-medium)',
            marginBottom: 'var(--space-2)',
          }}
        >
          Save a few jobs to unlock recommendations
        </h3>
        <p
          style={{
            color: 'var(--color-text-secondary)',
            fontSize: 'var(--font-size-sm)',
          }}
        >
          Once you've saved at least one role from the Jobs tab, we'll mine its
          requirements against your CV to surface the Top 3 skills to learn
          next.
        </p>
      </div>
    );
  }

  const priorityColor = {
    high: 'var(--color-error)',
    medium: 'var(--color-warning)',
    low: 'var(--color-info)',
  };

  return (
    <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
      <header style={{ marginBottom: 'var(--space-4)' }}>
        <h3
          style={{
            fontSize: 'var(--font-size-xl)',
            fontWeight: 'var(--font-weight-bold)',
            marginBottom: 'var(--space-1)',
          }}
        >
          🎯 Top skills to learn next
        </h3>
        <p
          style={{
            fontSize: 'var(--font-size-sm)',
            color: 'var(--color-text-muted)',
          }}
        >
          Based on {jobsAnalyzed} saved job{jobsAnalyzed !== 1 ? 's' : ''}
          {insufficientPeers
            ? ' — peer comparison skipped (fewer than 30 peers at your level/niche yet).'
            : ` · ${peerGroupSize} peer${peerGroupSize !== 1 ? 's' : ''} at your level/niche.`}
        </p>
      </header>

      {missingSkills.length === 0 ? (
        <p
          style={{
            color: 'var(--color-text-secondary)',
            fontSize: 'var(--font-size-sm)',
          }}
        >
          You're already covering every technology your saved JDs require. Time
          to save some harder roles. 🎉
        </p>
      ) : (
        <div
          style={{
            display: 'grid',
            gap: 'var(--space-3)',
            marginBottom: 'var(--space-5)',
          }}
        >
          {missingSkills.map((skill) => (
            <div
              key={skill.skill}
              style={{
                padding: 'var(--space-3) var(--space-4)',
                background: 'var(--color-bg-secondary)',
                borderRadius: 'var(--radius-md)',
                borderLeft: `3px solid ${priorityColor[skill.priority] || 'var(--color-border)'}`,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 'var(--space-3)',
                  marginBottom: 'var(--space-1)',
                  flexWrap: 'wrap',
                }}
              >
                <strong
                  style={{
                    fontSize: 'var(--font-size-md)',
                    textTransform: 'capitalize',
                  }}
                >
                  {skill.skill}
                </strong>
                <span
                  style={{
                    background:
                      priorityColor[skill.priority] || 'var(--color-accent)',
                    color: 'white',
                    fontSize: 'var(--font-size-xs)',
                    padding: '2px var(--space-2)',
                    borderRadius: 'var(--radius-sm)',
                    textTransform: 'capitalize',
                  }}
                >
                  {skill.priority} priority
                </span>
              </div>
              <p
                style={{
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--color-text-secondary)',
                  margin: 0,
                }}
              >
                {skill.justification}
              </p>
            </div>
          ))}
        </div>
      )}

      {keywords.length > 0 && (
        <section>
          <h4
            style={{
              fontSize: 'var(--font-size-sm)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              fontWeight: 'var(--font-weight-semibold)',
              color: 'var(--color-accent)',
              marginBottom: 'var(--space-2)',
            }}
          >
            ATS keywords to surface on your CV
          </h4>
          <div
            style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}
          >
            {keywords.map((kw) => (
              <span
                key={kw.keyword}
                title={
                  kw.in_cv
                    ? `Already on your CV · requested in ${kw.jd_count} saved job${kw.jd_count !== 1 ? 's' : ''}`
                    : `Missing from your CV · requested in ${kw.jd_count} saved job${kw.jd_count !== 1 ? 's' : ''}`
                }
                style={{
                  background: kw.in_cv
                    ? 'oklch(from var(--color-success) l c h / 0.15)'
                    : 'oklch(from var(--color-warning) l c h / 0.15)',
                  color: kw.in_cv
                    ? 'var(--color-success)'
                    : 'var(--color-warning)',
                  border: `1px solid ${kw.in_cv ? 'var(--color-success)' : 'var(--color-warning)'}`,
                  padding: '2px var(--space-2)',
                  borderRadius: 'var(--radius-full)',
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: 'var(--font-weight-medium)',
                }}
              >
                {kw.in_cv ? '✓' : '+'} {kw.keyword}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default Benchmarks;
