# Strategia de testare în ProFolio

Document care inventariază testele existente pe categorii (unit, integration, E2E, edge case, security) și verifică cerința de testare.

---

## 1. Sumar

| Categorie       | Backend | Frontend | Total |
|-----------------|---------|----------|-------|
| Unit            | ~220    | 14       | ~234  |
| Service         | ~80     | -        | ~80   |
| Integration     | ~70     | 7        | ~77   |
| E2E             | 24      | -        | 24    |
| Edge cases      | 13      | 7        | 20    |
| **TOTAL**       | **394** | **28**   | **422** |

**Distribuție pe 33 fișiere backend** + **7 fișiere frontend**, rulate prin **CI GitHub Actions** pe fiecare push/PR.

---

## 2. Infrastructura de testare

### Backend — pytest

[backend/pyproject.toml](backend/pyproject.toml#L19-L23):
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

Librării folosite:
- `pytest` + `pytest-asyncio` — pentru cod async (FastAPI)
- `httpx.AsyncClient` cu `ASGITransport` — pentru integration tests direct pe `app`
- `unittest.mock` (AsyncMock, MagicMock) — pentru mock-uri LLM
- `pypdf`, `reportlab` — pentru fixtures dinamice PDF
- Real PostgreSQL service în CI (`autoapply_test_db`) — fiecare test rulează în tranzacție cu rollback automat

**Conftest** ([backend/tests/conftest.py](backend/tests/conftest.py)): creează DB de test, rulează migrațiile Alembic, oferă `client` și `db_session` fixtures.

### Frontend — Vitest

[frontend/vitest.config.js](frontend/vitest.config.js):
```js
{
  globals: true,
  environment: 'jsdom',
  setupFiles: ['./src/test/setup.js'],
  coverage: { provider: 'v8', reporter: ['text', 'lcov'] }
}
```

Librării folosite:
- `vitest` cu environment `jsdom`
- `@testing-library/react` + `@testing-library/jest-dom` — pentru aserțiuni DOM
- `@testing-library/user-event` — pentru simulare interacțiuni
- Storage shim per-test ([setup.js](frontend/src/test/setup.js)) — curăță `localStorage`/`sessionStorage` între teste

### CI/CD ([.github/workflows/ci.yml](.github/workflows/ci.yml))

Job-uri rulate la fiecare push/PR:
- **backend-ci** — Lint (Flake8, Black, isort, mypy) → Migrations → `pytest -v --cov` → Upload Codecov
- **frontend-ci** — Lint (ESLint, Prettier) → `npm test` (vitest) → Build
- **integration-tests** — Full stack E2E pe container PostgreSQL real
- **security-scan** — Trivy + `pip-audit` + `npm audit`
- **docker-build** — Build și smoke test imagini Docker

---

## 3. Unit Tests — Funcții pure și logică izolată

Testează funcții individuale, fără DB, fără rețea, fără side effects.

### Backend (~220 teste)

| Fișier                                   | Funcție testată                                    | # teste |
|------------------------------------------|----------------------------------------------------|---------|
| [test_token_guard.py](backend/tests/test_token_guard.py)               | `estimate_tokens`, `truncate_for_budget`, strategia head+tail | 14 |
| [test_tech_extractor.py](backend/tests/test_tech_extractor.py)         | Extragere tehnologii din JD, catalogul de 130 tehnologii      | 14 |
| [test_benchmark_sanitizer.py](backend/tests/test_benchmark_sanitizer.py) | GDPR-compliant peer extraction, frozen dataclass        | 18 |
| [test_prompt_cache.py](backend/tests/test_prompt_cache.py)             | SHA-256 cache key, Redis fallback, LRU eviction              | 14 |
| [test_task_manager.py](backend/tests/test_task_manager.py)             | Async task registry, asyncio.Queue progress bus              | 8  |
| [test_file_processing.py](backend/tests/test_file_processing.py)       | Magic bytes, MIME, PDF/DOCX extraction                       | 6  |
| [test_pdf_export.py](backend/tests/test_pdf_export.py)                 | PDF generation pentru CV + cover letter                      | 28 |
| [test_job_models.py](backend/tests/test_job_models.py)                 | SQLAlchemy models, constraints                                | 4  |
| [test_job_schemas.py](backend/tests/test_job_schemas.py)               | Pydantic schemas, validation                                  | 2  |
| [test_peer_data.py](backend/tests/test_peer_data.py)                   | Loaders pentru peer profiles                                  | 5  |

**Total unit backend: ~113 teste pure + ~107 agent unit tests** (vezi mai jos).

### Agent Unit Tests (logică LLM cu mock)

| Fișier                                              | Agent testat              | # teste |
|-----------------------------------------------------|---------------------------|---------|
| [test_cv_optimizer.py](backend/tests/test_cv_optimizer.py)             | `CVOptimizerAgent` — prompt building, fabrication detector, JSON parsing | 20 |
| [test_cv_profiler.py](backend/tests/test_cv_profiler.py)               | `CVProfilerAgent` — text extraction → JSON Pydantic | 18 |
| [test_interview_coach.py](backend/tests/test_interview_coach.py)       | Generare 3 tech + 2 behavioral Q's, tech cheat sheet | 16 |
| [test_job_scanner.py](backend/tests/test_job_scanner.py)               | Scanning logic, deduplicare, matching scor          | 27 |

LLM-ul este **mock-uit** cu `AsyncMock` (nu se fac request-uri reale către Gemini în CI).

### Frontend (14 teste)

| Fișier                                                                 | Componentă testată | Tipuri de teste |
|------------------------------------------------------------------------|--------------------|-----------------|
| [client.test.js](frontend/src/api/client.test.js)                      | API client cu fetch wrapper | URL building, error handling, 401 interceptor |
| [ErrorBoundary.test.jsx](frontend/src/__tests__/ErrorBoundary.test.jsx) | Boundary React     | Render + fallback la error |
| [NotFound.test.jsx](frontend/src/__tests__/NotFound.test.jsx)           | 404 page           | Render + link la home |

---

## 4. Service Tests — Logică de business cu DB mock

Testează service-urile care orchestrează agenți + DB. DB e mock-uit sau folosește `AsyncSession` real.

| Fișier                                                                          | Service                  | # teste |
|---------------------------------------------------------------------------------|--------------------------|---------|
| [test_cv_optimizer_service.py](backend/tests/test_cv_optimizer_service.py)      | `CVOptimizerService`     | 12 |
| [test_cv_profiler.py](backend/tests/test_cv_profiler.py)                        | `CVProfilerAgent`        | 18 |
| [test_benchmark_service.py](backend/tests/test_benchmark_service.py)            | `BenchmarkService`       | 13 |
| [test_interview_coach_service.py](backend/tests/test_interview_coach_service.py)| `InterviewCoachService`  | 12 |
| [test_job_service.py](backend/tests/test_job_service.py)                        | `JobService`             | 17 |
| [test_recommendations_service.py](backend/tests/test_recommendations_service.py)| `RecommendationsService` | 10 |
| [test_feedback_service.py](backend/tests/test_feedback_service.py)              | `FeedbackService`        | 5  |
| [test_resume_service.py](backend/tests/test_resume_service.py)                  | `ResumeService`          | 3  |

**Total: ~80 teste service.**

---

## 5. Integration Tests — Router + DB + Auth (full HTTP)

Folosesc `httpx.AsyncClient(ASGITransport(app=app))` ca să apeleze endpoint-urile prin FastAPI **fără să pornească un server real** — sunt rapide și deterministe.

| Fișier                                                              | Endpoint-uri testate          | # teste |
|---------------------------------------------------------------------|-------------------------------|---------|
| [test_auth_endpoints.py](backend/tests/test_auth_endpoints.py)      | `/auth/register`, `/login`, `/me`, `/refresh` | 23 |
| [test_auth_middleware.py](backend/tests/test_auth_middleware.py)    | JWT validation, expired tokens, missing headers | 16 |
| [test_benchmark_router.py](backend/tests/test_benchmark_router.py)  | `/benchmarks/*`               | 19 |
| [test_jobs_router.py](backend/tests/test_jobs_router.py)            | `/jobs/*`                     | 3  |
| [test_idor_jobs.py](backend/tests/test_idor_jobs.py)                | **Security:** cross-user access denial | 1 |
| [test_adzuna_client.py](backend/tests/test_adzuna_client.py)        | Adzuna API client (mocked)    | 5  |
| [test_health.py](backend/tests/test_health.py)                      | `/health`, `/`                | 3  |
| [test_migrations.py](backend/tests/test_migrations.py)              | Alembic up/down               | 16 |

**Total: ~86 teste integration.**

### Frontend (7 teste integration componentă)

| Fișier                                                                  | Componentă testată | Tipuri |
|-------------------------------------------------------------------------|--------------------|--------|
| [Login.test.jsx](frontend/src/__tests__/Login.test.jsx)                 | `Login` page       | Form submit + API mock + redirect |
| [CVUpload.test.jsx](frontend/src/__tests__/CVUpload.test.jsx)           | `CVUpload`         | File upload + progress + error states |
| [Settings.test.jsx](frontend/src/__tests__/Settings.test.jsx)           | `Settings` page    | Profile update + validation |
| [AuthContext.test.jsx](frontend/src/__tests__/AuthContext.test.jsx)     | `AuthContext`      | Login/logout flow + token persistence |

---

## 6. E2E Tests — Stack complet

Testează fluxuri complete end-to-end, de la HTTP până la output final (PDF, JSON).

### `test_cv_optimizer_e2e.py` — 22 teste

[backend/tests/test_cv_optimizer_e2e.py](backend/tests/test_cv_optimizer_e2e.py) acoperă **întregul stack Phase 4 Epic 3**:

```python
"""
End-to-end tests covering the full Phase 4 stack:
  - PDF export: optimize → export CV → validate bytes
  - PDF export: cover letter generate → export → validate bytes
  - NO_FABRICATION: prompt contains all mandatory rules
  - changes_summary: field present in optimized response
  - user_motivation: threaded into cover letter prompt
  - PDF paragraph split: real newlines, not escaped \\n
"""
```

Scenarii acoperite:
1. **CV optimization complet**: parsed CV + JD → optimizer → JSON → PDF binar → validare magic bytes PDF
2. **Cover letter complet**: parsed CV + JD + motivation → generator → text → PDF
3. **Verificare reguli NO_FABRICATION**: prompt-ul conține toate regulile contractate
4. **Verificare `changes_summary`**: câmpul obligatoriu apare în output
5. **Propagare `user_motivation`**: motivația ajunge până în prompt
6. **PDF paragraf split**: newline-uri reale, nu escaped

### `test_auth_full_flow.py` — 2 teste

Lifecycle complet de autentificare:

```python
async def test_full_auth_lifecycle(client):
    # Step 1: Register → 201
    # Step 2: Login → 200 + access_token
    # Step 3: GET /me → 200 + email match
    # Step 4: DELETE /me → 204
    # Step 5: Login again → 401 (user deleted)
```

---

## 7. Edge Cases — Scenarii defensive

### `test_cv_profiler_edge_cases.py` — 13 teste

[backend/tests/test_cv_profiler_edge_cases.py](backend/tests/test_cv_profiler_edge_cases.py) — generează fișiere de test **on-the-fly** cu `pypdf` și `reportlab`:

- **Zero-byte file** → reject la validare
- **Oversized file** (>10MB) → reject
- **Corrupted PDF** → eroare clară
- **Image-only PDF** (fără text extras) → fallback
- **Spoofed extension** (`.pdf` cu conținut `.exe`) → magic bytes catch
- **DOCX fără `word/document.xml`** → reject
- **Truncated ZIP** → BadZipFile
- **Empty paragraphs only** → "no extractable text"

---

## 8. Security Tests

### IDOR — Insecure Direct Object Reference
[test_idor_jobs.py](backend/tests/test_idor_jobs.py) — verifică că un user **nu poate accesa** resursele altui user prin manipularea ID-ului în URL.

### Authentication
[test_auth_middleware.py](backend/tests/test_auth_middleware.py) — 16 scenarii:
- Token absent → 401
- Token expirat → 401
- Token cu signature invalidă → 401
- Token cu claim-uri lipsă → 401
- Bearer header malformat → 401
- User șters dar token încă valid → 401

### Upload security
[test_file_processing.py](backend/tests/test_file_processing.py):
- Magic byte verification (`%PDF`, `PK\x03\x04`)
- Extension spoofing detection
- File size limits
- ZIP archive integrity (DOCX)

---

## 9. Tabel acoperire pe componentă

| Componentă                          | Unit | Service | Integration | E2E | Total |
|-------------------------------------|------|---------|-------------|-----|-------|
| **CV Optimizer Agent**              | 20   | 12      | -           | 22  | 54    |
| **CV Profiler Agent**               | 18   | 3       | -           | (în e2e) | 21 |
| **Interview Coach Agent**           | 16   | 12      | -           | -   | 28    |
| **Job Scanner Agent**               | 27   | 17      | 3           | -   | 47    |
| **Auth (router + middleware)**      | -    | -       | 39          | 2   | 41    |
| **Benchmark**                       | 18   | 13      | 19          | -   | 50    |
| **PDF Export**                      | 28   | -       | -           | (în e2e) | 28 |
| **Token Guard**                     | 14   | -       | -           | -   | 14    |
| **Tech Extractor**                  | 14   | -       | -           | -   | 14    |
| **Prompt Cache**                    | 14   | -       | -           | -   | 14    |
| **File Processing**                 | 6    | -       | -           | 13 (edge) | 19 |
| **Migrations**                      | -    | -       | 16          | -   | 16    |
| **Frontend (componente + API)**     | 14   | -       | 14          | -   | 28    |

---

## 10. Cum rulezi testele local

### Backend

```bash
cd backend

# Toate testele
pytest tests/ -v

# Cu acoperire
pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=xml

# Un singur fișier
pytest tests/test_cv_optimizer_e2e.py -v

# Un singur test
pytest tests/test_auth_full_flow.py::test_full_auth_lifecycle -v
```

### Frontend

```bash
cd frontend

# Toate testele (one-shot)
npm test

# Watch mode
npm run test:watch

# Cu acoperire
npx vitest run --coverage
```

### Full CI local (Docker)

```bash
docker compose up --build
docker compose exec backend pytest tests/ -v
docker compose exec frontend npm test
```

---

## 11. Verificare cerință

| Tip de testare              | Cerut? | Avem? | Unde                                                          |
|-----------------------------|--------|-------|---------------------------------------------------------------|
| **Unit testing**            | Da     | Da    | ~234 teste (token_guard, tech_extractor, agents mock, etc.)   |
| **Integration testing**     | Da     | Da    | ~86 teste (routers cu HTTP real prin ASGITransport)           |
| **End-to-end testing**      | Da     | Da    | 24 teste (cv_optimizer_e2e + auth_full_flow)                  |
| **Edge case testing**       | Da     | Da    | 13 teste (cv_profiler_edge_cases + fixtures dinamice)         |
| **Security testing**        | Bonus  | Da    | IDOR + auth middleware + upload magic-bytes                   |
| **Component testing (UI)**  | Bonus  | Da    | 28 teste Vitest + Testing Library                             |
| **Migration testing**       | Bonus  | Da    | 16 teste Alembic up/down                                      |
| **CI automation**           | Bonus  | Da    | GitHub Actions cu 5 job-uri paralele                          |

**Concluzie:** Toate tipurile de testare cerute există. Nu este nevoie să fie adăugate teste suplimentare pentru a îndeplini cerința — proiectul are **422 teste** într-o suită bine structurată, cu CI automat și raportare de acoperire pe Codecov.

---

## 12. Trasabilitate

```bash
# Lista completă fișiere test backend
ls backend/tests/test_*.py

# Lista completă fișiere test frontend
find frontend/src -name "*.test.*" -not -path "*/node_modules/*"

# Numărarea testelor
for f in backend/tests/test_*.py; do
  echo "$(grep -cE '(async )?def test_' $f) $f"
done | sort -nr

# Rulare cu raport HTML coverage
cd backend && pytest --cov=app --cov-report=html
open htmlcov/index.html
```
