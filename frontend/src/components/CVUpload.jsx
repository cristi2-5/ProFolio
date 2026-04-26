/**
 * CVUpload Component — Resume Upload and Parsing Interface.
 *
 * Handles file upload, parsing progress, and displays parsed CV data.
 * Supports drag-and-drop, file validation, and manual editing of parsed content.
 */

import { useState, useEffect, useCallback } from 'react';
import { post, get } from '../api/client';

/**
 * CV Upload and parsing component.
 *
 * Features:
 * - Drag-and-drop file upload
 * - File validation (PDF/DOCX, max 5MB)
 * - Real-time parsing progress
 * - Display parsed CV data
 * - Manual editing of parsed content
 * - Error handling and retry functionality
 *
 * @param {Object} props - Component props.
 * @param {Function} props.onUploadComplete - Callback when upload is successful.
 * @returns {JSX.Element} The CV upload component.
 */
function CVUpload({ onUploadComplete }) {
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState(null);
  const [resumes, setResumes] = useState([]);
  const [selectedResume, setSelectedResume] = useState(null);

  /**
   * Validate file before upload.
   */
  const validateFile = (file) => {
    const errors = [];

    // Check file type
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    const allowedExtensions = ['.pdf', '.docx'];

    if (
      !allowedTypes.includes(file.type) &&
      !allowedExtensions.some((ext) => file.name.toLowerCase().endsWith(ext))
    ) {
      errors.push('Only PDF and DOCX files are supported');
    }

    // Check file size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      errors.push('File size must be less than 5MB');
    }

    return errors;
  };

  /**
   * Upload file to backend.
   */
  const uploadFile = async (file) => {
    if (uploading || parsing) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setError(null);

    try {
      // Upload file
      const response = await fetch('/api/resumes/upload', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const resumeData = await response.json();

      // Start polling for parsing completion
      await pollForParsingCompletion(resumeData.id);

      // Refresh resume list
      await fetchResumes();

      if (onUploadComplete) {
        onUploadComplete(resumeData);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  /**
   * Poll for parsing completion.
   */
  const pollForParsingCompletion = async (resumeId) => {
    setParsing(true);

    try {
      let attempts = 0;
      const maxAttempts = 30; // 30 seconds max

      while (attempts < maxAttempts) {
        const resume = await get(`/resumes/${resumeId}`);

        if (resume.parsed_data && Object.keys(resume.parsed_data).length > 0) {
          // Parsing complete
          setSelectedResume(resume);
          break;
        }

        if (resume.parsing_error) {
          throw new Error(resume.parsing_error);
        }

        await new Promise((resolve) => setTimeout(resolve, 1000));
        attempts++;
      }

      if (attempts >= maxAttempts) {
        throw new Error('Parsing timeout - please try again');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setParsing(false);
    }
  };

  /**
   * Fetch user's resumes.
   */
  const fetchResumes = async (signal) => {
    try {
      const data = await get('/resumes/', { signal });
      if (signal?.aborted) return;
      setResumes(Array.isArray(data) ? data : data.resumes || []);
    } catch (err) {
      if (err.name === 'AbortError') return;
      if (import.meta.env.DEV) {
        console.error('Failed to fetch resumes:', err);
      }
    }
  };

  /**
   * Handle file selection.
   */
  const handleFile = useCallback((file) => {
    const errors = validateFile(file);

    if (errors.length > 0) {
      setError(errors.join('. '));
      return;
    }

    uploadFile(file);
  }, []);

  /**
   * Handle drag events.
   */
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  /**
   * Handle drop event.
   */
  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        handleFile(files[0]);
      }
    },
    [handleFile]
  );

  /**
   * Handle file input change.
   */
  const handleInputChange = useCallback(
    (e) => {
      const files = Array.from(e.target.files);
      if (files.length > 0) {
        handleFile(files[0]);
      }
    },
    [handleFile]
  );

  /**
   * Load existing resumes on mount.
   */
  useEffect(() => {
    const ctrl = new AbortController();
    fetchResumes(ctrl.signal);
    return () => ctrl.abort();
  }, []);

  return (
    <div
      style={{ maxWidth: '800px', margin: '0 auto', padding: 'var(--space-6)' }}
    >
      <h2
        style={{
          fontSize: 'var(--font-size-2xl)',
          fontWeight: 'var(--font-weight-bold)',
          marginBottom: 'var(--space-6)',
          color: 'var(--color-text-primary)',
        }}
      >
        Upload Your Resume
      </h2>

      {/* Upload Area */}
      <div
        className="card"
        style={{
          border: dragActive
            ? '2px dashed var(--color-accent)'
            : '2px dashed var(--color-border)',
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--space-8)',
          textAlign: 'center',
          marginBottom: 'var(--space-6)',
          cursor: uploading || parsing ? 'not-allowed' : 'pointer',
          opacity: uploading || parsing ? 0.7 : 1,
          transition: 'all var(--transition-base)',
        }}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={(e) => {
          if (uploading || parsing) {
            e.preventDefault();
            return;
          }
          handleDrop(e);
        }}
        onClick={() =>
          !uploading &&
          !parsing &&
          document.getElementById('file-input').click()
        }
      >
        <input
          type="file"
          id="file-input"
          accept=".pdf,.docx"
          onChange={handleInputChange}
          style={{ display: 'none' }}
          disabled={uploading || parsing}
        />

        {uploading ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 'var(--space-4)',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                border: '3px solid var(--color-border)',
                borderTop: '3px solid var(--color-accent)',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }}
            />
            <div>
              <p
                style={{
                  fontSize: 'var(--font-size-lg)',
                  fontWeight: 'var(--font-weight-medium)',
                }}
              >
                Uploading...
              </p>
              <p
                style={{
                  color: 'var(--color-text-secondary)',
                  fontSize: 'var(--font-size-sm)',
                }}
              >
                Please wait while we process your resume
              </p>
            </div>
          </div>
        ) : parsing ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 'var(--space-4)',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                border: '3px solid var(--color-border)',
                borderTop: '3px solid var(--color-accent)',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }}
            />
            <div>
              <p
                style={{
                  fontSize: 'var(--font-size-lg)',
                  fontWeight: 'var(--font-weight-medium)',
                }}
              >
                Parsing with AI...
              </p>
              <p
                style={{
                  color: 'var(--color-text-secondary)',
                  fontSize: 'var(--font-size-sm)',
                }}
              >
                GPT-4 is analyzing your resume structure
              </p>
            </div>
          </div>
        ) : (
          <div>
            <div style={{ fontSize: '3rem', marginBottom: 'var(--space-4)' }}>
              📄
            </div>
            <h3
              style={{
                fontSize: 'var(--font-size-lg)',
                fontWeight: 'var(--font-weight-medium)',
                marginBottom: 'var(--space-2)',
              }}
            >
              Drop your resume here or click to browse
            </h3>
            <p
              style={{
                color: 'var(--color-text-secondary)',
                fontSize: 'var(--font-size-sm)',
              }}
            >
              Supports PDF and DOCX files up to 5MB
            </p>
          </div>
        )}
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
          <p style={{ fontWeight: 'var(--font-weight-medium)' }}>
            Upload Error
          </p>
          <p
            style={{
              fontSize: 'var(--font-size-sm)',
              marginTop: 'var(--space-1)',
            }}
          >
            {error}
          </p>
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

      {/* Parsed Resume Display */}
      {selectedResume && selectedResume.parsed_data && (
        <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
          <h3
            style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-bold)',
              marginBottom: 'var(--space-4)',
              color: 'var(--color-text-primary)',
            }}
          >
            Parsed Resume Data
          </h3>

          <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
            {/* Personal Info */}
            {selectedResume.parsed_data.personal_info && (
              <div>
                <h4
                  style={{
                    fontSize: 'var(--font-size-md)',
                    fontWeight: 'var(--font-weight-medium)',
                    marginBottom: 'var(--space-2)',
                    color: 'var(--color-accent)',
                  }}
                >
                  Personal Information
                </h4>
                <p>
                  <strong>Name:</strong>{' '}
                  {selectedResume.parsed_data.personal_info.full_name ||
                    'Not specified'}
                </p>
                <p>
                  <strong>Email:</strong>{' '}
                  {selectedResume.parsed_data.personal_info.email ||
                    'Not specified'}
                </p>
                <p>
                  <strong>Phone:</strong>{' '}
                  {selectedResume.parsed_data.personal_info.phone ||
                    'Not specified'}
                </p>
              </div>
            )}

            {/* Skills */}
            {selectedResume.parsed_data.skills &&
              selectedResume.parsed_data.skills.length > 0 && (
                <div>
                  <h4
                    style={{
                      fontSize: 'var(--font-size-md)',
                      fontWeight: 'var(--font-weight-medium)',
                      marginBottom: 'var(--space-2)',
                      color: 'var(--color-accent)',
                    }}
                  >
                    Skills
                  </h4>
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 'var(--space-2)',
                    }}
                  >
                    {selectedResume.parsed_data.skills.map((skill, index) => (
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
                </div>
              )}

            {/* Experience */}
            {selectedResume.parsed_data.experience &&
              selectedResume.parsed_data.experience.length > 0 && (
                <div>
                  <h4
                    style={{
                      fontSize: 'var(--font-size-md)',
                      fontWeight: 'var(--font-weight-medium)',
                      marginBottom: 'var(--space-2)',
                      color: 'var(--color-accent)',
                    }}
                  >
                    Experience ({selectedResume.parsed_data.experience.length}{' '}
                    roles)
                  </h4>
                  {selectedResume.parsed_data.experience
                    .slice(0, 3)
                    .map((exp, index) => (
                      <div
                        key={index}
                        style={{ marginBottom: 'var(--space-3)' }}
                      >
                        <p>
                          <strong>{exp.role}</strong> at {exp.company}
                        </p>
                        <p
                          style={{
                            fontSize: 'var(--font-size-sm)',
                            color: 'var(--color-text-secondary)',
                          }}
                        >
                          {exp.duration}
                        </p>
                      </div>
                    ))}
                </div>
              )}

            {/* Education */}
            {selectedResume.parsed_data.education &&
              selectedResume.parsed_data.education.length > 0 && (
                <div>
                  <h4
                    style={{
                      fontSize: 'var(--font-size-md)',
                      fontWeight: 'var(--font-weight-medium)',
                      marginBottom: 'var(--space-2)',
                      color: 'var(--color-accent)',
                    }}
                  >
                    Education
                  </h4>
                  {selectedResume.parsed_data.education
                    .slice(0, 2)
                    .map((edu, index) => (
                      <div
                        key={index}
                        style={{ marginBottom: 'var(--space-2)' }}
                      >
                        <p>
                          <strong>{edu.degree}</strong>
                        </p>
                        <p
                          style={{
                            fontSize: 'var(--font-size-sm)',
                            color: 'var(--color-text-secondary)',
                          }}
                        >
                          {edu.institution} {edu.year && `(${edu.year})`}
                        </p>
                      </div>
                    ))}
                </div>
              )}
          </div>

          <div
            style={{
              marginTop: 'var(--space-4)',
              padding: 'var(--space-4)',
              background: 'var(--color-bg-secondary)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <p
              style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
              }}
            >
              ✅ Resume successfully parsed with GPT-4. You can now use this
              data for job matching and CV optimization.
            </p>
          </div>
        </div>
      )}

      {/* Existing Resumes List */}
      {resumes.length > 0 && (
        <div className="card">
          <h3
            style={{
              fontSize: 'var(--font-size-xl)',
              fontWeight: 'var(--font-weight-bold)',
              marginBottom: 'var(--space-4)',
            }}
          >
            Your Resumes
          </h3>
          <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
            {resumes.map((resume) => (
              <div
                key={resume.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 'var(--space-3)',
                  background: 'var(--color-bg-secondary)',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                }}
                onClick={() => setSelectedResume(resume)}
              >
                <div>
                  <p
                    style={{
                      fontWeight: 'var(--font-weight-medium)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    {resume.filename}
                    {resume.is_active && (
                      <span
                        style={{
                          fontSize: '10px',
                          background: 'var(--color-success)',
                          color: 'white',
                          padding: '2px 6px',
                          borderRadius: '4px',
                        }}
                      >
                        ACTIVE
                      </span>
                    )}
                  </p>
                  <p
                    style={{
                      fontSize: 'var(--font-size-sm)',
                      color: 'var(--color-text-secondary)',
                    }}
                  >
                    Uploaded {new Date(resume.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: '12px' }}
                >
                  <div
                    style={{
                      fontSize: 'var(--font-size-sm)',
                      color: resume.parsed_data
                        ? 'var(--color-success)'
                        : 'var(--color-warning)',
                    }}
                  >
                    {resume.parsed_data ? '✅ Parsed' : '⏳ Processing'}
                  </div>
                  {!resume.is_active && resume.parsed_data && (
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '4px 8px', fontSize: '12px' }}
                      onClick={async (e) => {
                        e.stopPropagation();
                        try {
                          await post(`/resumes/${resume.id}/activate`);
                          fetchResumes();
                        } catch (err) {
                          if (import.meta.env.DEV) {
                            console.error(err);
                          }
                        }
                      }}
                    >
                      Make Active
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default CVUpload;
