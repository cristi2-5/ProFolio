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
  const [optInStatus, setOptInStatus] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Fetch user benchmarks and opt-in status.
   */
  const fetchBenchmarks = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch opt-in status
      const optInData = await get('/auth/benchmark-opt-in');
      setOptInStatus(optInData.benchmark_opt_in);

      // Fetch benchmarks if opted in
      if (optInData.benchmark_opt_in) {
        const benchmarkData = await get('/benchmarks');
        setBenchmarks(benchmarkData.benchmarks || []);
      } else {
        setBenchmarks([]);
      }

    } catch (err) {
      console.error('Failed to fetch benchmarks:', err);
      setError(err.message || 'Failed to load benchmark data');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Update benchmark opt-in status.
   */
  const updateOptInStatus = async (status) => {
    try {
      setUpdating(true);
      setError(null);

      await patch('/auth/benchmark-opt-in', { benchmark_opt_in: status });
      setOptInStatus(status);

      // Update user context
      updateUser({ benchmark_opt_in: status });

      // Refresh benchmarks if enabling
      if (status) {
        setTimeout(() => {
          fetchBenchmarks();
        }, 1000);
      } else {
        setBenchmarks([]);
      }

    } catch (err) {
      setError('Failed to update opt-in status: ' + err.message);
    } finally {
      setUpdating(false);
    }
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

    const scores = benchmarks.map(b => b.score);
    return {
      avgScore: Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length),
      highestScore: Math.max(...scores),
      lowestScore: Math.min(...scores),
      totalBenchmarks: benchmarks.length,
    };
  };

  /**
   * Get most common skill gaps across benchmarks.
   */
  const getTopSkillGaps = () => {
    const skillGapCounts = {};

    benchmarks.forEach(benchmark => {
      if (benchmark.skill_gaps) {
        benchmark.skill_gaps.forEach(gap => {
          if (skillGapCounts[gap.skill]) {
            skillGapCounts[gap.skill].count++;
            skillGapCounts[gap.skill].priorities.push(gap.priority);
          } else {
            skillGapCounts[gap.skill] = {
              skill: gap.skill,
              count: 1,
              priorities: [gap.priority],
              recommendation: gap.recommendation,
            };
          }
        });
      }
    });

    return Object.values(skillGapCounts)
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  };

  /**
   * Load data on mount.
   */
  useEffect(() => {
    fetchBenchmarks();
  }, []);

  const stats = getAggregateStats();
  const topSkillGaps = getTopSkillGaps();

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
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: 'var(--space-6)' }}>
      {/* Header */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h1 style={{
          fontSize: 'var(--font-size-3xl)',
          fontWeight: 'var(--font-weight-bold)',
          marginBottom: 'var(--space-2)',
        }}>
          Competitive Benchmarks
        </h1>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-lg)' }}>
          See how you compare to other professionals in your field
        </p>
      </div>

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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-4)' }}>
          <div>
            <h3 style={{
              fontSize: 'var(--font-size-lg)',
              fontWeight: 'var(--font-weight-medium)',
              marginBottom: 'var(--space-2)',
            }}>
              Benchmark Participation
            </h3>
            <p style={{
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-3)',
              lineHeight: 1.5,
            }}>
              {optInStatus
                ? 'You\'re participating in GDPR-compliant competitive benchmarking. Your data is used only in anonymized aggregations.'
                : 'Join competitive benchmarking to see how you compare to peers and get personalized skill recommendations.'
              }
            </p>
            <div style={{
              background: 'var(--color-info-bg)',
              border: '1px solid var(--color-info)',
              borderRadius: 'var(--radius-sm)',
              padding: 'var(--space-2)',
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-info)',
            }}>
              🔒 Privacy-first: All comparisons use anonymized data. You can opt out anytime.
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-2)' }}>
            <div style={{
              width: '60px',
              height: '60px',
              borderRadius: '50%',
              background: optInStatus ? 'var(--color-success-bg)' : 'var(--color-text-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 'var(--font-size-xl)',
            }}>
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
                <div style={{
                  width: '14px',
                  height: '14px',
                  border: '2px solid transparent',
                  borderTop: '2px solid currentColor',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                }} />
              )}
              {updating ? 'Updating...' : (optInStatus ? 'Opt Out' : 'Opt In')}
            </button>
          </div>
        </div>
      </div>

      {/* Opt-in Required State */}
      {!optInStatus ? (
        <div className="card" style={{ textAlign: 'center', padding: 'var(--space-10)' }}>
          <div style={{ fontSize: '4rem', marginBottom: 'var(--space-4)' }}>📊</div>
          <h3 style={{
            fontSize: 'var(--font-size-xl)',
            fontWeight: 'var(--font-weight-medium)',
            marginBottom: 'var(--space-2)',
          }}>
            Opt-in Required for Benchmarking
          </h3>
          <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
            Enable competitive benchmarking to see your performance compared to other professionals and get personalized skill development recommendations.
          </p>
          <button
            onClick={() => updateOptInStatus(true)}
            className="btn btn-primary"
            style={{ fontSize: 'var(--font-size-lg)', padding: 'var(--space-4) var(--space-6)' }}
          >
            Enable Benchmarking
          </button>
        </div>
      ) : benchmarks.length === 0 ? (
        /* No Benchmarks State */
        <div className="card" style={{ textAlign: 'center', padding: 'var(--space-10)' }}>
          <div style={{ fontSize: '4rem', marginBottom: 'var(--space-4)' }}>🎯</div>
          <h3 style={{
            fontSize: 'var(--font-size-xl)',
            fontWeight: 'var(--font-weight-medium)',
            marginBottom: 'var(--space-2)',
          }}>
            No Benchmarks Yet
          </h3>
          <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
            Apply to jobs and calculate benchmarks to see competitive analysis and peer comparisons.
          </p>
          <button
            onClick={() => navigate('/jobs')}
            className="btn btn-primary"
          >
            Browse Jobs
          </button>
        </div>
      ) : (
        /* Benchmark Dashboard */
        <>
          {/* Statistics Overview */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--space-4)',
            marginBottom: 'var(--space-8)',
          }}>
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
              label="Skill Gaps"
              value={topSkillGaps.length.toString()}
              subtext="areas to improve"
              color="var(--color-warning)"
            />
          </div>

          {/* Top Skill Gaps */}
          {topSkillGaps.length > 0 && (
            <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
              <h3 style={{
                fontSize: 'var(--font-size-xl)',
                fontWeight: 'var(--font-weight-bold)',
                marginBottom: 'var(--space-4)',
              }}>
                Top Skill Development Opportunities
              </h3>
              <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
                {topSkillGaps.map((gap, index) => (
                  <div
                    key={gap.skill}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: 'var(--space-3)',
                      background: 'var(--color-bg-secondary)',
                      borderRadius: 'var(--radius-md)',
                    }}
                  >
                    <div>
                      <div style={{
                        fontSize: 'var(--font-size-md)',
                        fontWeight: 'var(--font-weight-medium)',
                        marginBottom: 'var(--space-1)',
                        textTransform: 'capitalize',
                      }}>
                        {gap.skill}
                      </div>
                      <div style={{
                        fontSize: 'var(--font-size-sm)',
                        color: 'var(--color-text-secondary)',
                      }}>
                        {gap.recommendation}
                      </div>
                    </div>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--space-2)',
                    }}>
                      <span style={{
                        background: 'var(--color-accent)',
                        color: 'white',
                        padding: 'var(--space-1) var(--space-2)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: 'var(--font-size-xs)',
                      }}>
                        {gap.count} job{gap.count !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Individual Benchmarks */}
          <div className="card">
            <h3 style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-bold)',
              marginBottom: 'var(--space-4)',
            }}>
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
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
        <div style={{
          width: '48px',
          height: '48px',
          borderRadius: 'var(--radius-lg)',
          background: `${color}15`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 'var(--font-size-lg)',
        }}>
          {icon}
        </div>
        <div>
          <p style={{
            color: 'var(--color-text-muted)',
            fontSize: 'var(--font-size-xs)',
            fontWeight: 'var(--font-weight-medium)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: 'var(--space-1)',
          }}>
            {label}
          </p>
          <p style={{
            fontSize: 'var(--font-size-xl)',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--color-text-primary)',
            marginBottom: 'var(--space-1)',
          }}>
            {value}
          </p>
          <p style={{
            color: 'var(--color-text-secondary)',
            fontSize: 'var(--font-size-xs)',
          }}>
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
        <h4 style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-medium)',
          marginBottom: 'var(--space-1)',
        }}>
          {benchmark.job_title}
        </h4>
        <p style={{
          fontSize: 'var(--font-size-sm)',
          color: 'var(--color-text-secondary)',
          marginBottom: 'var(--space-2)',
        }}>
          {benchmark.company_name}
        </p>
        <div style={{ display: 'flex', gap: 'var(--space-4)', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
          <span>👥 {benchmark.peer_group_size} peers</span>
          <span>🎯 {benchmark.skill_gaps_count} gaps</span>
          <span>📅 {new Date(benchmark.calculated_at).toLocaleDateString()}</span>
        </div>
      </div>

      {/* Score Visualization */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 'var(--space-1)',
      }}>
        <div style={{
          width: '60px',
          height: '60px',
          borderRadius: '50%',
          background: `conic-gradient(${getScoreColor(benchmark.score)} ${benchmark.score * 3.6}deg, var(--color-border) 0deg)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <div style={{
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
          }}>
            {benchmark.score}
          </div>
        </div>
        <span style={{
          fontSize: 'var(--font-size-xs)',
          color: 'var(--color-text-muted)',
          textAlign: 'center',
        }}>
          percentile
        </span>
      </div>
    </div>
  );
}

export default Benchmarks;