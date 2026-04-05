# Auto-Apply — Project Index

> Living index of all project files, their purposes, and dependencies.
> Updated per `rules.md` §2 whenever files are created, deleted, renamed, or substantially modified.
>
> **Last Updated:** 2026-04-05 (Phase 2 Complete)

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
| `backend/app/main.py` | FastAPI entry point, CORS, lifespan, health check, router registration | `config`, `routers/*` |
| `backend/app/config.py` | Pydantic BaseSettings — loads all env vars | `pydantic-settings` |
| `backend/app/database.py` | SQLAlchemy async engine, session factory, `get_db` dependency | `config`, `sqlalchemy`, `asyncpg` |

### Dependencies (`/backend/app/dependencies/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `dependencies/__init__.py` | Package init for dependency injection modules | — |
| `dependencies/auth.py` | JWT authentication dependency (`get_current_user`, `get_current_active_user`) | `jose`, `models/user`, `database` |

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
| `models/job.py` | `ScrapedJob` + `UserJob` models (dedup hash, match scores) | `database.Base` |
| `models/benchmark.py` | `BenchmarkScore` model (GDPR-compliant scoring) | `database.Base` |

### Pydantic Schemas (`/backend/app/schemas/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `schemas/__init__.py` | Package init | — |
| `schemas/user.py` | `UserCreate`, `UserUpdate`, `UserResponse`, `Token`, `LoginRequest` | `pydantic` |
| `schemas/resume.py` | `ResumeResponse`, `ResumeUpdate` | `pydantic` |
| `schemas/job.py` | `JobResponse`, `UserJobResponse`, `UserJobStatusUpdate` | `pydantic` |
| `schemas/benchmark.py` | `BenchmarkResponse` | `pydantic` |

### API Routers (`/backend/app/routers/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `routers/__init__.py` | Package init | — |
| `routers/auth.py` | Registration + login endpoints (stubs → Phase 2) | `schemas/user`, `database` |
| `routers/resumes.py` | CV upload + listing endpoints (stubs → Phase 2) | `database` |
| `routers/jobs.py` | Job listing + status update endpoints (stubs → Phase 2) | `database` |
| `routers/benchmarks.py` | Benchmark scores endpoint (stubs → Phase 3) | `database` |

### Business Logic Services (`/backend/app/services/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `services/__init__.py` | Package init | — |
| `services/auth_service.py` | Registration (dedup, hashing) + authentication (JWT) | `models/user`, `utils/security` |
| `services/resume_service.py` | CV upload + parsing orchestration with file handling and agent integration | `agents/cv_profiler`, `utils/file_validation` |
| `services/job_service.py` | Job matching, deduplication, and scoring with Adzuna API integration | `clients/adzuna`, `agents/job_scanner`, `utils/hashing` |
| `services/benchmark_service.py` | GDPR-compliant competitive scoring with peer group analysis | `models/user`, `models/benchmark`, `utils/statistics` |

### AI Agents (`/backend/app/agents/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `agents/__init__.py` | Package docs — agent architecture overview | — |
| `agents/cv_profiler.py` | CV parsing agent (PDF/DOCX → structured JSON via GPT-4) with text extraction and validation | `openai`, `PyPDF2`, `python-docx` |
| `agents/job_scanner.py` | Job discovery agent (Adzuna API + daily cron) with cross-platform deduplication and scoring | `openai`, `httpx`, `clients/adzuna` |
| `agents/cv_optimizer.py` | ATS rewriting + cover letter agent with keyword optimization and PDF export | `openai`, `services/pdf_export` |
| `agents/interview_coach.py` | Interview prep generator with technical/behavioral questions and cheat sheets | `openai` |
| `agents/prompts/__init__.py` | Package init for prompt engineering modules | — |
| `agents/prompts/cv_profiler.py` | GPT-4 prompts for structured CV parsing with "no fabrication" rules | — |
| `agents/prompts/cv_optimizer.py` | GPT-4 prompts for ATS optimization and cover letter generation | — |
| `agents/prompts/interview_coach.py` | GPT-4 prompts for interview question and cheat sheet generation | — |

### API Clients (`/backend/app/clients/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `clients/__init__.py` | Package init for external API clients | — |
| `clients/adzuna.py` | Adzuna job search API client with rate limiting and error handling | `httpx`, `config` |

### Utilities (`/backend/app/utils/`)

| File | Purpose | Dependencies |
|------|---------|-------------|
| `utils/__init__.py` | Package init | — |
| `utils/security.py` | Password hashing (bcrypt) + JWT creation/verification | `passlib`, `python-jose` |
| `utils/exceptions.py` | Custom exception hierarchy (`NotFoundError`, `DuplicateError`, etc.) | `fastapi` |
| `utils/file_validation.py` | File upload security validation (size, MIME type, content checking) | — |
| `utils/hashing.py` | Content hashing utilities for job deduplication | `hashlib` |
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
| `backend/tests/test_interview_coach.py` | Interview coach tests (15 scenarios: question generation, cheat sheets, tech analysis) | `conftest`, `agents/interview_coach` |
| `backend/tests/test_benchmark_service.py` | Benchmark service tests (25 scenarios: competitive scoring, GDPR compliance, peer analysis) | `conftest`, `services/benchmark_service` |
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
| `frontend/src/contexts/AuthContext.jsx` | Global authentication state with useReducer, auto-login, ProtectedRoute component | `api/client`, `react-router-dom` |

### Components

| File | Purpose | Dependencies |
|------|---------|-------------|
| `frontend/src/components/Layout.jsx` | App shell with sidebar nav (NavLink active states) | `react-router-dom` |
| `frontend/src/components/CVUpload.jsx` | Drag-and-drop file upload with validation, progress tracking, parsing result display | `api/client`, `contexts/AuthContext` |
| `frontend/src/components/JobPreferences.jsx` | Job search criteria configuration with skills management, location preferences, salary ranges | `api/client` |
| `frontend/src/components/JobCard.jsx` | Interactive job display with match score visualization, status management, action buttons | `api/client` |

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
| `frontend/src/__tests__/AuthContext.test.jsx` | Authentication context tests (15 scenarios: registration, login, protected routes, auto-login) | `@testing-library/react`, `contexts/AuthContext` |
| `frontend/src/__tests__/CVUpload.test.jsx` | File upload component tests (12 scenarios: drag-drop, validation, progress, parsing) | `@testing-library/react`, `components/CVUpload` |
| `frontend/src/__tests__/JobCard.test.jsx` | Job card component tests (10 scenarios: display, status management, actions) | `@testing-library/react`, `components/JobCard` |
| `frontend/src/__tests__/JobDetail.test.jsx` | Job detail tests (18 scenarios: AI tools, content generation, editing, export) | `@testing-library/react`, `pages/JobDetail` |
| `frontend/src/__tests__/Benchmarks.test.jsx` | Benchmarks tests (8 scenarios: opt-in management, visualization, privacy) | `@testing-library/react`, `pages/Benchmarks` |

### Utilities & Hooks

| File | Purpose | Dependencies |
|------|---------|-------------|
| `frontend/src/api/client.js` | Fetch-based API client with JWT auto-attachment, error handling, response processing | — |
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
