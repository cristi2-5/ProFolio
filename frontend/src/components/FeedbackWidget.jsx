/**
 * Feedback Widget — Phase 7 beta launch.
 *
 * Compact 5-star rater with optional comment, shown under any piece of
 * AI-generated content. Submits to POST /api/feedback. Persists a
 * "already submitted" marker per (content_type, content_id) in
 * localStorage so the same content isn't re-rated by accident.
 *
 * Props:
 *   - contentType: one of 'optimized_cv' | 'cover_letter'
 *                         | 'interview_prep' | 'benchmark' | 'other'.
 *   - contentId:  optional reference to the artefact (e.g. job_id).
 *   - label:      user-visible label (defaults to "Was this useful?").
 */

import { useMemo, useState } from 'react';
import { post } from '../api/client';

const RATING_LABELS = {
  1: 'Poor',
  2: 'Meh',
  3: 'OK',
  4: 'Good',
  5: 'Great',
};

function storageKey(contentType, contentId) {
  return `profolio.feedback.${contentType}:${contentId || '-'}`;
}

function FeedbackWidget({
  contentType,
  contentId,
  label = 'Was this useful?',
}) {
  const alreadySubmitted = useMemo(() => {
    try {
      return localStorage.getItem(storageKey(contentType, contentId)) === '1';
    } catch {
      return false;
    }
  }, [contentType, contentId]);

  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState('');
  const [expanded, setExpanded] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(alreadySubmitted);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    if (rating < 1 || rating > 5) return;
    try {
      setSubmitting(true);
      setError(null);
      await post('/feedback', {
        content_type: contentType,
        content_id: contentId ?? null,
        rating,
        comment: comment.trim() ? comment.trim().slice(0, 2000) : null,
      });
      setSubmitted(true);
      try {
        localStorage.setItem(storageKey(contentType, contentId), '1');
      } catch {
        // ignore storage errors — widget still UX-correct for this session
      }
    } catch (err) {
      setError(err.message || 'Could not send feedback');
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div
        style={{
          marginTop: 'var(--space-3)',
          padding: 'var(--space-2) var(--space-3)',
          background: 'oklch(from var(--color-success) l c h / 0.10)',
          border: '1px solid oklch(from var(--color-success) l c h / 0.3)',
          borderRadius: 'var(--radius-md)',
          fontSize: 'var(--font-size-sm)',
          color: 'var(--color-success)',
        }}
      >
        🙏 Thanks for the feedback — it helps us tune the agents.
      </div>
    );
  }

  return (
    <div
      style={{
        marginTop: 'var(--space-3)',
        padding: 'var(--space-3)',
        background: 'var(--color-bg-secondary)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-md)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)',
          flexWrap: 'wrap',
        }}
      >
        <span
          style={{
            fontSize: 'var(--font-size-sm)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {label}
        </span>
        <div
          role="radiogroup"
          aria-label={label}
          style={{ display: 'flex', gap: '4px' }}
        >
          {[1, 2, 3, 4, 5].map((star) => {
            const active = star <= (hover || rating);
            return (
              <button
                key={star}
                type="button"
                role="radio"
                aria-checked={rating === star}
                aria-label={`${star} star${star !== 1 ? 's' : ''} — ${RATING_LABELS[star]}`}
                onMouseEnter={() => setHover(star)}
                onMouseLeave={() => setHover(0)}
                onFocus={() => setHover(star)}
                onBlur={() => setHover(0)}
                onClick={() => {
                  setRating(star);
                  setExpanded(true);
                }}
                disabled={submitting}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: submitting ? 'default' : 'pointer',
                  fontSize: 'var(--font-size-lg)',
                  color: active
                    ? 'var(--color-warning)'
                    : 'var(--color-text-muted)',
                  padding: '2px',
                  transition: 'transform 0.15s ease',
                  transform: active ? 'scale(1.1)' : 'scale(1)',
                }}
              >
                ★
              </button>
            );
          })}
        </div>
        {rating > 0 && (
          <span
            style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-text-muted)',
            }}
          >
            {RATING_LABELS[rating]}
          </span>
        )}
      </div>

      {expanded && rating > 0 && (
        <div style={{ marginTop: 'var(--space-3)' }}>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="What worked or didn't? (optional, max 2000 chars)"
            maxLength={2000}
            style={{
              width: '100%',
              minHeight: '72px',
              padding: 'var(--space-2)',
              background: 'var(--color-bg-primary)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--color-text-primary)',
              fontSize: 'var(--font-size-sm)',
              lineHeight: 1.5,
              resize: 'vertical',
            }}
          />
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: 'var(--space-2)',
              gap: 'var(--space-2)',
              flexWrap: 'wrap',
            }}
          >
            <span
              style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--color-text-muted)',
              }}
            >
              {comment.length}/2000
            </span>
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setExpanded(false);
                  setComment('');
                  setRating(0);
                }}
                disabled={submitting}
                style={{ fontSize: 'var(--font-size-sm)' }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSubmit}
                disabled={submitting}
                style={{
                  fontSize: 'var(--font-size-sm)',
                  opacity: submitting ? 0.7 : 1,
                }}
              >
                {submitting ? 'Sending…' : 'Send feedback'}
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <p
          style={{
            marginTop: 'var(--space-2)',
            color: 'var(--color-error)',
            fontSize: 'var(--font-size-sm)',
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
}

export default FeedbackWidget;
