/**
 * Interview Prep Page — AI-powered interview preparation materials.
 *
 * Displays all user interview preparation materials with technical questions,
 * behavioral scenarios, and company-specific cheat sheets.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { get, post } from '../api/client';

/**
 * Interview Prep page component.
 *
 * Features:
 * - List all interview preparations for user's jobs
 * - Generate new interview prep materials
 * - View detailed preparation materials
 * - Technical and behavioral question management
 * - Company-specific cheat sheets
 *
 * @returns {JSX.Element} The interview prep page.
 */
function Interview() {
  const navigate = useNavigate();
  // eslint-disable-next-line no-unused-vars
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [preparations, setPreparations] = useState([]);
  const [selectedPrep, setSelectedPrep] = useState(null);
  // eslint-disable-next-line no-unused-vars
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  /**
   * Fetch all user interview preparations.
   */
  const fetchPreparations = async (signal) => {
    try {
      setLoading(true);
      setError(null);

      const response = await get('/jobs/interview-preps', { signal });
      setPreparations(response.preparations || []);
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.error('Failed to fetch interview preparations:', err);
      setError(err.message || 'Failed to load interview preparations');
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  /**
   * Generate interview prep for a specific job.
   */
  // eslint-disable-next-line no-unused-vars
  const generateInterviewPrep = async (jobId) => {
    try {
      setGenerating(true);
      setError(null);

      const response = await post(`/jobs/${jobId}/generate-interview-prep`, {
        include_user_background: true,
      });

      // Refresh preparations
      await fetchPreparations();
      setSelectedPrep(response);
      setActiveTab('questions');
    } catch (err) {
      setError('Failed to generate interview prep: ' + err.message);
    } finally {
      setGenerating(false);
    }
  };

  /**
   * View detailed preparation materials.
   */
  const viewPreparation = async (prep) => {
    try {
      const response = await get(`/jobs/${prep.job_id}/interview-prep`);
      setSelectedPrep(response);
      setActiveTab('questions');
    } catch (err) {
      setError('Failed to load preparation details: ' + err.message);
    }
  };

  /**
   * Load data on mount.
   */
  useEffect(() => {
    const ctrl = new AbortController();
    fetchPreparations(ctrl.signal);
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
    <div
      style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: 'var(--space-6)',
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h1
          style={{
            fontSize: 'var(--font-size-3xl)',
            fontWeight: 'var(--font-weight-bold)',
            marginBottom: 'var(--space-2)',
          }}
        >
          Interview Preparation
        </h1>
        <p
          style={{
            color: 'var(--color-text-secondary)',
            fontSize: 'var(--font-size-lg)',
          }}
        >
          AI-powered interview materials tailored to your job applications
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

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: selectedPrep ? '1fr 2fr' : '1fr',
          gap: 'var(--space-6)',
        }}
      >
        {/* Preparations List */}
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
                fontSize: 'var(--font-size-xl)',
                fontWeight: 'var(--font-weight-bold)',
              }}
            >
              Your Interview Preparations ({preparations.length})
            </h3>
            <button
              onClick={() => navigate('/jobs')}
              className="btn btn-primary btn-sm"
            >
              + New Prep
            </button>
          </div>

          {preparations.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
              <div style={{ fontSize: '3rem', marginBottom: 'var(--space-3)' }}>
                🎯
              </div>
              <h3
                style={{
                  fontSize: 'var(--font-size-lg)',
                  fontWeight: 'var(--font-weight-medium)',
                  marginBottom: 'var(--space-2)',
                }}
              >
                No Interview Preparations Yet
              </h3>
              <p
                style={{
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-4)',
                }}
              >
                Generate AI-powered interview materials for your job
                applications to get personalized questions and cheat sheets.
              </p>
              <button
                onClick={() => navigate('/jobs')}
                className="btn btn-primary"
              >
                Browse Jobs
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
              {preparations.map((prep) => (
                <PrepCard
                  key={prep.job_id}
                  prep={prep}
                  onClick={() => viewPreparation(prep)}
                  isSelected={selectedPrep?.job_id === prep.job_id}
                />
              ))}
            </div>
          )}
        </div>

        {/* Detailed View */}
        {selectedPrep && (
          <div className="card" style={{ height: 'fit-content' }}>
            {/* Prep Header */}
            <div
              style={{
                marginBottom: 'var(--space-4)',
                paddingBottom: 'var(--space-4)',
                borderBottom: '1px solid var(--color-border)',
              }}
            >
              <h2
                style={{
                  fontSize: 'var(--font-size-xl)',
                  fontWeight: 'var(--font-weight-bold)',
                  marginBottom: 'var(--space-1)',
                }}
              >
                {selectedPrep.job_title}
              </h2>
              <p
                style={{
                  color: 'var(--color-text-secondary)',
                  marginBottom: 'var(--space-2)',
                }}
              >
                {selectedPrep.company_name}
              </p>
              <p
                style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--color-text-muted)',
                }}
              >
                Generated on{' '}
                {new Date(selectedPrep.generated_at).toLocaleDateString()}
              </p>
            </div>

            {/* Tab Navigation */}
            <div style={{ marginBottom: 'var(--space-4)' }}>
              <div
                style={{
                  display: 'flex',
                  gap: 'var(--space-2)',
                  borderBottom: '1px solid var(--color-border)',
                }}
              >
                {[
                  {
                    id: 'questions',
                    label: 'Interview Questions',
                    count: selectedPrep.technical_questions?.length || 0,
                  },
                  {
                    id: 'behavioral',
                    label: 'Behavioral Scenarios',
                    count: selectedPrep.behavioral_questions?.length || 0,
                  },
                  {
                    id: 'cheatsheet',
                    label: 'Tech Cheat Sheet',
                    count: selectedPrep.technology_cheat_sheet?.length || 0,
                  },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    style={{
                      background: 'none',
                      border: 'none',
                      padding: 'var(--space-2) var(--space-3)',
                      cursor: 'pointer',
                      fontSize: 'var(--font-size-sm)',
                      fontWeight: 'var(--font-weight-medium)',
                      color:
                        activeTab === tab.id
                          ? 'var(--color-accent)'
                          : 'var(--color-text-secondary)',
                      borderBottom:
                        activeTab === tab.id
                          ? '2px solid var(--color-accent)'
                          : '2px solid transparent',
                      transition: 'all var(--transition-fast)',
                    }}
                  >
                    {tab.label} ({tab.count})
                  </button>
                ))}
              </div>
            </div>

            {/* Tab Content */}
            <div style={{ minHeight: '400px' }}>
              {activeTab === 'questions' && (
                <QuestionsSection
                  questions={selectedPrep.technical_questions}
                  type="Technical"
                />
              )}
              {activeTab === 'behavioral' && (
                <QuestionsSection
                  questions={selectedPrep.behavioral_questions}
                  type="Behavioral"
                />
              )}
              {activeTab === 'cheatsheet' && (
                <CheatSheetSection
                  cheatSheet={selectedPrep.technology_cheat_sheet}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Interview preparation card component.
 */
function PrepCard({ prep, onClick, isSelected }) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: 'var(--space-4)',
        background: isSelected
          ? 'var(--color-accent-bg)'
          : 'var(--color-bg-secondary)',
        borderRadius: 'var(--radius-lg)',
        cursor: 'pointer',
        transition: 'all var(--transition-fast)',
        border: `1px solid ${isSelected ? 'var(--color-accent)' : 'var(--color-border)'}`,
      }}
      onMouseEnter={(e) => {
        if (!isSelected) {
          e.target.style.borderColor = 'var(--color-accent-light)';
          e.target.style.transform = 'translateY(-1px)';
        }
      }}
      onMouseLeave={(e) => {
        if (!isSelected) {
          e.target.style.borderColor = 'var(--color-border)';
          e.target.style.transform = 'translateY(0)';
        }
      }}
    >
      <h4
        style={{
          fontSize: 'var(--font-size-md)',
          fontWeight: 'var(--font-weight-medium)',
          marginBottom: 'var(--space-1)',
          color: isSelected
            ? 'var(--color-accent)'
            : 'var(--color-text-primary)',
        }}
      >
        {prep.job_title}
      </h4>
      <p
        style={{
          fontSize: 'var(--font-size-sm)',
          color: 'var(--color-text-secondary)',
          marginBottom: 'var(--space-2)',
        }}
      >
        {prep.company_name}
      </p>
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-3)',
          fontSize: 'var(--font-size-xs)',
          color: 'var(--color-text-muted)',
          flexWrap: 'wrap',
        }}
      >
        {prep.has_technical_questions && <span>💻 Technical</span>}
        {prep.has_behavioral_questions && <span>🗣️ Behavioral</span>}
        {prep.has_cheat_sheet && <span>📚 Cheat sheet</span>}
        {prep.updated_at && (
          <span>📅 {new Date(prep.updated_at).toLocaleDateString()}</span>
        )}
      </div>
    </div>
  );
}

/**
 * Questions section component.
 */
function QuestionsSection({ questions, type }) {
  if (!questions || questions.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
        <div style={{ fontSize: '2rem', marginBottom: 'var(--space-2)' }}>
          ❓
        </div>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          No {type.toLowerCase()} questions available
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
      <h4
        style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-bold)',
          color: 'var(--color-text-primary)',
        }}
      >
        {type} Questions ({questions.length})
      </h4>
      {questions.map((question, index) => (
        <div
          key={index}
          style={{
            padding: 'var(--space-4)',
            background: 'var(--color-bg-secondary)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div
            style={{
              fontSize: 'var(--font-size-md)',
              fontWeight: 'var(--font-weight-medium)',
              marginBottom: 'var(--space-2)',
              color: 'var(--color-text-primary)',
            }}
          >
            Q{index + 1}: {question.question}
          </div>
          {(question.guidance || question.star_guidance) && (
            <div
              style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
                background: 'var(--color-info-bg)',
                padding: 'var(--space-2)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-info)',
              }}
            >
              <strong>💡 Ideal answer:</strong>{' '}
              {question.guidance || question.star_guidance}
            </div>
          )}
          {question.sample_answer && (
            <details style={{ marginTop: 'var(--space-2)' }}>
              <summary
                style={{
                  cursor: 'pointer',
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--color-accent)',
                }}
              >
                Show sample answer
              </summary>
              <p
                style={{
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--color-text-secondary)',
                  marginTop: 'var(--space-2)',
                }}
              >
                {question.sample_answer}
              </p>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Technology cheat sheet section component.
 */
function CheatSheetSection({ cheatSheet }) {
  const entries = Array.isArray(cheatSheet) ? cheatSheet : [];
  if (entries.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
        <div style={{ fontSize: '2rem', marginBottom: 'var(--space-2)' }}>
          📚
        </div>
        <p style={{ color: 'var(--color-text-secondary)' }}>
          No technology cheat sheet available
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
      <h4
        style={{
          fontSize: 'var(--font-size-lg)',
          fontWeight: 'var(--font-weight-bold)',
          color: 'var(--color-text-primary)',
        }}
      >
        Technology Cheat Sheet ({entries.length} technologies)
      </h4>
      {entries.map((entry, index) => (
        <div
          key={index}
          style={{
            padding: 'var(--space-4)',
            background: 'var(--color-bg-secondary)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div
            style={{
              fontSize: 'var(--font-size-md)',
              fontWeight: 'var(--font-weight-medium)',
              marginBottom: 'var(--space-2)',
              color: 'var(--color-accent)',
            }}
          >
            {entry.concept}
          </div>
          <div
            style={{
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-text-secondary)',
              lineHeight: 1.5,
              marginBottom: entry.key_points?.length ? 'var(--space-2)' : 0,
            }}
          >
            {entry.definition}
          </div>
          {entry.key_points && entry.key_points.length > 0 && (
            <ul
              style={{
                paddingLeft: 'var(--space-5)',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {entry.key_points.map((kp, i) => (
                <li key={i}>{kp}</li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

export default Interview;
