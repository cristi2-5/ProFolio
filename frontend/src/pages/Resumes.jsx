/**
 * Resumes Page — CV Management Interface.
 *
 * Allows users to upload, view, and manage their resumes.
 * Displays parsed CV data and provides manual editing capabilities.
 */

import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import CVUpload from '../components/CVUpload';
import { get, patch } from '../api/client';

/**
 * Resumes page component.
 *
 * Features:
 * - CV upload and parsing
 * - Resume list and management
 * - Manual editing of parsed data
 * - Profile completion tracking
 *
 * @returns {JSX.Element} The resumes page.
 */
function Resumes() {
  const { user } = useAuth();
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingResume, setEditingResume] = useState(null);
  const [editData, setEditData] = useState({});

  /**
   * Fetch user's resumes.
   */
  const fetchResumes = async () => {
    try {
      setLoading(true);
      const data = await get('/resumes');
      setResumes(data.resumes || []);
    } catch (err) {
      setError('Failed to load resumes');
      console.error('Failed to fetch resumes:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handle successful upload.
   */
  const handleUploadComplete = (newResume) => {
    setResumes(prev => [newResume, ...prev]);
  };

  /**
   * Start editing a resume.
   */
  const startEdit = (resume) => {
    setEditingResume(resume.id);
    setEditData(resume.parsed_data || {});
  };

  /**
   * Save resume edits.
   */
  const saveEdit = async () => {
    try {
      await patch(`/resumes/${editingResume}`, {
        parsed_data: editData,
      });

      // Update local state
      setResumes(prev =>
        prev.map(resume =>
          resume.id === editingResume
            ? { ...resume, parsed_data: editData }
            : resume
        )
      );

      setEditingResume(null);
      setEditData({});
    } catch (err) {
      setError('Failed to save changes');
      console.error('Failed to save resume:', err);
    }
  };

  /**
   * Cancel editing.
   */
  const cancelEdit = () => {
    setEditingResume(null);
    setEditData({});
  };

  /**
   * Update edit data.
   */
  const updateEditData = (path, value) => {
    setEditData(prev => {
      const newData = { ...prev };
      const keys = path.split('.');
      let current = newData;

      for (let i = 0; i < keys.length - 1; i++) {
        if (!current[keys[i]]) {
          current[keys[i]] = {};
        }
        current = current[keys[i]];
      }

      current[keys[keys.length - 1]] = value;
      return newData;
    });
  };

  /**
   * Load resumes on mount.
   */
  useEffect(() => {
    fetchResumes();
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
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: 'var(--space-6)' }}>
      {/* Header */}
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <h1 style={{
          fontSize: 'var(--font-size-3xl)',
          fontWeight: 'var(--font-weight-bold)',
          marginBottom: 'var(--space-2)',
        }}>
          My Resumes
        </h1>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-lg)' }}>
          Upload and manage your resumes for AI-powered job matching
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

      {/* Main Content */}
      <div style={{ display: 'grid', gap: 'var(--space-8)' }}>
        {/* Upload Section */}
        <CVUpload onUploadComplete={handleUploadComplete} />

        {/* Profile Completion */}
        {resumes.length > 0 && (
          <div className="card">
            <h2 style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-bold)',
              marginBottom: 'var(--space-4)',
            }}>
              Profile Completion
            </h2>

            <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <div style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: resumes.length > 0 ? 'var(--color-success)' : 'var(--color-border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontSize: 'var(--font-size-sm)',
                }}>
                  ✓
                </div>
                <span>Resume uploaded and parsed</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <div style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: user?.seniority_level ? 'var(--color-success)' : 'var(--color-border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontSize: 'var(--font-size-sm)',
                }}>
                  {user?.seniority_level ? '✓' : '○'}
                </div>
                <span>Experience level set ({user?.seniority_level || 'Not set'})</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <div style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: 'var(--color-border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontSize: 'var(--font-size-sm)',
                }}>
                  ○
                </div>
                <span>Job preferences configured (Go to Dashboard)</span>
              </div>
            </div>
          </div>
        )}

        {/* Resume Management */}
        {resumes.length > 0 && (
          <div className="card">
            <h2 style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-bold)',
              marginBottom: 'var(--space-4)',
            }}>
              Manage Resumes
            </h2>

            <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
              {resumes.map((resume) => (
                <div
                  key={resume.id}
                  className="card"
                  style={{
                    background: 'var(--color-bg-secondary)',
                    border: editingResume === resume.id ? '2px solid var(--color-accent)' : '1px solid var(--color-border)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-4)' }}>
                    <div>
                      <h3 style={{
                        fontSize: 'var(--font-size-lg)',
                        fontWeight: 'var(--font-weight-medium)',
                        marginBottom: 'var(--space-1)',
                      }}>
                        {resume.filename}
                      </h3>
                      <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                        Uploaded {new Date(resume.created_at).toLocaleDateString()}
                      </p>
                    </div>

                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                      {editingResume === resume.id ? (
                        <>
                          <button
                            onClick={saveEdit}
                            className="btn btn-primary"
                            style={{ padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--font-size-sm)' }}
                          >
                            Save
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="btn btn-secondary"
                            style={{ padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--font-size-sm)' }}
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => startEdit(resume)}
                          className="btn btn-secondary"
                          style={{ padding: 'var(--space-2) var(--space-3)', fontSize: 'var(--font-size-sm)' }}
                          disabled={!resume.parsed_data}
                        >
                          Edit
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Parsed Data Display/Edit */}
                  {resume.parsed_data && (
                    <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
                      {/* Skills Section */}
                      <div>
                        <h4 style={{
                          fontSize: 'var(--font-size-md)',
                          fontWeight: 'var(--font-weight-medium)',
                          marginBottom: 'var(--space-2)',
                          color: 'var(--color-accent)',
                        }}>
                          Skills
                        </h4>

                        {editingResume === resume.id ? (
                          <textarea
                            value={editData.skills ? editData.skills.join(', ') : ''}
                            onChange={(e) => updateEditData('skills', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                            placeholder="Enter skills separated by commas"
                            style={{
                              width: '100%',
                              minHeight: '80px',
                              padding: 'var(--space-3)',
                              background: 'var(--color-bg-primary)',
                              border: '1px solid var(--color-border)',
                              borderRadius: 'var(--radius-md)',
                              color: 'var(--color-text-primary)',
                              fontSize: 'var(--font-size-sm)',
                              resize: 'vertical',
                            }}
                          />
                        ) : (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                            {(resume.parsed_data.skills || []).map((skill, index) => (
                              <span
                                key={index}
                                style={{
                                  background: 'var(--color-accent)',
                                  color: 'white',
                                  padding: 'var(--space-1) var(--space-2)',
                                  borderRadius: 'var(--radius-sm)',
                                  fontSize: 'var(--font-size-sm)',
                                }}
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Summary Section */}
                      <div>
                        <h4 style={{
                          fontSize: 'var(--font-size-md)',
                          fontWeight: 'var(--font-weight-medium)',
                          marginBottom: 'var(--space-2)',
                          color: 'var(--color-accent)',
                        }}>
                          Summary
                        </h4>

                        {editingResume === resume.id ? (
                          <textarea
                            value={editData.summary || ''}
                            onChange={(e) => updateEditData('summary', e.target.value)}
                            placeholder="Professional summary"
                            style={{
                              width: '100%',
                              minHeight: '100px',
                              padding: 'var(--space-3)',
                              background: 'var(--color-bg-primary)',
                              border: '1px solid var(--color-border)',
                              borderRadius: 'var(--radius-md)',
                              color: 'var(--color-text-primary)',
                              fontSize: 'var(--font-size-sm)',
                              resize: 'vertical',
                            }}
                          />
                        ) : (
                          <p style={{ fontSize: 'var(--font-size-sm)', lineHeight: '1.5' }}>
                            {resume.parsed_data.summary || 'No summary available'}
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {!resume.parsed_data && (
                    <div style={{
                      padding: 'var(--space-4)',
                      background: 'var(--color-warning-bg)',
                      border: '1px solid var(--color-warning)',
                      borderRadius: 'var(--radius-md)',
                      color: 'var(--color-warning)',
                      textAlign: 'center',
                    }}>
                      <p>Resume is still being processed. Please check back in a few moments.</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {resumes.length === 0 && (
          <div className="card" style={{ textAlign: 'center', padding: 'var(--space-10)' }}>
            <div style={{ fontSize: '4rem', marginBottom: 'var(--space-4)' }}>📄</div>
            <h3 style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-medium)',
              marginBottom: 'var(--space-2)',
            }}>
              No resumes uploaded yet
            </h3>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
              Upload your first resume to get started with AI-powered job matching
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Resumes;