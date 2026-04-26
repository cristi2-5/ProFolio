# Auto-Apply — Project Index

> Living index of all project files, their purposes, and dependencies.
> Updated per `rules.md` §2 whenever files are created, deleted, renamed, or substantially modified.
>
> **Last Updated:** 2026-04-26 (Security & Quality Audit Remediation — auth hardening, IDOR fixes, file-upload security, LLM resilience, race-condition guards, frontend critical bugs, CI strictness)

---

## 🏗 Tech Stack Decisions (for the team)

| Component          | Choice                          | Rationale                                         |
|--------------------|---------------------------------|---------------------------------------------------|
| **LLM Provider**   | OpenAI GPT-4                    | Most mature structured-output API, widely adopted |
| **Job API**        | Adzuna API                      | Free tier, legal compliance, structured JSON      |
| **File Storage**   | Local filesystem (→ S3 later)   | Simple start, S3-ready abstraction planned        |
| **Deployment**     | Docker Compose (local)          | Easy onboarding, Railway-ready for production     |
| **Auth**           | JWT (HS256) + OAuth (Phase 2)   | Stateless, scalable, industry standard            |

---

## 📁 Root Files

| File | Purpose | Dependencies |
|------|---------|-------------|
| `rules.md` | Agent workflow rules, coding standards, git protocol, logging template | — |
| `README.md` | Project overview, user stories, acceptance criteria | — |
| `project_index.md` | This file — living file index | — |
| `log.txt` | Audit log per `rules.md` §7 format | — |
| `.gitignore` | Git exclusion rules for Python, Node, Docker, IDE files | — |
| `.env.example` | Environment variable template (no secrets) | — |
| `docker-compose.yml` | Dev environment: PostgreSQL + Backend + Frontend | `backend/Dockerfile`, `frontend/Dockerfile` |

---

## 🐍 Backend (`/backend`)

### Core Application

| File | Purpose | Dependencies |
|------|---------|-------------|
| `backend/app/__init__.py` | Package init | — |
| `backend/app/main.py` | FastAPI entry point, CORS, lifespan, health check, router registration, **APScheduler 24h job scan cron**; **Phase 8 — registers `app.state.limiter` + `SlowAPIMiddleware` + `RateLimitExceeded` handler; APScheduler `max_instances=1`+`coalesce=True`; cron callback wraps `pg_advisory_lock`; `/health` runs `SELECT 1` and returns 503 on DB failure** | `config`, `routers/*`, `apscheduler`, `slowapi`, `utils/rate_limit` |
| `backend/app/config.py` | Pydantic BaseSettings — loads all env vars, **+ job_scan_interval_hours, job_scan_rate_limit_hours**; **Phase 8 — `model_validator(mode="after")` refuses startup in production with default or <32-char SECRET_KEY; `max_resumes_per_user: int = 5`** | `pydantic-settings` |
| `backend/app/database.py` | SQLAlchemy async engine, session factory, `get_db` dependency | `config`, `sqlalchemy`, `asyncpg` |

### Dependencies (`/backend/app/dependencies/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `dependencies/__init__.py` | Package init for dependency injection modules | — |
| `dependencies/auth.py` | JWT authentication dependency (`get_current_user`, `get_current_active_user`) | `jose`, `models/user`, `database` |
| `dependencies/jobs.py` | **Phase 8 — IDOR helper `get_user_job_or_403(job_id, user, db)`; single SELECT...JOIN happy path, second SELECT only on miss to disambiguate 404 vs 403** | `models/job`, `models/user` |

### Middleware (`/backend/app/middleware/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `middleware/__init__.py` | Package init for middleware modules | — |
| `middleware/rate_limit.py` | Rate limiting middleware (100/min default, slowapi) | `slowapi` |
| `middleware/security_headers.py` | OWASP security headers middleware (XSS, clickjacking protection) | `starlette` |

### ORM Models (`/backend/app/models/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `models/__init__.py` | Exports all models for Alembic auto-discovery | All model files |
| `models/user.py` | `User` + `JobPreference` models (auth, GDPR opt-in, seniority) | `database.Base` |
| `models/resume.py` | `ParsedResume` model (JSONB for parsed CV data) | `database.Base` |
| `models/job.py` | `ScrapedJob` + `UserJob` models (dedup hash, match scores, **applied_at timestamp**) | `database.Base` |
| `models/benchmark.py` | `BenchmarkScore` model (GDPR-compliant scoring) | `database.Base` |
| `models/feedback.py` | **Phase 7 — Feedback model (user-authored ratings + comments on AI output; discriminated by content_type)** | `database.Base` |

### Pydantic Schemas (`/backend/app/schemas/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `schemas/__init__.py` | Package init | — |
| `schemas/user.py` | `UserCreate`, `UserUpdate`, `UserResponse`, `Token`, `LoginRequest` | `pydantic` |
| `schemas/resume.py` | `ResumeResponse`, `ResumeUpdate` | `pydantic` |
| `schemas/job.py` | `JobResponse`, `UserJobResponse` (**+applied_at**), `UserJobListResponse` (paginated), `UserJobStatusUpdate` | `pydantic` |
| `schemas/benchmark.py` | `BenchmarkResponse` | `pydantic` |

### API Routers (`/backend/app/routers/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `routers/__init__.py` | Package init | — |
| `routers/auth.py` | Registration + login endpoints (stubs → Phase 2) | `schemas/user`, `database` |
| `routers/resumes.py` | CV upload + listing endpoints (stubs → Phase 2) | `database` |
| `routers/jobs.py` | Job listing (**paginated, searchable, sortable**) + status update + **real scan trigger (rate-limited 1/hr)** + interview/benchmark endpoints | `database`, `agents/job_scanner` |
| `routers/benchmarks.py` | Benchmark scores endpoint (stubs → Phase 3) | `database` |
| `routers/tasks.py` | **Phase 7 — poll + SSE stream endpoints for background agent tasks (`/api/tasks/{id}`, `/api/tasks/{id}/events`)** | `services/task_manager` |
| `routers/feedback.py` | **Phase 7 — beta-launch endpoints: submit feedback, list own history, aggregate stats** | `services/feedback_service`, `schemas/feedback` |

### Business Logic Services (`/backend/app/services/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `services/__init__.py` | Package init | — |
| `services/auth_service.py` | Registration (dedup, hashing) + authentication (JWT) | `models/user`, `utils/security` |
| `services/resume_service.py` | CV upload + parsing orchestration with file handling and agent integration; **Phase 8 — per-user resume quota check (5 max) raises HTTPException(413) before any disk write** | `agents/cv_profiler`, `utils/file_validation` |
| `services/job_service.py` | Job matching, deduplication, scoring — **list with search/sort/pagination+total_count, update sets applied_at**; **Phase 8 — `update_job_status` is now a single atomic `UPDATE...RETURNING ... WHERE applied_at IS NULL` with idempotent re-apply (returns 200 + current state instead of duplicating `applied_at`)** | `clients/adzuna`, `agents/job_scanner`, `utils/hashing` |
| `services/benchmark_service.py` | **Phase 6 / Epic 5 — peer-average-weighted competitive scoring (US 5.1/5.2) with 30-peer minimum, sanitized peer pool, top-3 skill gap ranking** | `models/user`, `models/benchmark`, `utils/benchmark_sanitizer` |
| `services/recommendations_service.py` | **Phase 6 / Epic 5 — aggregate Set A − Set B across all saved JDs for Top 3 missing skills + ATS keyword suggestions (US 5.3)** | `models/job`, `models/user`, `utils/benchmark_sanitizer` |
| `services/task_manager.py` | **Phase 7 — async task registry with SSE progress bus; in-process singleton with TTL-based GC** | `asyncio` |
| `services/feedback_service.py` | **Phase 7 — beta-launch feedback persistence + aggregate stats per content type** | `models/feedback` |

### AI Agents (`/backend/app/agents/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `agents/__init__.py` | Package docs — agent architecture overview | — |
| `agents/cv_profiler.py` | CV parsing agent (PDF/DOCX → structured JSON via GPT-4) with text extraction and validation; **Phase 8 — raises `CVProfilerError` (422) on Pydantic validation failure instead of returning empty `ParsedCVData()`; user CV text wrapped via `_prompt_safety`; OpenAI call wrapped in `with_retry`** | `openai`, `PyPDF2`, `python-docx`, `agents/_prompt_safety`, `utils/llm_retry` |
| `agents/job_scanner.py` | Job discovery agent (Adzuna API + 24h APScheduler cron) — **lazy Adzuna client, graceful missing-key handling**; **Phase 8 — `normalize_company_name()` strips `Inc/Ltd/LLC/Corp/...` for dedup; fuzzy-match path acquires `pg_advisory_xact_lock` keyed on a deterministic SHA-256-derived 63-bit int (NOT Python's per-process-random `hash()`); skipped on non-PG dialects** | `openai`, `httpx`, `clients/adzuna` |
| `agents/cv_optimizer.py` | ATS rewriting + cover letter agent with keyword optimization and PDF export; **Phase 8 — full Pydantic `OptimizedCV` validation on LLM output; `with_retry` + `AgentError` mapping; JD/CV inputs sanitized via `_prompt_safety`; heuristic `_detect_potential_fabrications` flags suspicious tech tokens absent from source CV (non-blocking warning)** | `openai`, `services/pdf_export`, `agents/_prompt_safety`, `utils/llm_retry`, `schemas/cv_optimizer` |
| `agents/interview_coach.py` | **Phase 5 / Epic 4 Interview Coach Agent — 3 technical + 2 behavioral questions with ideal-answer guidance + tech cheat sheet driven by deterministic extractor**; **Phase 8 — Pydantic validation on technical/behavioral/cheat-sheet outputs; `with_retry` + `AgentError`; JD wrapped via `_prompt_safety`; `jd_truncated`/`jd_truncation_chars_dropped` propagated to response** | `openai`, `agents/prompts/interview_coach`, `utils/tech_extractor`, `agents/_prompt_safety`, `utils/llm_retry` |
| `agents/prompts/__init__.py` | Package init for prompt engineering modules | — |
| `agents/prompts/interview_coach.py` | **Prompt builders for the Interview Coach — technical, behavioral, and cheat-sheet prompts with strict JSON contracts; Phase 8 — system prompt notes BEGIN/END markers as untrusted user data** | — |
| `agents/_prompt_safety.py` | **Phase 8 — basic prompt-injection mitigation: `sanitize_user_text(text, max_chars=50_000)` strips role tags (`<system>`/`<user>`/`<assistant>`); `wrap_user_content(label, content)` adds BEGIN/END delimiters so the LLM can be told to treat enclosed spans as untrusted** | — |

### API Clients (`/backend/app/clients/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `clients/__init__.py` | Package init for external API clients | — |
| `clients/adzuna.py` | Adzuna job search API client with rate limiting and error handling — **lazy singleton via get_adzuna_client()** | `httpx`, `config` |

### Utilities (`/backend/app/utils/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `utils/__init__.py` | Package init | — |
| `utils/security.py` | Password hashing (bcrypt) + JWT creation/verification; **Phase 8 — UTF-8 truncation hack removed; raises `ValueError` if password >72 bytes (validation now happens in the schema layer at registration)** | `passlib`, `python-jose` |
| `utils/exceptions.py` | Custom exception hierarchy (`NotFoundError`, `DuplicateError`, etc.); **Phase 8 — `AgentError` family (CVProfilerError 422, CVOptimizerError 422, InterviewCoachError 422, LLMRateLimitError 429, LLMUnavailableError 503, LLMConfigurationError 500)** | `fastapi` |
| `utils/file_validation.py` | File upload security validation (size, MIME type, content checking) | — |
| `utils/hashing.py` | Content hashing utilities for job deduplication | `hashlib` |
| `utils/tech_extractor.py` | **Phase 5 / Epic 4 — deterministic extraction of technologies from JD text using a curated catalog + smart-boundary regex** | — |
| `utils/benchmark_sanitizer.py` | **Phase 6 / Epic 5 — GDPR data sanitization; yields `SanitizedProfile` with only seniority/niche/years/skills, decoupled from user_id (US 5.1)** | `utils/tech_extractor` |
| `utils/token_guard.py` | **Phase 7 — approximate-token estimator + deterministic head+tail JD truncation to stay inside LLM context budgets** | — |
| `utils/prompt_cache.py` | **Phase 7 — content-hash prompt cache with Redis backend (optional) or in-memory LRU fallback; shared singleton across agents** | `config`, `redis` (optional) |
| `utils/rate_limit.py` | **Phase 8 — central slowapi `Limiter` + `user_id_key(request)` helper that decodes Bearer JWT to derive a per-user limit key (falls back to remote address)** | `slowapi`, `jose`, `config` |
| `utils/llm_retry.py` | **Phase 8 — `with_retry(coro_factory, max_retries=2)` wraps OpenAI calls with exponential backoff (1s, 4s) on RateLimit/Timeout/Connection; immediate fail on Auth/BadRequest; maps SDK errors to AgentError subclasses** | `openai`, `utils/exceptions` |
| `services/pdf_export.py` | PDF generation service for ATS-optimized CVs and cover letters | `reportlab` |

### Testing & Configuration

| File | Purpose | Dependencies |
|------|---------|-------------|
| `backend/tests/__init__.py` | Package init | — |
| `backend/tests/conftest.py` | Pytest fixtures — async HTTP test client, test database session with transaction rollback, authenticated test client | `httpx`, `app.main`, `sqlalchemy` |
| `backend/tests/test_health.py` | `/health` endpoint tests (happy path + validation) | `conftest` |
| `backend/tests/test_migrations.py` | Database migration validation tests (27 scenarios: constraints, indexes, CASCADE) | `conftest`, `models/*` |
| `backend/tests/test_auth_middleware.py` | Auth middleware tests (16 scenarios: JWT validation, rate limiting, security headers) | `conftest`, `dependencies/auth`, `middleware/*` |
| `backend/tests/test_auth_endpoints.py` | Auth endpoint tests (20 scenarios: registration, login, JWT integration) | `conftest`, `routers/auth`, `services/auth_service` |
| `backend/tests/test_cv_profiler.py` | CV parsing agent tests (22 scenarios: PDF/DOCX extraction, GPT-4 integration, validation) | `conftest`, `agents/cv_profiler` |
| `backend/tests/test_job_scanner.py` | Job discovery tests (28 scenarios: Adzuna API, deduplication, scoring, cron jobs) | `conftest`, `agents/job_scanner`, `clients/adzuna` |
| `backend/tests/test_cv_optimizer.py` | CV optimization tests (18 scenarios: ATS rewriting, cover letters, PDF export) | `conftest`, `agents/cv_optimizer` |
| `backend/tests/test_tech_extractor.py` | **Phase 5 / Epic 4 — deterministic tech extractor tests (15 scenarios: catalog matches, word boundaries, frequency ranking, category grouping)** | `utils/tech_extractor` |
| `backend/tests/test_interview_coach.py` | **Phase 5 / Epic 4 — Interview Coach Agent tests (16 scenarios: technical/behavioral/cheat-sheet generation, dev-mode mocks, error handling)** | `agents/interview_coach`, `utils/tech_extractor` |
| `backend/tests/test_interview_coach_service.py` | **Phase 5 / Epic 4 — Interview Coach Service tests (12 scenarios: background inclusion, rollback on failure, merge-update, list summarisation)** | `services/interview_coach_service` |
| `backend/tests/test_benchmark_sanitizer.py` | **Phase 6 / Epic 5 — sanitizer tests (16 scenarios: GDPR field invariants, skill normalisation, years-of-experience fallbacks, JD requirement parsing)** | `utils/benchmark_sanitizer` |
| `backend/tests/test_benchmark_service.py` | **Phase 6 / Epic 5 — benchmark service tests (14 scenarios: peer-weighted scoring, insufficient-peer raise, opt-in enforcement, mid/senior niche gate)** | `services/benchmark_service` |
| `backend/tests/test_recommendations_service.py` | **Phase 6 / Epic 5 — recommendations tests (11 scenarios: cross-JD demand counting, peer-frequency weighting, insufficient-peer graceful mode)** | `services/recommendations_service` |
| `backend/tests/test_token_guard.py` | **Phase 7 QA — token estimator + head+tail truncation tests (14 scenarios: boundary budgets, head_ratio, stability, realistic JD sanity)** | `utils/token_guard` |
| `backend/tests/test_prompt_cache.py` | **Phase 7 — prompt cache tests (16 scenarios: key stability, in-memory LRU, eviction, disabled mode, malformed-data fail-safe)** | `utils/prompt_cache` |
| `backend/tests/test_task_manager.py` | **Phase 7 — async task manager tests (10 scenarios: lifecycle, SSE ordering, owner enforcement, exception-to-FAILED)** | `services/task_manager` |
| `backend/tests/test_feedback_service.py` | **Phase 7 — feedback service tests (5 scenarios: create happy path, DB rollback, list ordering, aggregate math)** | `services/feedback_service` |
| `backend/tests/test_cv_profiler_edge_cases.py` | **Phase 7 QA — weird-PDF edge cases (14 scenarios: zero byte, oversized, image-only, corrupted, spoofed extensions, empty DOCX, happy path)** | `utils/file_processing` |
| `backend/tests/test_file_processing.py` | **Phase 8 — magic-byte verification tests (6 scenarios: %PDF happy/spoofed, ZIP-without-document.xml, .docx with bogus magic, empty file, unsupported extension)** | `utils/file_processing` |
| `backend/tests/test_resume_service.py` | **Phase 8 — quota tests (3 scenarios: under-quota success, at-quota raises 413, well-over-quota raises 413)** | `services/resume_service` |
| `backend/tests/test_peer_data.py` | **Phase 8 — peer sanitiser invariants (4 scenarios across SanitizedProfile shape, opt-out exclusion, requesting-user exclusion from own pool, 30-peer threshold raise)** | `services/peer_data`, `utils/benchmark_sanitizer` |
| `backend/tests/test_cv_optimizer_e2e.py` | **CV optimizer E2E tests (PDF export bytes validation, prompt rules check, changes_summary validation)** | `conftest`, `agents/cv_optimizer`, `utils/pdf_export` |
| `backend/tests/test_job_scanner.py` | **Job Scanner Agent tests (25 scenarios: dedup URL/hash, scan happy/error, cron, hashing)** | `conftest`, `agents/job_scanner`, `utils/hashing` |
| `backend/tests/test_job_service.py` | **Job Service tests (15 scenarios: list_user_jobs pagination/search/sort, update_job_status+applied_at, match_jobs)** | `conftest`, `services/job_service` |
| `backend/tests/test_benchmark_router.py` | Benchmark API tests (20 scenarios: calculation endpoints, opt-in management, privacy) | `conftest`, `routers/benchmarks` |
| `backend/tests/fixtures/sample.pdf` | Test PDF file for CV parsing validation | — |
| `backend/tests/fixtures/sample.docx` | Test DOCX file for CV parsing validation | — |
| `backend/pyproject.toml` | Black, isort, Flake8, pytest, mypy config | — |
| `backend/requirements.txt` | Production Python dependencies | — |
| `backend/requirements-dev.txt` | Dev/test Python dependencies | `requirements.txt` |
| `backend/alembic.ini` | Alembic migration config | — |
| `backend/alembic/env.py` | Async migration environment | `database`, `models/*` |
| `backend/alembic/versions/001_create_users_and_job_preferences.py` | Migration for users & job_preferences tables | `alembic` |
| `backend/alembic/versions/002_create_parsed_resumes.py` | Migration for parsed_resumes table with JSONB + GIN index | `alembic` |
| `backend/alembic/versions/003_create_scraped_jobs_and_user_jobs.py` | Migration for scraped_jobs & user_jobs with dedup hash | `alembic` |
| `backend/alembic/versions/004_create_benchmark_scores.py` | Migration for benchmark_scores table (GDPR-compliant) | `alembic` |
| `backend/alembic/versions/005_add_applied_at_to_user_jobs.py` | **Additive migration: nullable applied_at TIMESTAMPTZ on user_jobs** | `alembic` |
| `backend/alembic/versions/006_create_feedback.py` | **Phase 7 — feedback table with rating/content_type CHECK constraints + (user_id, created_at) index** | `alembic` |
| `backend/app/dependencies/__init__.py` | Package init for auth dependencies | — |
| `backend/app/dependencies/auth.py` | JWT authentication dependency (`get_current_user`, `get_current_user_optional`) | `app.utils.security`, `app.models.user` |
| `backend/app/middleware/__init__.py` | Package init for middleware | — |
| `backend/app/middleware/rate_limit.py` | Rate limiting middleware (100/hour anonymous, 1000/hour auth, 10/15min auth endpoints) | `slowapi`, `app.dependencies.auth` |
| `backend/app/middleware/security_headers.py` | OWASP security headers middleware (CSP, HSTS, X-Frame-Options, etc.) | `fastapi` |
| `backend/Dockerfile` | Production Docker image (Python 3.11-slim) | `requirements.txt` |

---

## ⚛️ Frontend (`/frontend`)

### Core Application

| File | Purpose | Dependencies |
|------|---------|-------------|
| `frontend/index.html` | HTML entry point with SEO meta, Inter font | — |
| `frontend/src/main.jsx` | React DOM entry point | `App.jsx`, `index.css` |
| `frontend/src/App.jsx` | Root component with React Router, authentication routes, protected routes | `contexts/AuthContext`, `components/Layout`, pages |
| `frontend/src/App.css` | Layout-specific styles (sidebar, main content) | — |
| `frontend/src/index.css` | Design system — CSS tokens, utilities, animations | — |

### Context & State Management

| File | Purpose | Dependencies |
|------|---------|-------------|
| `frontend/src/contexts/AuthContext.jsx` | Global authentication state with useReducer, auto-login, ProtectedRoute component; **Phase 8 — inline `decodeJWT`/`getTokenExpMs` (no jwt-decode dep); rejects already-expired tokens on init; schedules auto-logout 1s after `exp`; listens for `auth:logout` events from API client + stores `returnTo` in sessionStorage; `ProtectedRoute` uses `<Navigate to="/login" state={{ from: location }} replace />` instead of `window.location.href`** | `api/client`, `react-router-dom` |

### Components

| File | Purpose | Dependencies |
|------|---------|-------------|
| `frontend/src/components/Layout.jsx` | App shell with sidebar nav (NavLink active states) | `react-router-dom` |
| `frontend/src/components/CVUpload.jsx` | Drag-and-drop file upload with validation, progress tracking, parsing result display; **Phase 8 — bug fix: `useState(() => fetchResumes(), [])` was a typo for `useEffect` so the resume list never loaded on mount** | `api/client`, `contexts/AuthContext` |
| `frontend/src/components/JobPreferences.jsx` | Job search criteria configuration with skills management, location preferences, salary ranges | `api/client` |
| `frontend/src/components/JobCard.jsx` | Interactive job display with match score visualization, status management, action buttons | `api/client` |
| `frontend/src/components/GdprConsentModal.jsx` | **Phase 6 / Epic 5 — GDPR opt-in/opt-out popup shown on first Benchmarks visit (US 5.1)** | — |
| `frontend/src/components/FeedbackWidget.jsx` | **Phase 7 — compact 5-star feedback widget with optional comment; persists "already submitted" per artefact in localStorage** | `api/client` |

### Pages

| File | Purpose | Dependencies |
|------|---------|-------------|
| `frontend/src/pages/Dashboard.jsx` | Main dashboard with real-time backend integration, profile completion wizard, job statistics | `contexts/AuthContext`, `components/CVUpload`, `components/JobPreferences` |
| `frontend/src/pages/Login.jsx` | Authentication page with real API integration, validation, error handling, redirect logic | `contexts/AuthContext` |
| `frontend/src/pages/Resumes.jsx` | Resume management page with upload, listing, parsing status, and editing | `components/CVUpload`, `api/client` |
| `frontend/src/pages/Jobs.jsx` | Job listing with filtering, sorting, search, status management, pagination integration | `components/JobCard`, `api/client` |
| `frontend/src/pages/JobDetail.jsx` | Comprehensive job analysis with AI tools integration, tabbed interface, real-time content generation | `api/client`, `contexts/AuthContext` |
| `frontend/src/pages/Benchmarks.jsx` | GDPR opt-in management, competitive scoring visualization, skill gap recommendations, peer group insights | `api/client`, `contexts/AuthContext` |

### Testing

| File | Purpose | Dependencies |
|------|---------|-------------|
| `frontend/vitest.config.js` | **Phase 8 — Vitest config: jsdom env (`url: 'http://localhost/'` for non-opaque origin), globals enabled, v8 coverage, references setup file** | `vitest`, `vite` |
| `frontend/src/test/setup.js` | **Phase 8 — Vitest setup: registers `@testing-library/jest-dom/vitest` matchers, `cleanup()` after each test, memory-storage shim for `localStorage`/`sessionStorage` (Node 25 + Vitest 4 + jsdom Storage-prototype shadowing workaround)** | `@testing-library/jest-dom` |
| `frontend/src/api/client.test.js` | **Phase 8 — API client tests (2 scenarios: 2xx parse path, 401 clears `access_token` and dispatches `auth:logout` event)** | `vitest`, `api/client` |
| `frontend/src/__tests__/AuthContext.test.jsx` | Authentication context tests (15 scenarios: registration, login, protected routes, auto-login) | `@testing-library/react`, `contexts/AuthContext` |
| `frontend/src/__tests__/CVUpload.test.jsx` | File upload component tests (12 scenarios: drag-drop, validation, progress, parsing) | `@testing-library/react`, `components/CVUpload` |
| `frontend/src/__tests__/JobCard.test.jsx` | Job card component tests (10 scenarios: display, status management, actions) | `@testing-library/react`, `components/JobCard` |
| `frontend/src/__tests__/JobDetail.test.jsx` | Job detail tests (18 scenarios: AI tools, content generation, editing, export) | `@testing-library/react`, `pages/JobDetail` |
| `frontend/src/__tests__/Benchmarks.test.jsx` | Benchmarks tests (8 scenarios: opt-in management, visualization, privacy) | `@testing-library/react`, `pages/Benchmarks` |

### Utilities & Hooks

| File | Purpose | Dependencies |
|------|---------|-------------|
| `frontend/src/api/client.js` | Fetch-based API client with JWT auto-attachment, error handling, response processing; **Phase 8 — `signal` passthrough for AbortController; on 401 clears `access_token` and dispatches `auth:logout` CustomEvent with `returnTo` detail** | — |
| `frontend/src/hooks/useAuth.js` | Auth state hook (login, register, logout) | `api/client` |
| `frontend/src/utils/constants.js` | App constants (seniority levels, niches, statuses) | — |

### Configuration & Build

| File | Purpose | Dependencies |
|------|---------|-------------|
| `frontend/vite.config.js` | Vite config with API proxy to :8000 | `@vitejs/plugin-react` |
| `frontend/package.json` | Node dependencies and scripts | — |
| `frontend/.prettierrc` | Prettier formatting config | — |
| `frontend/eslint.config.js` | ESLint config (auto-generated by Vite) | — |
| `frontend/Dockerfile` | Production Docker image (Node build → nginx serve) | — |

---

## 🔄 CI/CD

| File | Purpose | Dependencies |
|------|---------|-------------|
| `.github/workflows/ci.yml` | GitHub Actions — backend lint/test, frontend lint/build, Docker build | All source files |
