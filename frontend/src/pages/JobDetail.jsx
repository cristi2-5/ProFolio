/**
 * JobDetail Page — Comprehensive Job Analysis and AI Tools.
 *
 * Single job view with CV optimization, interview preparation, and benchmark scoring.
 * Provides access to all AI-powered job application tools.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { get, post, patch } from '../api/client';

/**
 * Job detail page component with AI-powered tools.
 *
 * Features:
 * - Complete job information display
 * - CV optimization with GPT-4
 * - Cover letter generation
 * - Interview preparation materials
 * - Competitive benchmarking
 * - PDF export functionality
 *
 * @returns {JSX.Element} The job detail page.
 */
function JobDetail() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);

  // AI tool states
  const [optimizing, setOptimizing] = useState(false);
  const [generatingCover, setGeneratingCover] = useState(false);
  const [preparingInterview, setPreparingInterview] = useState(false);
  const [calculatingBenchmark, setCalculatingBenchmark] = useState(false);

  // Content states
  const [optimizedCV, setOptimizedCV] = useState(null);
  const [coverLetter, setCoverLetter] = useState(null);
  const [interviewPrep, setInterviewPrep] = useState(null);
  const [benchmark, setBenchmark] = useState(null);

  // UI states
  const [activeTab, setActiveTab] = useState('overview');
  const [editingCV, setEditingCV] = useState(false);
  const [editingCover, setEditingCover] = useState(false);

  /**
   * Fetch job details and existing AI content.
   */
  const fetchJobDetails = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch job details
      const jobData = await get(`/jobs/${jobId}`);
      setJob(jobData);

      // Fetch existing AI content if available
      if (jobData.optimized_cv) {
        setOptimizedCV(jobData.optimized_cv);
      }

      if (jobData.cover_letter) {
        setCoverLetter(jobData.cover_letter);
      }

      if (jobData.interview_prep) {
        setInterviewPrep(jobData.interview_prep);
      }

      // Try to fetch benchmark if exists
      try {
        const benchmarkData = await get(`/benchmarks/job/${jobId}`);
        setBenchmark(benchmarkData);
      } catch (err) {
        // Benchmark doesn't exist yet
        setBenchmark(null);
      }

    } catch (err) {
      console.error('Failed to fetch job details:', err);
      setError(err.message || 'Failed to load job details');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Optimize CV for this job.
   */
  const optimizeCV = async () => {
    try {
      setOptimizing(true);
      const response = await post(`/jobs/${jobId}/optimize-cv`);
      setOptimizedCV(response);
      setActiveTab('cv-optimization');
    } catch (err) {
      setError('Failed to optimize CV: ' + err.message);
    } finally {
      setOptimizing(false);
    }
  };

  /**
   * Generate cover letter.
   */
  const generateCoverLetter = async () => {
    try {
      setGeneratingCover(true);
      const response = await post(`/jobs/${jobId}/generate-cover-letter`);
      setCoverLetter(response);
      setActiveTab('cover-letter');
    } catch (err) {
      setError('Failed to generate cover letter: ' + err.message);
    } finally {
      setGeneratingCover(false);
    }
  };

  /**
   * Prepare interview materials.
   */
  const prepareInterview = async () => {
    try {
      setPreparingInterview(true);
      const response = await post(`/jobs/${jobId}/generate-interview-prep`);
      setInterviewPrep(response);
      setActiveTab('interview-prep');
    } catch (err) {
      setError('Failed to generate interview prep: ' + err.message);
    } finally {
      setPreparingInterview(false);
    }
  };

  /**
   * Calculate benchmark score.
   */
  const calculateBenchmark = async () => {
    try {
      setCalculatingBenchmark(true);
      const response = await post(`/jobs/${jobId}/calculate-benchmark`);
      setBenchmark(response);
      setActiveTab('benchmark');
    } catch (err) {
      if (err.message.includes('insufficient_peers')) {
        setError('Not enough peer data for competitive benchmarking (minimum 30 users required)');
      } else if (err.message.includes('opt into benchmarking')) {
        setError('You need to opt into benchmarking in Settings to use this feature');
      } else {
        setError('Failed to calculate benchmark: ' + err.message);
      }
    } finally {
      setCalculatingBenchmark(false);
    }
  };

  /**
   * Export CV as PDF.
   */
  const exportCV = async () => {
    try {
      const response = await fetch(`/api/jobs/${jobId}/export-cv`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      // Create download
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${job.company_name}_${job.job_title}_CV.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

    } catch (err) {
      setError('Failed to export CV: ' + err.message);
    }
  };

  /**
   * Save edited CV content.
   */
  const saveOptimizedCV = async () => {
    try {
      await patch(`/jobs/${jobId}/optimized-cv`, { optimized_cv: optimizedCV });
      setEditingCV(false);
    } catch (err) {
      setError('Failed to save CV changes: ' + err.message);
    }
  };

  /**
   * Save edited cover letter content.
   */
  const saveCoverLetter = async () => {
    try {
      await patch(`/jobs/${jobId}/cover-letter`, { cover_letter: coverLetter });
      setEditingCover(false);
    } catch (err) {
      setError('Failed to save cover letter: ' + err.message);
    }
  };

  /**
   * Load job details on mount.
   */
  useEffect(() => {
    if (jobId) {
      fetchJobDetails();
    }
  }, [jobId]);

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

  if (!job) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: 'var(--space-10)', maxWidth: '600px', margin: '0 auto' }}>
        <h2>Job Not Found</h2>
        <p>The requested job could not be found.</p>
        <button onClick={() => navigate('/jobs')} className="btn btn-primary">
          Back to Jobs
        </button>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: '📋' },
    { id: 'cv-optimization', label: 'CV Optimization', icon: '📝', content: optimizedCV },
    { id: 'cover-letter', label: 'Cover Letter', icon: '💌', content: coverLetter },
    { id: 'interview-prep', label: 'Interview Prep', icon: '🎯', content: interviewPrep },
    { id: 'benchmark', label: 'Benchmark', icon: '📊', content: benchmark },
  ];

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: 'var(--space-6)' }}>
      {/* Header */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <button
          onClick={() => navigate('/jobs')}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--color-accent)',
            cursor: 'pointer',
            fontSize: 'var(--font-size-sm)',
            marginBottom: 'var(--space-3)',
          }}
        >
          ← Back to Jobs
        </button>

        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 'var(--space-6)',
        }}>
          <div style={{ flex: 1 }}>
            <h1 style={{
              fontSize: 'var(--font-size-2xl)',
              fontWeight: 'var(--font-weight-bold)',
              marginBottom: 'var(--space-2)',
            }}>
              {job.job_title}
            </h1>
            <p style={{
              fontSize: 'var(--font-size-lg)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-1)',
            }}>
              {job.company_name}
            </p>
            {job.location && (
              <p style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-muted)',
              }}>
                📍 {job.location}
              </p>
            )}
          </div>

          {/* Match Score */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 'var(--space-2)',
          }}>
            <div style={{
              width: '80px',
              height: '80px',
              borderRadius: '50%',
              background: `conic-gradient(var(--color-accent) ${job.match_score * 3.6}deg, var(--color-border) 0deg)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                background: 'var(--color-bg-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 'var(--font-size-lg)',
                fontWeight: 'var(--font-weight-bold)',
                color: 'var(--color-accent)',
              }}>
                {Math.round(job.match_score)}%
              </div>
            </div>
            <span style={{
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-text-secondary)',
              textAlign: 'center',
              fontWeight: 'var(--font-weight-medium)',
            }}>
              Match Score
            </span>
          </div>
        </div>
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

      {/* AI Tools Quick Actions */}
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <h3 style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-medium)',
          marginBottom: 'var(--space-4)',
        }}>
          AI-Powered Tools
        </h3>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--space-3)',
        }}>
          <button
            onClick={optimizeCV}
            disabled={optimizing}
            className="btn btn-primary"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              opacity: optimizing ? 0.7 : 1,
            }}
          >
            {optimizing ? (
              <div style={{ width: '16px', height: '16px', border: '2px solid transparent', borderTop: '2px solid currentColor', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
            ) : (
              '📝'
            )}
            {optimizing ? 'Optimizing...' : 'Optimize CV'}
          </button>

          <button
            onClick={generateCoverLetter}
            disabled={generatingCover}
            className="btn btn-primary"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              opacity: generatingCover ? 0.7 : 1,
            }}
          >
            {generatingCover ? (
              <div style={{ width: '16px', height: '16px', border: '2px solid transparent', borderTop: '2px solid currentColor', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
            ) : (
              '💌'
            )}
            {generatingCover ? 'Generating...' : 'Cover Letter'}
          </button>

          <button
            onClick={prepareInterview}
            disabled={preparingInterview}
            className="btn btn-primary"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              opacity: preparingInterview ? 0.7 : 1,
            }}
          >
            {preparingInterview ? (
              <div style={{ width: '16px', height: '16px', border: '2px solid transparent', borderTop: '2px solid currentColor', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
            ) : (
              '🎯'
            )}
            {preparingInterview ? 'Preparing...' : 'Interview Prep'}
          </button>

          <button
            onClick={calculateBenchmark}
            disabled={calculatingBenchmark}
            className="btn btn-primary"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              opacity: calculatingBenchmark ? 0.7 : 1,
            }}
          >
            {calculatingBenchmark ? (
              <div style={{ width: '16px', height: '16px', border: '2px solid transparent', borderTop: '2px solid currentColor', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
            ) : (
              '📊'
            )}
            {calculatingBenchmark ? 'Calculating...' : 'Benchmark'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{
          display: 'flex',
          gap: 'var(--space-1)',
          borderBottom: '1px solid var(--color-border)',
          marginBottom: 'var(--space-6)',
        }}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: 'var(--space-3) var(--space-4)',
                background: activeTab === tab.id ? 'var(--color-accent)' : 'transparent',
                color: activeTab === tab.id ? 'white' : 'var(--color-text-primary)',
                border: 'none',
                borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
                cursor: 'pointer',
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-medium)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                position: 'relative',
              }}
            >
              {tab.icon} {tab.label}
              {tab.content && (
                <span style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: 'var(--color-success)',
                  marginLeft: 'var(--space-1)',
                }} />
              )}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="card">
          {activeTab === 'overview' && (
            <JobOverview job={job} />
          )}

          {activeTab === 'cv-optimization' && (
            <CVOptimizationTab
              job={job}
              optimizedCV={optimizedCV}
              editing={editingCV}
              onEdit={setEditingCV}
              onSave={saveOptimizedCV}
              onChange={setOptimizedCV}
              onExport={exportCV}
            />
          )}

          {activeTab === 'cover-letter' && (
            <CoverLetterTab
              job={job}
              coverLetter={coverLetter}
              editing={editingCover}
              onEdit={setEditingCover}
              onSave={saveCoverLetter}
              onChange={setCoverLetter}
            />
          )}

          {activeTab === 'interview-prep' && (
            <InterviewPrepTab job={job} interviewPrep={interviewPrep} />
          )}

          {activeTab === 'benchmark' && (
            <BenchmarkTab job={job} benchmark={benchmark} />
          )}
        </div>
      </div>
    </div>
  );
}

// Tab Components
function JobOverview({ job }) {
  return (
    <div>
      <h3 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 'var(--font-weight-bold)', marginBottom: 'var(--space-4)' }}>
        Job Description
      </h3>

      <div style={{ display: 'grid', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
        {job.salary_min || job.salary_max ? (
          <div>
            <strong>Salary: </strong>
            {job.salary_min && job.salary_max
              ? `$${(job.salary_min / 1000).toFixed(0)}K - $${(job.salary_max / 1000).toFixed(0)}K`
              : job.salary_min
              ? `$${(job.salary_min / 1000).toFixed(0)}K+`
              : `Up to $${(job.salary_max / 1000).toFixed(0)}K`}
          </div>
        ) : null}

        {job.job_type && (
          <div><strong>Job Type: </strong>{job.job_type.replace('_', ' ')}</div>
        )}

        {job.external_url && (
          <div>
            <strong>Apply: </strong>
            <a
              href={job.external_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--color-accent)', textDecoration: 'underline' }}
            >
              View on {job.external_url.includes('linkedin') ? 'LinkedIn' : 'Job Board'}
            </a>
          </div>
        )}
      </div>

      <div style={{
        background: 'var(--color-bg-secondary)',
        padding: 'var(--space-4)',
        borderRadius: 'var(--radius-md)',
        whiteSpace: 'pre-wrap',
        lineHeight: 1.6,
      }}>
        {job.description}
      </div>
    </div>
  );
}

function CVOptimizationTab({ job, optimizedCV, editing, onEdit, onSave, onChange, onExport }) {
  if (!optimizedCV) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
        <div style={{ fontSize: '3rem', marginBottom: 'var(--space-4)' }}>📝</div>
        <h3 style={{ marginBottom: 'var(--space-2)' }}>CV Not Optimized Yet</h3>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
          Click "Optimize CV" above to generate an ATS-optimized resume for this position.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
        <h3 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 'var(--font-weight-bold)' }}>
          Optimized CV for {job.company_name}
        </h3>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          {editing ? (
            <>
              <button onClick={onSave} className="btn btn-primary">Save</button>
              <button onClick={() => onEdit(false)} className="btn btn-secondary">Cancel</button>
            </>
          ) : (
            <>
              <button onClick={() => onEdit(true)} className="btn btn-secondary">Edit</button>
              <button onClick={onExport} className="btn btn-primary">📥 Export PDF</button>
            </>
          )}
        </div>
      </div>

      {editing ? (
        <textarea
          value={JSON.stringify(optimizedCV, null, 2)}
          onChange={(e) => {
            try {
              onChange(JSON.parse(e.target.value));
            } catch (err) {
              // Invalid JSON, keep as string for now
            }
          }}
          style={{
            width: '100%',
            minHeight: '400px',
            padding: 'var(--space-3)',
            background: 'var(--color-bg-primary)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--color-text-primary)',
            fontSize: 'var(--font-size-sm)',
            fontFamily: 'monospace',
            resize: 'vertical',
          }}
        />
      ) : (
        <div style={{
          background: 'var(--color-bg-secondary)',
          padding: 'var(--space-4)',
          borderRadius: 'var(--radius-md)',
          whiteSpace: 'pre-wrap',
          lineHeight: 1.6,
        }}>
          {typeof optimizedCV === 'string' ? optimizedCV : JSON.stringify(optimizedCV, null, 2)}
        </div>
      )}
    </div>
  );
}

function CoverLetterTab({ job, coverLetter, editing, onEdit, onSave, onChange }) {
  if (!coverLetter) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
        <div style={{ fontSize: '3rem', marginBottom: 'var(--space-4)' }}>💌</div>
        <h3 style={{ marginBottom: 'var(--space-2)' }}>Cover Letter Not Generated Yet</h3>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          Click "Cover Letter" above to generate a personalized cover letter for this position.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-4)' }}>
        <h3 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 'var(--font-weight-bold)' }}>
          Cover Letter for {job.company_name}
        </h3>
        {editing ? (
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <button onClick={onSave} className="btn btn-primary">Save</button>
            <button onClick={() => onEdit(false)} className="btn btn-secondary">Cancel</button>
          </div>
        ) : (
          <button onClick={() => onEdit(true)} className="btn btn-secondary">Edit</button>
        )}
      </div>

      {editing ? (
        <textarea
          value={typeof coverLetter === 'string' ? coverLetter : coverLetter.content || ''}
          onChange={(e) => onChange(e.target.value)}
          style={{
            width: '100%',
            minHeight: '300px',
            padding: 'var(--space-3)',
            background: 'var(--color-bg-primary)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--color-text-primary)',
            fontSize: 'var(--font-size-sm)',
            lineHeight: 1.6,
            resize: 'vertical',
          }}
        />
      ) : (
        <div style={{
          background: 'var(--color-bg-secondary)',
          padding: 'var(--space-4)',
          borderRadius: 'var(--radius-md)',
          whiteSpace: 'pre-wrap',
          lineHeight: 1.6,
        }}>
          {typeof coverLetter === 'string' ? coverLetter : coverLetter.content || ''}
        </div>
      )}
    </div>
  );
}

function InterviewPrepTab({ job, interviewPrep }) {
  if (!interviewPrep) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
        <div style={{ fontSize: '3rem', marginBottom: 'var(--space-4)' }}>🎯</div>
        <h3 style={{ marginBottom: 'var(--space-2)' }}>Interview Preparation Not Generated Yet</h3>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          Click "Interview Prep" above to generate personalized interview materials.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h3 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 'var(--font-weight-bold)', marginBottom: 'var(--space-4)' }}>
        Interview Preparation for {job.company_name}
      </h3>

      <div style={{ display: 'grid', gap: 'var(--space-6)' }}>
        {/* Questions */}
        {interviewPrep.questions && interviewPrep.questions.length > 0 && (
          <div>
            <h4 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-medium)', marginBottom: 'var(--space-3)', color: 'var(--color-accent)' }}>
              Interview Questions
            </h4>
            {interviewPrep.questions.map((question, index) => (
              <div key={index} style={{ marginBottom: 'var(--space-4)', padding: 'var(--space-3)', background: 'var(--color-bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                <p style={{ fontWeight: 'var(--font-weight-medium)', marginBottom: 'var(--space-2)' }}>
                  Q{index + 1}: {question.question}
                </p>
                {question.suggested_answer && (
                  <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>
                    <strong>Suggested approach:</strong> {question.suggested_answer}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Cheat Sheet */}
        {interviewPrep.cheat_sheet && (
          <div>
            <h4 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-medium)', marginBottom: 'var(--space-3)', color: 'var(--color-accent)' }}>
              Technology Cheat Sheet
            </h4>
            <div style={{
              background: 'var(--color-bg-secondary)',
              padding: 'var(--space-4)',
              borderRadius: 'var(--radius-md)',
              whiteSpace: 'pre-wrap',
              lineHeight: 1.6,
            }}>
              {typeof interviewPrep.cheat_sheet === 'string' ? interviewPrep.cheat_sheet : JSON.stringify(interviewPrep.cheat_sheet, null, 2)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function BenchmarkTab({ job, benchmark }) {
  if (!benchmark) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
        <div style={{ fontSize: '3rem', marginBottom: 'var(--space-4)' }}>📊</div>
        <h3 style={{ marginBottom: 'var(--space-2)' }}>Benchmark Not Calculated Yet</h3>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
          Click "Benchmark" above to see how you compare to other candidates.
        </p>
        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
          Requires at least 30 users with similar profiles to generate meaningful comparisons.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h3 style={{ fontSize: 'var(--font-size-xl)', fontWeight: 'var(--font-weight-bold)', marginBottom: 'var(--space-4)' }}>
        Competitive Benchmark for {job.company_name}
      </h3>

      <div style={{ display: 'grid', gap: 'var(--space-6)' }}>
        {/* Score Display */}
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '120px',
            height: '120px',
            borderRadius: '50%',
            background: `conic-gradient(var(--color-success) ${benchmark.score * 3.6}deg, var(--color-border) 0deg)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto',
            marginBottom: 'var(--space-3)',
          }}>
            <div style={{
              width: '96px',
              height: '96px',
              borderRadius: '50%',
              background: 'var(--color-bg-primary)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <div style={{
                fontSize: 'var(--font-size-xl)',
                fontWeight: 'var(--font-weight-bold)',
                color: 'var(--color-success)',
              }}>
                {benchmark.score}
              </div>
              <div style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--color-text-muted)',
              }}>
                percentile
              </div>
            </div>
          </div>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            You score higher than {benchmark.score}% of similar candidates
          </p>
        </div>

        {/* Peer Group Info */}
        {benchmark.peer_group && (
          <div>
            <h4 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-medium)', marginBottom: 'var(--space-3)', color: 'var(--color-accent)' }}>
              Peer Group Comparison
            </h4>
            <div style={{
              background: 'var(--color-bg-secondary)',
              padding: 'var(--space-4)',
              borderRadius: 'var(--radius-md)',
            }}>
              <p><strong>Sample Size:</strong> {benchmark.peer_group.size} professionals</p>
              <p><strong>Experience Level:</strong> {benchmark.peer_group.seniority_level}</p>
              <p><strong>Privacy Compliant:</strong> ✅ All data anonymized and aggregated</p>
            </div>
          </div>
        )}

        {/* Skill Gaps */}
        {benchmark.skill_gaps && benchmark.skill_gaps.length > 0 && (
          <div>
            <h4 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-medium)', marginBottom: 'var(--space-3)', color: 'var(--color-accent)' }}>
              Skill Development Opportunities
            </h4>
            {benchmark.skill_gaps.map((gap, index) => (
              <div key={index} style={{
                padding: 'var(--space-3)',
                background: 'var(--color-bg-secondary)',
                borderRadius: 'var(--radius-md)',
                marginBottom: 'var(--space-3)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                  <strong style={{ textTransform: 'capitalize' }}>{gap.skill}</strong>
                  <span style={{
                    background: gap.priority === 'high' ? 'var(--color-error)' : gap.priority === 'medium' ? 'var(--color-warning)' : 'var(--color-info)',
                    color: 'white',
                    padding: 'var(--space-1) var(--space-2)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: 'var(--font-size-xs)',
                  }}>
                    {gap.priority} priority
                  </span>
                </div>
                <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-2)' }}>
                  {gap.peer_frequency} of similar candidates have this skill
                </p>
                <p style={{ fontSize: 'var(--font-size-sm)' }}>
                  <strong>Recommendation:</strong> {gap.recommendation}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default JobDetail;