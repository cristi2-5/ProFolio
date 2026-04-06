# Job Scanner Engine Documentation

The Job Scanner Engine is responsible for autonomous job discovery, deduplication, and user-centric matching. 

## Architecture

The engine consists of three main components:

1.  **Job Scanner Agent (`JobScannerAgent`)**: 
    - Interfaces with the Adzuna API.
    - Handles pagination and rate limiting.
    - Per-user preference filtering.
2.  **Deduplication Logic**:
    - Uses SHA-256 hashing of job descriptions to catch cross-platform duplicates.
    - Checks external URLs for direct duplicates.
3.  **Matching Engine (`JobService`)**:
    - Calculates a compatibility score (0-100) based on skill overlap and preferences.
    - Default production threshold: **30% match**.

## Adzuna Integration

We use Adzuna as our primary source due to its structured JSON output and generous free tier. 
Requires:
- `ADZUNA_APP_ID`
- `ADZUNA_APP_KEY`

## Database Schema

- `scraped_jobs`: Global repository of discovered positions.
- `user_jobs`: Per-user associations, match scores, and application status.
