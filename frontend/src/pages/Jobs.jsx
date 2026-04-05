/**
 * Jobs Page — Job Matches Management Interface.
 *
 * Displays filtered job listings with search, sorting, and status management.
 * Provides access to job details and AI-powered job tools.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import JobCard from '../components/JobCard';
import { get, post } from '../api/client';

/**
 * Jobs page component.
 *
 * Features:
 * - Job listing with filtering and sorting
 * - Status-based filtering (new, saved, applied, hidden)
 * - Search by title/company
 * - Manual job scanning trigger
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

  // Filtering and pagination state
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('match_score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [jobsPerPage] = useState(20);

  /**
   * Fetch jobs from backend with filters.
   */
  const fetchJobs = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (searchQuery) params.append('search', searchQuery);
      params.append('sort_by', sortBy);
      params.append('sort_order', sortOrder);
      params.append('limit', jobsPerPage.toString());
      params.append('offset', ((currentPage - 1) * jobsPerPage).toString());

      const data = await get(`/jobs/?${params.toString()}`);
      setJobs(data.jobs || []);
      setTotalJobs(data.total_count || 0);

    } catch (err) {
      console.error('Failed to fetch jobs:', err);
      setError(err.message || 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Trigger job scanning manually.
   */
  const triggerJobScan = async () => {
    try {
      setScanning(true);
      await post('/jobs/scan');

      // Refresh jobs after scan
      setTimeout(() => {
        fetchJobs();
      }, 2000);

    } catch (err) {
      console.error('Failed to trigger job scan:', err);
      setError('Failed to trigger job scan');
    } finally {
      setScanning(false);
    }
  };

  /**
   * Handle job status change.
   */
  const handleStatusChange = (jobId, newStatus) => {
    setJobs(prev =>
      prev.map(job =>
        job.id === jobId ? { ...job, status: newStatus } : job
      )
    );
  };

  /**
   * Handle job card click.
   */
  const handleJobClick = (job) => {
    navigate(`/jobs/${job.id}`);
  };

  /**
   * Reset pagination when filters change.
   */
  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter, searchQuery, sortBy, sortOrder]);

  /**
   * Fetch jobs when filters or pagination changes.
   */
  useEffect(() => {
    fetchJobs();
  }, [statusFilter, searchQuery, sortBy, sortOrder, currentPage]);

  /**
   * Get status filter counts.
   */
  const getStatusCounts = () => {
    const counts = jobs.reduce((acc, job) => {
      acc[job.status] = (acc[job.status] || 0) + 1;
      return acc;
    }, {});

    return {
      all: totalJobs,
      new: counts.new || 0,
      saved: counts.saved || 0,
      applied: counts.applied || 0,
      hidden: counts.hidden || 0,
    };
  };

  const statusCounts = getStatusCounts();
  const totalPages = Math.ceil(totalJobs / jobsPerPage);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: 'var(--space-6)' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: 'var(--space-6)',
      }}>
        <div>
          <h1 style={{
            fontSize: 'var(--font-size-3xl)',
            fontWeight: 'var(--font-weight-bold)',
            marginBottom: 'var(--space-2)',
          }}>
            Job Matches
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-lg)' }}>
            {totalJobs} job{totalJobs !== 1 ? 's' : ''} found matching your profile and preferences
          </p>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button
            onClick={triggerJobScan}
            disabled={scanning}
            className="btn btn-primary"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              opacity: scanning ? 0.7 : 1,
            }}
          >
            {scanning ? (
              <>
                <div style={{
                  width: '16px',
                  height: '16px',
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
      </div>

      {/* Filters and Search */}
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'grid', gap: 'var(--space-4)' }}>
          {/* Status Filter Tabs */}
          <div>
            <h4 style={{
              fontSize: 'var(--font-size-sm)',
              fontWeight: 'var(--font-weight-medium)',
              color: 'var(--color-text-secondary)',
              marginBottom: 'var(--space-2)',
            }}>
              Filter by Status
            </h4>
            <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
              {[
                { key: 'all', label: `All (${statusCounts.all})` },
                { key: 'new', label: `New (${statusCounts.new})` },
                { key: 'saved', label: `Saved (${statusCounts.saved})` },
                { key: 'applied', label: `Applied (${statusCounts.applied})` },
                { key: 'hidden', label: `Hidden (${statusCounts.hidden})` },
              ].map(filter => (
                <button
                  key={filter.key}
                  onClick={() => setStatusFilter(filter.key)}
                  style={{
                    padding: 'var(--space-2) var(--space-3)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    background: statusFilter === filter.key ? 'var(--color-accent)' : 'transparent',
                    color: statusFilter === filter.key ? 'white' : 'var(--color-text-primary)',
                    fontSize: 'var(--font-size-sm)',
                    cursor: 'pointer',
                    transition: 'all var(--transition-fast)',
                  }}
                >
                  {filter.label}
                </button>
              ))}
            </div>
          </div>

          {/* Search and Sort */}
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
                <option value="match_score">Match Score</option>
                <option value="created_at">Date Found</option>
                <option value="company_name">Company</option>
                <option value="job_title">Job Title</option>
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

      {/* Jobs List */}
      {loading ? (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '300px',
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
      ) : jobs.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 'var(--space-10)' }}>
          <div style={{ fontSize: '4rem', marginBottom: 'var(--space-4)' }}>🔍</div>
          <h3 style={{
            fontSize: 'var(--font-size-xl)',
            fontWeight: 'var(--font-weight-medium)',
            marginBottom: 'var(--space-2)',
          }}>
            {searchQuery || statusFilter !== 'all' ? 'No jobs match your filters' : 'No jobs found yet'}
          </h3>
          <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-4)' }}>
            {searchQuery || statusFilter !== 'all'
              ? 'Try adjusting your search or filter criteria.'
              : 'Upload your resume and set preferences to start finding job matches.'}
          </p>
          {!searchQuery && statusFilter === 'all' && (
            <button
              onClick={() => navigate('/dashboard')}
              className="btn btn-primary"
            >
              Go to Dashboard
            </button>
          )}
        </div>
      ) : (
        <>
          {/* Job Cards */}
          <div style={{
            display: 'grid',
            gap: 'var(--space-4)',
            marginBottom: 'var(--space-6)',
          }}>
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
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              gap: 'var(--space-2)',
            }}>
              <button
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
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

              <span style={{
                padding: 'var(--space-2) var(--space-4)',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
              }}>
                Page {currentPage} of {totalPages}
              </span>

              <button
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
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