/**
 * Application Constants.
 *
 * Centralized configuration values used across the frontend.
 */

/** Base URL for the API (proxied by Vite in dev). */
export const API_BASE_URL = '/api';

/** Application display name. */
export const APP_NAME = 'Auto-Apply';

/** Application tagline. */
export const APP_TAGLINE = 'Job Hunter & Interview Strategist';

/** Valid seniority levels for profile configuration. */
export const SENIORITY_LEVELS = ['intern', 'junior', 'mid', 'senior'];

/** Valid job location types. */
export const LOCATION_TYPES = ['remote', 'hybrid', 'onsite'];

/** Job status options for the pipeline. */
export const JOB_STATUSES = ['new', 'applied', 'saved', 'hidden', 'duplicate'];

/** Minimum peer group size for valid benchmark scores. */
export const MIN_BENCHMARK_PEERS = 30;

/**
 * Technical niche options for Mid/Senior benchmarking.
 * @type {string[]}
 */
export const NICHE_OPTIONS = [
  'Frontend',
  'Backend',
  'Full Stack',
  'Mobile',
  'DevOps',
  'Data Science',
  'Machine Learning',
  'QA / Testing',
  'Security',
  'Cloud / Infrastructure',
];
