/**
 * Jobs Page — Job Matches Management Interface.
 *
 * Displays filtered job listings with search, sorting, status management,
 * and a dedicated Application History tab for tracking applied jobs.
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import JobCard from '../components/JobCard';
import { get, post } from '../api/client';

/** Valid status tabs with display labels. */
const STATUS_TABS = [
  { key: 'all', label: '🔍 All' },
  { key: 'new', label: '✨ New' },
  { key: 'saved', label: '⭐ Saved' },
  { key: 'applied', label: '✅ Applied' },
  { key: 'hidden', label: '🙈 Hidden' },
];

/** Valid sort options. */
const SORT_OPTIONS = [
  { value: 'match_score', label: 'Match Score' },
  { value: 'created_at', label: 'Date Found' },
  { value: 'company_name', label: 'Company' },
  { value: 'job_title', label: 'Job Title' },
];

/**
 * Jobs page component.
 *
 * Features:
 * - Job listing with search, filtering, and sorting
 * - Status-based tabs (new, saved, applied, hidden)
 * - Dedicated Application History view (applied tab with timeline)
 * - Manual job scan trigger (rate-limited 1/hour)
 * - Pagination for large job lists
 *
 * @returns {JSX.Element} The jobs page.
 */
function Jobs() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [error, setError] = useState(null);
  const [scanMessage, setScanMessage] = useState(null);

  // Filtering, sorting, and pagination state
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('match_score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  /**
   * Fetch jobs from backend with all current filters applied.
   */
  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (activeTab !== 'all') params.append('status_filter', activeTab);
      if (searchQuery.trim()) params.append('search', searchQuery.trim());
      params.append('sort_by', sortBy);
      params.append('sort_order', sortOrder);
      params.append('limit', pageSize.toString());
      params.append('offset', ((currentPage - 1) * pageSize).toString());

      const data = await get(`/jobs/?${params.toString()}`);
      setJobs(data.jobs || []);
      setTotalJobs(data.total_count ?? 0);
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
      setError(err.message || 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  }, [activeTab, searchQuery, sortBy, sortOrder, currentPage]);

  /** Reset page to 1 whenever filters/sorting change. */
  useEffect(() => {
    setCurrentPage(1);
  }, [activeTab, searchQuery, sortBy, sortOrder]);

  /** Refetch jobs when query params change. */
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  /**
   * Trigger a real manual job scan.
   */
  const triggerJobScan = async () => {
    try {
      setScanning(true);
      setScanMessage(null);
      setError(null);

      const result = await post('/jobs/scan');
      setScanMessage(
        result.jobs_found > 0
          ? `✅ Found ${result.jobs_found} new job${result.jobs_found !== 1 ? 's' : ''}!`
          : '✅ Scan complete — no new jobs found at this time.',
      );

      // Refresh the list after a short delay
      setTimeout(() => fetchJobs(), 1500);
    } catch (err) {
      if (err.status === 429) {
        setError(err.message || 'Rate limit reached. Please wait before scanning again.');
      } else if (err.status === 503) {
        setError('Job scan service is not available right now.');
      } else {
        setError(err.message || 'Failed to trigger job scan');
      }
    } finally {
      setScanning(false);
    }
  };

  /**
   * Optimistically update job status in the local list.
   */
  const handleStatusChange = (jobId, newStatus) => {
    setJobs((prev) =>
      prev.map((job) =>
        job.id === jobId ? { ...job, status: newStatus } : job,
      ),
    );
  };

  /** Navigate to job detail page. */
  const handleJobClick = (job) => {
    navigate(`/jobs/${job.id}`);
  };

  const totalPages = Math.ceil(totalJobs / pageSize);
  const isHistoryTab = activeTab === 'applied';

  // Group applied jobs by date for the history timeline view
  const groupedByDate = isHistoryTab
    ? jobs.reduce((acc, job) => {
        const date = job.applied_at
          ? new Date(job.applied_at).toLocaleDateString('en-US', {
              weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
            })
          : 'Unknown Date';
        if (!acc[date]) acc[date] = [];
        acc[date].push(job);
        return acc;
      }, {})
    : null;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: 'var(--space-6)' }}>
      {/* ── Header ── */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: 'var(--space-6)',
        flexWrap: 'wrap',
        gap: 'var(--space-3)',
      }}>
        <div>
          <h1 style={{
            fontSize: 'var(--font-size-3xl)',
            fontWeight: 'var(--font-weight-bold)',
            marginBottom: 'var(--space-2)',
          }}>
            {isHistoryTab ? '📋 Application History' : 'Job Matches'}
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-lg)' }}>
            {isHistoryTab
              ? `${totalJobs} job application${totalJobs !== 1 ? 's' : ''} tracked`
              : `${totalJobs} job${totalJobs !== 1 ? 's' : ''} matching your profile`}
          </p>
        </div>

        <button
          onClick={triggerJobScan}
          disabled={scanning}
          id="btn-scan-jobs"
          className="btn btn-primary"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
            opacity: scanning ? 0.7 : 1,
            whiteSpace: 'nowrap',
          }}
        >
          {scanning ? (
            <>
              <div style={{
                width: '16px', height: '16px',
                border: '2px solid transparent',
                borderTop: '2px solid currentColor',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite',
              }} />
              Scanning...
            </>
          ) : (
            <>🔍 Scan for New Jobs</>
          )}
        </button>
      </div>

      {/* ── Scan feedback banner ── */}
      {scanMessage && (
        <div style={{
          background: 'var(--color-success-bg)',
          border: '1px solid var(--color-success)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-3) var(--space-4)',
          marginBottom: 'var(--space-4)',
          color: 'var(--color-success)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span>{scanMessage}</span>
          <button
            onClick={() => setScanMessage(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontSize: '1.2rem' }}
          >×</button>
        </div>
      )}

      {/* ── Error banner ── */}
      {error && (
        <div style={{
          background: 'var(--color-error-bg)',
          border: '1px solid var(--color-error)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-4)',
          marginBottom: 'var(--space-4)',
          color: 'var(--color-error)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <p>{error}</p>
          <button
            onClick={() => setError(null)}
            style={{ background: 'none', border: 'none', color: 'var(--color-error)', cursor: 'pointer', fontSize: '1.2rem' }}
          >×</button>
        </div>
      )}

      {/* ── Filters card ── */}
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        {/* Status tabs */}
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <p style={{
            fontSize: 'var(--font-size-sm)',
            fontWeight: 'var(--font-weight-medium)',
            color: 'var(--color-text-secondary)',
            marginBottom: 'var(--space-2)',
          }}>
            Filter by Status
          </p>
          <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.key}
                id={`tab-${tab.key}`}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  background: activeTab === tab.key ? 'var(--color-accent)' : 'transparent',
                  color: activeTab === tab.key ? 'white' : 'var(--color-text-primary)',
                  fontSize: 'var(--font-size-sm)',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                  fontWeight: activeTab === tab.key ? 'var(--font-weight-semibold)' : 'normal',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Search + Sort row (hidden in history view for clarity) */}
        {!isHistoryTab && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto auto',
            gap: 'var(--space-3)',
            alignItems: 'end',
          }}>
            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-medium)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-1)',
              }}>
                Search Jobs
              </label>
              <input
                id="input-search-jobs"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by title or company..."
                style={{
                  width: '100%',
                  padding: 'var(--space-3)',
                  background: 'var(--color-bg-primary)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--color-text-primary)',
                  fontSize: 'var(--font-size-sm)',
                }}
              />
            </div>

            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-medium)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-1)',
              }}>
                Sort by
              </label>
              <select
                id="select-sort-by"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                style={{
                  padding: 'var(--space-3)',
                  background: 'var(--color-bg-primary)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--color-text-primary)',
                  fontSize: 'var(--font-size-sm)',
                }}
              >
                {SORT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                fontWeight: 'var(--font-weight-medium)',
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-1)',
              }}>
                Order
              </label>
              <select
                id="select-sort-order"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                style={{
                  padding: 'var(--space-3)',
                  background: 'var(--color-bg-primary)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--color-text-primary)',
                  fontSize: 'var(--font-size-sm)',
                }}
              >
                <option value="desc">High to Low</option>
                <option value="asc">Low to High</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* ── Main content area ── */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px' }}>
          <div style={{
            width: '40px', height: '40px',
            border: '4px solid var(--color-border)',
            borderTop: '4px solid var(--color-accent)',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
          }} />
        </div>
      ) : jobs.length === 0 ? (
        /* ── Empty state ── */
        <div className="card" style={{ textAlign: 'center', padding: 'var(--space-10)' }}>
          <div style={{ fontSize: '4rem', marginBottom: 'var(--space-4)' }}>
            {isHistoryTab ? '📋' : '🔍'}
          </div>
          <h3 style={{
            fontSize: 'var(--font-size-xl)',
            fontWeight: 'var(--font-weight-medium)',
            marginBottom: 'var(--space-2)',
          }}>
            {isHistoryTab
              ? "You haven't applied to any jobs yet"
              : searchQuery || activeTab !== 'all'
                ? 'No jobs match your filters'
                : 'No jobs found yet'}
          </h3>
          <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
            {isHistoryTab
              ? 'When you click "Applied" on a job, it will appear here with the date you applied.'
              : searchQuery || activeTab !== 'all'
                ? 'Try adjusting your search or filter criteria.'
                : 'Upload your resume and set preferences, then click "Scan for New Jobs".'}
          </p>
          {!isHistoryTab && !searchQuery && activeTab === 'all' && (
            <button onClick={() => navigate('/dashboard')} className="btn btn-primary">
              Go to Dashboard
            </button>
          )}
        </div>
      ) : isHistoryTab ? (
        /* ── Application History timeline view ── */
        <div>
          <p style={{
            fontSize: 'var(--font-size-sm)',
            color: 'var(--color-text-secondary)',
            marginBottom: 'var(--space-5)',
          }}>
            Showing {jobs.length} of {totalJobs} application{totalJobs !== 1 ? 's' : ''}
          </p>
          {Object.entries(groupedByDate).map(([date, dateJobs]) => (
            <div key={date} style={{ marginBottom: 'var(--space-6)' }}>
              {/* Date group header */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                marginBottom: 'var(--space-3)',
              }}>
                <div style={{
                  width: '12px', height: '12px',
                  borderRadius: '50%',
                  background: 'var(--color-success)',
                  flexShrink: 0,
                }} />
                <h3 style={{
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}>
                  {date}
                </h3>
                <div style={{
                  flex: 1,
                  height: '1px',
                  background: 'var(--color-border)',
                }} />
                <span style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--color-text-muted)',
                }}>
                  {dateJobs.length} application{dateJobs.length !== 1 ? 's' : ''}
                </span>
              </div>

              {/* Jobs for this date */}
              <div style={{
                display: 'grid',
                gap: 'var(--space-3)',
                paddingLeft: 'var(--space-6)',
                borderLeft: '2px solid var(--color-border)',
                marginLeft: '5px',
              }}>
                {dateJobs.map((job) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    onClick={() => handleJobClick(job)}
                    onStatusChange={handleStatusChange}
                    showAppliedAt
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* ── Standard job card grid ── */
        <>
          <div style={{ display: 'grid', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
            {jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onClick={() => handleJobClick(job)}
                onStatusChange={handleStatusChange}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 'var(--space-2)' }}>
              <button
                id="btn-prev-page"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  background: currentPage === 1 ? 'var(--color-bg-secondary)' : 'var(--color-accent)',
                  color: currentPage === 1 ? 'var(--color-text-muted)' : 'white',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                }}
              >
                Previous
              </button>
              <span style={{ padding: 'var(--space-2) var(--space-4)', fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)' }}>
                Page {currentPage} of {totalPages}
              </span>
              <button
                id="btn-next-page"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                style={{
                  padding: 'var(--space-2) var(--space-3)',
                  background: currentPage === totalPages ? 'var(--color-bg-secondary)' : 'var(--color-accent)',
                  color: currentPage === totalPages ? 'var(--color-text-muted)' : 'white',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                }}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default Jobs;