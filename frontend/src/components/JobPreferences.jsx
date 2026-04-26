/**
 * JobPreferences Component — Job Search Configuration Interface.
 *
 * Allows users to set and manage their job search criteria including
 * desired role, location preferences, keywords, and other filters.
 */

import { useState, useEffect } from 'react';
import { get, post } from '../api/client';

/**
 * Job preferences configuration component.
 *
 * Features:
 * - Job title and location preferences
 * - Skill keywords management
 * - Remote/hybrid/onsite preferences
 * - Experience level matching
 * - Real-time validation and save
 *
 * @param {Object} props - Component props.
 * @param {Function} props.onPreferencesSaved - Callback when preferences are saved.
 * @returns {JSX.Element} The job preferences component.
 */
function JobPreferences({ onPreferencesSaved }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const [preferences, setPreferences] = useState({
    desired_title: '',
    location_type: 'remote',
    location_city: '',
    keywords: [],
    min_salary: '',
    max_salary: '',
    experience_level: 'any',
    job_type: 'full_time',
  });

  const [keywordInput, setKeywordInput] = useState('');

  /**
   * Fetch existing preferences.
   */
  const fetchPreferences = async (signal) => {
    try {
      setLoading(true);
      const data = await get('/jobs/preferences', { signal });
      if (signal?.aborted) return;
      if (data && Object.keys(data).length > 0) {
        setPreferences((prev) => ({
          ...prev,
          ...data,
        }));
      }
    } catch (err) {
      if (err.name === 'AbortError') return;
      if (import.meta.env.DEV) {
        console.error('Failed to fetch preferences:', err);
      }
      // Don't show error for missing preferences (404 expected for new users)
      if (err.message && !err.message.includes('404')) {
        setError('Failed to load preferences');
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  /**
   * Save preferences to backend.
   */
  const savePreferences = async () => {
    if (saving) return;
    try {
      setSaving(true);
      setError(null);

      // Validate required fields
      const errors = [];
      if (!preferences.desired_title.trim()) {
        errors.push('Job title is required');
      }
      if (preferences.keywords.length < 3) {
        errors.push('At least 3 skill keywords are required');
      }
      if (preferences.keywords.length > 10) {
        errors.push('Maximum 10 skill keywords allowed');
      }

      if (errors.length > 0) {
        setError(errors.join('. '));
        return;
      }

      // Save preferences
      await post('/jobs/preferences', preferences);

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);

      if (onPreferencesSaved) {
        onPreferencesSaved(preferences);
      }
    } catch (err) {
      setError(err.message || 'Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  /**
   * Handle form field changes.
   */
  const handleChange = (field, value) => {
    setPreferences((prev) => ({ ...prev, [field]: value }));
    setError(null);
  };

  /**
   * Add keyword to list.
   */
  const addKeyword = () => {
    const keyword = keywordInput.trim().toLowerCase();
    if (
      keyword &&
      !preferences.keywords.includes(keyword) &&
      preferences.keywords.length < 10
    ) {
      setPreferences((prev) => ({
        ...prev,
        keywords: [...prev.keywords, keyword],
      }));
      setKeywordInput('');
    }
  };

  /**
   * Remove keyword from list.
   */
  const removeKeyword = (keywordToRemove) => {
    setPreferences((prev) => ({
      ...prev,
      keywords: prev.keywords.filter((k) => k !== keywordToRemove),
    }));
  };

  /**
   * Handle keyword input key press.
   */
  const handleKeywordKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addKeyword();
    }
  };

  /**
   * Load preferences on mount.
   */
  useEffect(() => {
    const ctrl = new AbortController();
    fetchPreferences(ctrl.signal);
    return () => ctrl.abort();
  }, []);

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '200px',
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
      </div>
    );
  }

  return (
    <div className="card" style={{ maxWidth: '600px' }}>
      <h3
        style={{
          fontSize: 'var(--font-size-xl)',
          fontWeight: 'var(--font-weight-bold)',
          marginBottom: 'var(--space-6)',
        }}
      >
        Job Search Preferences
      </h3>

      {/* Success Message */}
      {success && (
        <div
          style={{
            background: 'var(--color-success-bg)',
            border: '1px solid var(--color-success)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-3)',
            marginBottom: 'var(--space-4)',
            color: 'var(--color-success)',
            fontSize: 'var(--font-size-sm)',
          }}
        >
          ✅ Preferences saved successfully! Job scanning will use these
          criteria.
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div
          style={{
            background: 'var(--color-error-bg)',
            border: '1px solid var(--color-error)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-3)',
            marginBottom: 'var(--space-4)',
            color: 'var(--color-error)',
            fontSize: 'var(--font-size-sm)',
          }}
        >
          {error}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          savePreferences();
        }}
        style={{ display: 'grid', gap: 'var(--space-4)' }}
      >
        {/* Job Title */}
        <div>
          <label htmlFor="desired_title" style={labelStyle}>
            Desired Job Title *
          </label>
          <input
            type="text"
            id="desired_title"
            value={preferences.desired_title}
            onChange={(e) => handleChange('desired_title', e.target.value)}
            placeholder="e.g., Senior Frontend Developer, Full Stack Engineer"
            style={inputStyle}
            required
          />
          <p style={helpTextStyle}>
            This will be used to search for relevant job postings
          </p>
        </div>

        {/* Location Preferences */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 'var(--space-3)',
          }}
        >
          <div>
            <label htmlFor="location_type" style={labelStyle}>
              Work Arrangement
            </label>
            <select
              id="location_type"
              value={preferences.location_type}
              onChange={(e) => handleChange('location_type', e.target.value)}
              style={inputStyle}
            >
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site</option>
            </select>
          </div>

          {preferences.location_type !== 'remote' && (
            <div>
              <label htmlFor="location_city" style={labelStyle}>
                City/Location
              </label>
              <input
                type="text"
                id="location_city"
                value={preferences.location_city}
                onChange={(e) => handleChange('location_city', e.target.value)}
                placeholder="e.g., San Francisco, New York"
                style={inputStyle}
              />
            </div>
          )}
        </div>

        {/* Skills Keywords */}
        <div>
          <label htmlFor="keyword_input" style={labelStyle}>
            Skill Keywords * ({preferences.keywords.length}/10)
          </label>

          <div
            style={{
              display: 'flex',
              gap: 'var(--space-2)',
              marginBottom: 'var(--space-2)',
            }}
          >
            <input
              type="text"
              id="keyword_input"
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyPress={handleKeywordKeyPress}
              placeholder="e.g., React, Node.js, Python"
              style={{ ...inputStyle, flex: 1 }}
            />
            <button
              type="button"
              onClick={addKeyword}
              disabled={
                !keywordInput.trim() || preferences.keywords.length >= 10
              }
              style={{
                padding: 'var(--space-2) var(--space-3)',
                background: 'var(--color-accent)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                fontSize: 'var(--font-size-sm)',
                opacity:
                  !keywordInput.trim() || preferences.keywords.length >= 10
                    ? 0.5
                    : 1,
              }}
            >
              Add
            </button>
          </div>

          {/* Keywords List */}
          <div
            style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}
          >
            {preferences.keywords.map((keyword) => (
              <span
                key={keyword}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-1)',
                  background: 'var(--color-accent)',
                  color: 'white',
                  padding: 'var(--space-1) var(--space-2)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 'var(--font-size-sm)',
                }}
              >
                {keyword}
                <button
                  type="button"
                  onClick={() => removeKeyword(keyword)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'white',
                    cursor: 'pointer',
                    fontSize: 'var(--font-size-xs)',
                    padding: '0',
                    marginLeft: 'var(--space-1)',
                  }}
                  aria-label={`Remove ${keyword}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>

          <p style={helpTextStyle}>
            Add 3-10 skills that are important to you. Press Enter or click Add
            to include each skill.
          </p>
        </div>

        {/* Salary Range */}
        <div>
          <label style={labelStyle}>Salary Range (Optional)</label>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto 1fr',
              gap: 'var(--space-2)',
              alignItems: 'center',
            }}
          >
            <input
              type="number"
              value={preferences.min_salary}
              onChange={(e) => handleChange('min_salary', e.target.value)}
              placeholder="Min salary"
              style={inputStyle}
              min="0"
              step="1000"
            />
            <span style={{ color: 'var(--color-text-secondary)' }}>to</span>
            <input
              type="number"
              value={preferences.max_salary}
              onChange={(e) => handleChange('max_salary', e.target.value)}
              placeholder="Max salary"
              style={inputStyle}
              min="0"
              step="1000"
            />
          </div>
          <p style={helpTextStyle}>
            Annual salary in USD. Leave blank if flexible.
          </p>
        </div>

        {/* Experience Level */}
        <div>
          <label htmlFor="experience_level" style={labelStyle}>
            Experience Level
          </label>
          <select
            id="experience_level"
            value={preferences.experience_level}
            onChange={(e) => handleChange('experience_level', e.target.value)}
            style={inputStyle}
          >
            <option value="any">Any Level</option>
            <option value="entry">Entry Level</option>
            <option value="mid">Mid Level</option>
            <option value="senior">Senior Level</option>
            <option value="lead">Lead/Principal</option>
          </select>
        </div>

        {/* Job Type */}
        <div>
          <label htmlFor="job_type" style={labelStyle}>
            Job Type
          </label>
          <select
            id="job_type"
            value={preferences.job_type}
            onChange={(e) => handleChange('job_type', e.target.value)}
            style={inputStyle}
          >
            <option value="full_time">Full-time</option>
            <option value="part_time">Part-time</option>
            <option value="contract">Contract</option>
            <option value="freelance">Freelance</option>
          </select>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={saving}
          className="btn btn-primary"
          style={{
            padding: 'var(--space-4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--space-2)',
            opacity: saving ? 0.7 : 1,
            cursor: saving ? 'not-allowed' : 'pointer',
          }}
        >
          {saving && (
            <div
              style={{
                width: '16px',
                height: '16px',
                border: '2px solid transparent',
                borderTop: '2px solid currentColor',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }}
            />
          )}
          {saving ? 'Saving Preferences...' : 'Save Job Preferences'}
        </button>
      </form>
    </div>
  );
}

// Styles
const labelStyle = {
  display: 'block',
  fontSize: 'var(--font-size-sm)',
  fontWeight: 'var(--font-weight-medium)',
  color: 'var(--color-text-secondary)',
  marginBottom: 'var(--space-1)',
};

const inputStyle = {
  width: '100%',
  padding: 'var(--space-3)',
  background: 'var(--color-bg-primary)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--color-text-primary)',
  fontSize: 'var(--font-size-base)',
  fontFamily: 'var(--font-family)',
  outline: 'none',
  transition: 'border-color var(--transition-fast)',
};

const helpTextStyle = {
  fontSize: 'var(--font-size-xs)',
  color: 'var(--color-text-muted)',
  marginTop: 'var(--space-1)',
};

export default JobPreferences;
