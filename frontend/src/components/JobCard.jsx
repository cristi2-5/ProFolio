/**
 * JobCard Component — Individual Job Display Card.
 *
 * Displays job information with match score, status, and action buttons.
 * Supports different views (compact for lists, detailed for individual display).
 */

import { useState } from 'react';
import { patch } from '../api/client';

/**
 * Job card component for displaying job matches.
 *
 * Features:
 * - Match score visualization
 * - Job status management (new, applied, saved, hidden)
 * - Quick action buttons with visual feedback
 * - Company and role information
 * - applied_at date display for Application History
 *
 * @param {Object} props - Component props.
 * @param {Object} props.job - Job data object.
 * @param {boolean} props.compact - Whether to show compact view.
 * @param {boolean} props.showAppliedAt - Show the applied date (used in history tab).
 * @param {Function} props.onClick - Handler for card click.
 * @param {Function} props.onStatusChange - Handler for status changes.
 * @returns {JSX.Element} The job card component.
 */
const STATUS_TOAST_COPY = {
  new: '✓ Moved back to new',
  saved: '⭐ Saved for later',
  applied: '✅ Marked as applied',
  hidden: '🙈 Hidden from list',
};

function JobCard({
  job,
  compact = false,
  showAppliedAt = false,
  onClick,
  onStatusChange,
}) {
  const [status, setStatus] = useState(job.status || 'new');
  const [updating, setUpdating] = useState(false);
  const [justApplied, setJustApplied] = useState(false);
  const [toast, setToast] = useState(null);

  /**
   * Update job status via API and trigger visual feedback.
   */
  const updateStatus = async (newStatus) => {
    try {
      setUpdating(true);
      await patch(`/jobs/${job.id}/status`, { status: newStatus });
      setStatus(newStatus);

      setToast(
        STATUS_TOAST_COPY[newStatus] || `✓ Status updated to ${newStatus}`
      );
      setTimeout(() => setToast(null), 1800);

      // Flash animation when marking as applied
      if (newStatus === 'applied') {
        setJustApplied(true);
        setTimeout(() => setJustApplied(false), 1200);
      }

      if (onStatusChange) {
        onStatusChange(job.id, newStatus);
      }
    } catch (err) {
      if (import.meta.env.DEV) {
        console.error('Failed to update job status:', err);
      }
      setToast('⚠️ Could not update status');
      setTimeout(() => setToast(null), 2200);
    } finally {
      setUpdating(false);
    }
  };

  /**
   * Get match score color based on score value.
   */
  const getScoreColor = (score) => {
    if (score >= 80) return 'var(--color-success)';
    if (score >= 60) return 'var(--color-warning)';
    return 'var(--color-error)';
  };

  /**
   * Get status display info.
   */
  const getStatusInfo = (jobStatus) => {
    const statusMap = {
      new: {
        label: 'New',
        color: 'var(--color-info)',
        bg: 'var(--color-info-bg)',
      },
      saved: {
        label: 'Saved',
        color: 'var(--color-accent)',
        bg: 'rgba(99, 102, 241, 0.1)',
      },
      applied: {
        label: 'Applied',
        color: 'var(--color-success)',
        bg: 'var(--color-success-bg)',
      },
      hidden: {
        label: 'Hidden',
        color: 'var(--color-text-muted)',
        bg: 'rgba(128, 128, 128, 0.1)',
      },
    };
    return statusMap[jobStatus] || statusMap.new;
  };

  /**
   * Format salary display.
   */
  const formatSalary = () => {
    if (!job.salary_min && !job.salary_max) return null;

    if (job.salary_min && job.salary_max) {
      return `$${(job.salary_min / 1000).toFixed(0)}K - $${(job.salary_max / 1000).toFixed(0)}K`;
    }

    if (job.salary_min) {
      return `$${(job.salary_min / 1000).toFixed(0)}K+`;
    }

    return `Up to $${(job.salary_max / 1000).toFixed(0)}K`;
  };

  const statusInfo = getStatusInfo(status);
  const salary = formatSalary();

  /**
   * Format applied_at timestamp for display.
   */
  const formatAppliedAt = () => {
    if (!job.applied_at) return null;
    return new Date(job.applied_at).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const appliedAtDisplay = formatAppliedAt();

  return (
    <div
      className="card"
      style={{
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all var(--transition-fast)',
        opacity: status === 'hidden' ? 0.6 : 1,
        background: justApplied
          ? 'rgba(34, 197, 94, 0.08)'
          : status === 'hidden'
            ? 'var(--color-bg-secondary)'
            : undefined,
        outline: justApplied ? '1px solid var(--color-success)' : 'none',
        position: 'relative',
      }}
      onClick={onClick}
    >
      {toast && (
        <div
          role="status"
          aria-live="polite"
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'absolute',
            top: 'var(--space-2)',
            right: 'var(--space-2)',
            background: 'var(--color-bg-primary)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            padding: '4px var(--space-2)',
            fontSize: 'var(--font-size-xs)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
            zIndex: 2,
          }}
        >
          {toast}
        </div>
      )}

      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 'var(--space-3)',
        }}
      >
        <div style={{ flex: 1 }}>
          <h3
            style={{
              fontSize: compact ? 'var(--font-size-md)' : 'var(--font-size-lg)',
              fontWeight: 'var(--font-weight-semibold)',
              marginBottom: 'var(--space-1)',
              color: 'var(--color-text-primary)',
            }}
          >
            {job.job_title}
          </h3>
          <p
            style={{
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-1)',
            }}
          >
            {job.company_name}
          </p>
          {job.location && (
            <p
              style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--color-text-muted)',
              }}
            >
              📍 {job.location}
            </p>
          )}
        </div>

        {/* Match Score */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 'var(--space-1)',
            marginLeft: 'var(--space-4)',
          }}
        >
          <div
            style={{
              width: compact ? '48px' : '60px',
              height: compact ? '48px' : '60px',
              borderRadius: '50%',
              background: `conic-gradient(${getScoreColor(job.match_score)} ${job.match_score * 3.6}deg, var(--color-border) 0deg)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
            }}
          >
            <div
              style={{
                width: compact ? '36px' : '46px',
                height: compact ? '36px' : '46px',
                borderRadius: '50%',
                background: 'var(--color-bg-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: compact
                  ? 'var(--font-size-xs)'
                  : 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-bold)',
                color: getScoreColor(job.match_score),
              }}
            >
              {Math.round(job.match_score)}%
            </div>
          </div>
          <span
            style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-text-muted)',
              textAlign: 'center',
            }}
          >
            Match
          </span>
        </div>
      </div>

      {/* Job Details */}
      {!compact && (
        <div
          style={{
            display: 'grid',
            gap: 'var(--space-2)',
            marginBottom: 'var(--space-4)',
          }}
        >
          {salary && (
            <div
              style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-primary)',
                fontWeight: 'var(--font-weight-medium)',
              }}
            >
              💰 {salary}
            </div>
          )}

          {job.job_type && (
            <div
              style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
              }}
            >
              ⏰ {job.job_type.replace('_', '-')}
            </div>
          )}

          {/* applied_at display — shown in Application History tab */}
          {showAppliedAt && appliedAtDisplay && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 'var(--space-1)',
                fontSize: 'var(--font-size-xs)',
                color: 'var(--color-success)',
                fontWeight: 'var(--font-weight-medium)',
                background: 'var(--color-success-bg)',
                padding: 'var(--space-1) var(--space-2)',
                borderRadius: 'var(--radius-sm)',
                width: 'fit-content',
              }}
            >
              ✅ Applied {appliedAtDisplay}
            </div>
          )}

          {job.created_at && (
            <div
              style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--color-text-muted)',
              }}
            >
              🕒 Found {new Date(job.created_at).toLocaleDateString()}
            </div>
          )}
        </div>
      )}

      {/* Status and Actions */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 'var(--space-2)',
        }}
      >
        {/* Status Badge */}
        <span
          style={{
            background: statusInfo.bg,
            color: statusInfo.color,
            padding: 'var(--space-1) var(--space-2)',
            borderRadius: 'var(--radius-sm)',
            fontSize: 'var(--font-size-xs)',
            fontWeight: 'var(--font-weight-medium)',
          }}
        >
          {statusInfo.label}
        </span>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          {status !== 'applied' && (
            <button
              id={`btn-apply-${job.id}`}
              onClick={(e) => {
                e.stopPropagation();
                updateStatus('applied');
              }}
              disabled={updating}
              style={{
                background: justApplied
                  ? 'var(--color-success)'
                  : 'var(--color-success)',
                color: 'white',
                border: 'none',
                padding: 'var(--space-1) var(--space-2)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--font-size-xs)',
                cursor: updating ? 'not-allowed' : 'pointer',
                opacity: updating ? 0.7 : 1,
                transform: justApplied ? 'scale(1.05)' : 'scale(1)',
                transition: 'transform 0.2s ease',
              }}
            >
              {justApplied ? '🎉 Applied!' : 'Mark Applied'}
            </button>
          )}

          {status !== 'saved' && status !== 'applied' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                updateStatus('saved');
              }}
              disabled={updating}
              style={{
                background: 'var(--color-accent)',
                color: 'white',
                border: 'none',
                padding: 'var(--space-1) var(--space-2)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--font-size-xs)',
                cursor: updating ? 'not-allowed' : 'pointer',
                opacity: updating ? 0.7 : 1,
              }}
            >
              ⭐ Save
            </button>
          )}

          {status !== 'hidden' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                updateStatus('hidden');
              }}
              disabled={updating}
              style={{
                background: 'none',
                color: 'var(--color-text-muted)',
                border: '1px solid var(--color-border)',
                padding: 'var(--space-1) var(--space-2)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--font-size-xs)',
                cursor: updating ? 'not-allowed' : 'pointer',
                opacity: updating ? 0.7 : 1,
              }}
            >
              ✕ Hide
            </button>
          )}

          {updating && (
            <div
              style={{
                width: '16px',
                height: '16px',
                border: '2px solid var(--color-border)',
                borderTop: '2px solid var(--color-accent)',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default JobCard;
