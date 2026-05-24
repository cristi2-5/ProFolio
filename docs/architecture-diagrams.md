# Diagrame arhitectură ProFolio

Acest document conține:
1. **Diagramă de arhitectură** la nivel înalt (componente)
2. **Diagramă C4 — Context + Container**
3. **Diagramă UML — Class diagram** (modele DB + relații)
4. **Diagramă ER** (Entity-Relationship)
5. **Workflow — Upload + parsare CV**
6. **Workflow — Scanare joburi**
7. **Workflow — Optimizare CV + Cover Letter**
8. **Workflow — Authentication & JWT**
9. **Sequence diagram — Generare materiale aplicare**
10. **State diagram — Status UserJob**
11. **Deployment diagram**

Diagramele sunt în format **Mermaid** și se randează automat în GitHub, VS Code (cu extensia Markdown Preview Mermaid Support), și pe majoritatea platformelor de Markdown.

---

## 1. Arhitectura componentelor (high-level)

```mermaid
graph TB
    subgraph "Client Browser"
        UI[React SPA<br/>Vite + React Router]
    end

    subgraph "Backend API — FastAPI"
        AUTH[Auth Router<br/>JWT]
        RES[Resumes Router]
        JOBS[Jobs Router]
        CVO[CV Optimizer Router]
        BENCH[Benchmarks Router]
        FB[Feedback Router]
        TASKS[Tasks Router<br/>SSE]
    end

    subgraph "Service Layer"
        AUTH_SVC[AuthService]
        RES_SVC[ResumeService]
        JOB_SVC[JobService]
        CVO_SVC[CVOptimizerService]
        IC_SVC[InterviewCoachService]
        BENCH_SVC[BenchmarkService]
        REC_SVC[RecommendationsService]
        FB_SVC[FeedbackService]
        TM[TaskManager<br/>asyncio.Queue]
    end

    subgraph "AI Agents"
        CVP[CV Profiler<br/>parsing]
        CVOA[CV Optimizer<br/>ATS + Cover Letter]
        IC[Interview Coach]
        JS[Job Scanner]
    end

    subgraph "Utils & Infra"
        FP[File Processing<br/>pypdf/python-docx]
        TG[Token Guard]
        PS[Prompt Safety]
        PC[Prompt Cache<br/>Redis/LRU]
        PDF[PDF Export<br/>reportlab]
    end

    subgraph "External APIs"
        GEMINI[Google Gemini<br/>OpenAI-compat]
        ADZUNA[Adzuna Jobs API]
    end

    subgraph "Storage"
        DB[(PostgreSQL<br/>JSONB)]
        REDIS[(Redis<br/>optional)]
        FS[File System<br/>uploads/]
    end

    UI -->|HTTPS + JWT| AUTH
    UI -->|HTTPS + JWT| RES
    UI -->|HTTPS + JWT| JOBS
    UI -->|HTTPS + JWT| CVO
    UI -->|HTTPS + JWT| BENCH
    UI -->|SSE| TASKS

    AUTH --> AUTH_SVC
    RES --> RES_SVC
    JOBS --> JOB_SVC
    CVO --> CVO_SVC
    BENCH --> BENCH_SVC
    FB --> FB_SVC

    RES_SVC --> CVP
    RES_SVC --> FS
    CVO_SVC --> CVOA
    JOB_SVC --> JS
    IC_SVC --> IC
    BENCH_SVC --> REC_SVC

    CVP --> FP
    CVP --> PS
    CVOA --> TG
    CVOA --> PS
    CVOA --> PC
    IC --> PC

    CVP -->|Gemini API| GEMINI
    CVOA -->|Gemini API| GEMINI
    IC -->|Gemini API| GEMINI
    JS -->|Adzuna API| ADZUNA

    PC -.->|cache hit| REDIS
    CVO_SVC --> PDF

    AUTH_SVC --> DB
    RES_SVC --> DB
    JOB_SVC --> DB
    CVO_SVC --> DB
    BENCH_SVC --> DB
    FB_SVC --> DB
    TM --> DB

    style UI fill:#61dafb,stroke:#000,color:#000
    style GEMINI fill:#4285f4,stroke:#000,color:#fff
    style ADZUNA fill:#ff6b35,stroke:#000,color:#fff
    style DB fill:#336791,stroke:#000,color:#fff
    style REDIS fill:#dc382d,stroke:#000,color:#fff
```

---

## 2. C4 — Context & Containers

### Context (System Context Diagram)

```mermaid
graph TB
    USER([Job Seeker])
    ADMIN([Administrator])
    SYSTEM[ProFolio<br/>AI-powered job application platform]
    GEMINI[Google Gemini<br/>LLM provider]
    ADZUNA[Adzuna<br/>Jobs API aggregator]

    USER -->|"Upload CV, scan jobs,<br/>optimize, apply"| SYSTEM
    ADMIN -->|"Monitor, review feedback"| SYSTEM
    SYSTEM -->|"Parse / optimize<br/>CV & cover letter"| GEMINI
    SYSTEM -->|"Fetch job listings"| ADZUNA

    style USER fill:#08427b,stroke:#000,color:#fff
    style ADMIN fill:#08427b,stroke:#000,color:#fff
    style SYSTEM fill:#1168bd,stroke:#000,color:#fff
    style GEMINI fill:#999999,stroke:#000,color:#fff
    style ADZUNA fill:#999999,stroke:#000,color:#fff
```

### Container diagram

```mermaid
graph TB
    USER([Job Seeker])

    subgraph "ProFolio System"
        SPA[Single Page App<br/>React 18 + Vite + TailwindCSS<br/>Port 5173 dev / 80 prod]
        API[REST API<br/>FastAPI + SQLAlchemy async<br/>Port 8000]
        DB[(Database<br/>PostgreSQL 16<br/>Port 5432)]
        REDIS[(Cache<br/>Redis 7 — optional<br/>Port 6379)]
        FS[Local file storage<br/>uploads/ volume]
        SCH[APScheduler<br/>in-process<br/>daily job scan]
    end

    GEMINI[Google Gemini<br/>OpenAI-compatible endpoint]
    ADZUNA[Adzuna API]

    USER -->|HTTPS| SPA
    SPA -->|JSON / SSE| API
    API -->|asyncpg| DB
    API -.->|optional cache| REDIS
    API -->|read/write| FS
    SCH -->|trigger scan| API
    API -->|HTTPS| GEMINI
    API -->|HTTPS| ADZUNA

    style SPA fill:#61dafb,stroke:#000,color:#000
    style API fill:#009688,stroke:#000,color:#fff
    style DB fill:#336791,stroke:#000,color:#fff
    style REDIS fill:#dc382d,stroke:#000,color:#fff
```

---

## 3. UML Class Diagram — Modele DB

```mermaid
classDiagram
    class User {
        +UUID id
        +str email <unique>
        +str password_hash
        +str? full_name
        +str? seniority_level
        +str? niche
        +bool benchmark_opt_in
        +datetime created_at
        +datetime updated_at
        --
        relationships:
        job_preference: JobPreference?
        resumes: ParsedResume[]
        user_jobs: UserJob[]
        benchmark_scores: BenchmarkScore[]
    }

    class JobPreference {
        +UUID id
        +UUID user_id <FK>
        +str desired_title
        +str? location_type
        +list~str~? keywords
        +datetime created_at
    }

    class ParsedResume {
        +UUID id
        +UUID user_id <FK>
        +str? original_filename
        +str? file_url
        +JSONB parsed_data
        +bool is_active
        +datetime created_at
        +datetime updated_at
    }

    class ScrapedJob {
        +UUID id
        +str? external_url <unique>
        +str company_name
        +str job_title
        +str? description
        +str? description_hash <indexed>
        +str? location
        +str? source_platform
        +datetime scraped_at
    }

    class UserJob {
        +UUID id
        +UUID user_id <FK>
        +UUID job_id <FK>
        +int? match_score
        +str status «new|saved|applied|hidden»
        +JSONB? optimized_cv
        +str? cover_letter
        +JSONB? interview_prep
        +datetime? applied_at
        +datetime created_at
        +datetime updated_at
    }

    class BenchmarkScore {
        +UUID id
        +UUID user_id <FK>
        +UUID? job_id <FK>
        +int score
        +int? peer_group_size
        +str? seniority_level
        +str? niche
        +JSONB? missing_skills
        +JSONB? recommended_keywords
        +datetime calculated_at
    }

    class Feedback {
        +UUID id
        +UUID user_id <FK>
        +str content_type «optimized_cv|cover_letter|interview_prep»
        +str? content_id
        +int rating «1-5»
        +str? comment
        +datetime created_at
    }

    User "1" --> "0..1" JobPreference : has
    User "1" --> "*" ParsedResume : owns
    User "1" --> "*" UserJob : tracks
    User "1" --> "*" BenchmarkScore : has
    User "1" --> "*" Feedback : submits
    ScrapedJob "1" --> "*" UserJob : matched by
    ScrapedJob "1" --> "*" BenchmarkScore : referenced by
```

---

## 4. Entity-Relationship Diagram

```mermaid
erDiagram
    USER ||--o| JOB_PREFERENCE : "has 1"
    USER ||--o{ PARSED_RESUME : "uploads many"
    USER ||--o{ USER_JOB : "tracks many"
    USER ||--o{ BENCHMARK_SCORE : "has many"
    USER ||--o{ FEEDBACK : "submits many"
    SCRAPED_JOB ||--o{ USER_JOB : "matched by many"
    SCRAPED_JOB ||--o{ BENCHMARK_SCORE : "scored against"

    USER {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        string seniority_level
        string niche
        bool benchmark_opt_in
        timestamp created_at
    }

    JOB_PREFERENCE {
        uuid id PK
        uuid user_id FK
        string desired_title
        string location_type
        array keywords
    }

    PARSED_RESUME {
        uuid id PK
        uuid user_id FK
        string original_filename
        jsonb parsed_data
        bool is_active
        timestamp created_at
    }

    SCRAPED_JOB {
        uuid id PK
        string external_url UK
        string company_name
        string job_title
        text description
        string description_hash
        timestamp scraped_at
    }

    USER_JOB {
        uuid id PK
        uuid user_id FK
        uuid job_id FK
        int match_score
        string status
        jsonb optimized_cv
        text cover_letter
        jsonb interview_prep
        timestamp applied_at
    }

    BENCHMARK_SCORE {
        uuid id PK
        uuid user_id FK
        uuid job_id FK
        int score
        int peer_group_size
        jsonb missing_skills
    }

    FEEDBACK {
        uuid id PK
        uuid user_id FK
        string content_type
        int rating
        string comment
    }
```

---

## 5. Workflow — Upload + Parsare CV

```mermaid
flowchart TD
    START([User clicks Upload]) --> PICK[Selectează fișier PDF/DOCX]
    PICK --> POST[POST /api/resumes/upload<br/>multipart/form-data]
    POST --> AUTH{JWT valid?}
    AUTH -->|nu| R401[401 Unauthorized]
    AUTH -->|da| QUOTA{Quota OK?<br/>< MAX_RESUMES_PER_USER}
    QUOTA -->|nu| R413[413 Too Many Resumes]
    QUOTA -->|da| SAVE[Salvare pe disk<br/>uploads/uuid.ext]

    SAVE --> VALID{Validare:<br/>size, ext, MIME,<br/>magic bytes}
    VALID -->|fail| DEL1[Delete file]
    DEL1 --> R400[400 Bad Request]

    VALID -->|ok| EXTRACT[Extragere text<br/>pypdf / python-docx]
    EXTRACT --> CLEAN[Curățare text:<br/>normalize whitespace,<br/>strip page markers]
    CLEAN --> EMPTY{Text gol?}
    EMPTY -->|da| DEL2[Delete file]
    DEL2 --> R422[422 No text extracted]

    EMPTY -->|nu| TRUNC[Truncate la 8000 chars<br/>dacă necesar]
    TRUNC --> SANI[sanitize_user_text<br/>+ wrap_user_content]
    SANI --> LLM[Call Gemini<br/>temperature=0.1<br/>response_format=json_object]
    LLM -->|RateLimitError| FB[Fallback model chain<br/>2.5→2.0→1.5]
    FB --> LLM
    LLM -->|success| PARSE[Parse JSON +<br/>strip code fences]
    PARSE --> PYD{Pydantic validation<br/>ParsedCVData}
    PYD -->|fail| PARTIAL[Fallback parsing<br/>partial fields only]
    PYD -->|ok| STORE[INSERT INTO parsed_resumes<br/>is_active=true]
    PARTIAL --> STORE
    STORE --> DEACT[Deactivate other resumes<br/>UPDATE is_active=false]
    DEACT --> RESP[200 OK +<br/>ParsedResume JSON]
    RESP --> END([Frontend afișează<br/>CV parsed])

    style LLM fill:#4285f4,stroke:#000,color:#fff
    style STORE fill:#336791,stroke:#000,color:#fff
    style RESP fill:#4caf50,stroke:#000,color:#fff
    style R400 fill:#f44336,stroke:#000,color:#fff
    style R401 fill:#f44336,stroke:#000,color:#fff
    style R413 fill:#f44336,stroke:#000,color:#fff
    style R422 fill:#f44336,stroke:#000,color:#fff
```

---

## 6. Workflow — Scanare joburi

```mermaid
flowchart TD
    TRIG{Trigger}
    TRIG -->|"User: POST /jobs/scan"| MANUAL[Manual scan]
    TRIG -->|"APScheduler @ 03:00 UTC"| CRON[Daily global scan]

    MANUAL --> PREFS{User has<br/>JobPreference?}
    PREFS -->|nu| R400[400 Set preferences first]
    PREFS -->|da| QUERY[Build Adzuna query:<br/>desired_title +<br/>keywords + location_type]

    CRON --> ALL_USERS[Loop all users<br/>with preferences]
    ALL_USERS --> QUERY

    QUERY --> ADZUNA[GET adzuna.com<br/>api/v1/jobs/.../search]
    ADZUNA -->|429/5xx| RETRY[Retry with backoff]
    RETRY --> ADZUNA
    ADZUNA -->|200 OK| FETCH[Parse N jobs]
    FETCH --> LOOP{For each job}
    LOOP --> HASH[Compute description_hash<br/>SHA-256]
    HASH --> DEDUP{ScrapedJob exists<br/>by hash?}
    DEDUP -->|da| EXISTING[Reuse existing row]
    DEDUP -->|nu| INSERT[INSERT INTO scraped_jobs]
    EXISTING --> MATCH
    INSERT --> MATCH[Match against<br/>active resume]

    MATCH --> SCORE[Compute match_score<br/>0-100 based on<br/>skills overlap]
    SCORE --> EXISTUJ{UserJob exists?}
    EXISTUJ -->|da| SKIP[Skip — already tracked]
    EXISTUJ -->|nu| INSUJ[INSERT INTO user_jobs<br/>status=new]
    INSUJ --> LOOP
    SKIP --> LOOP
    LOOP -->|done| RESP[200 OK<br/>Found N jobs]
    RESP --> END([Frontend refresh])

    style ADZUNA fill:#ff6b35,stroke:#000,color:#fff
    style INSERT fill:#336791,stroke:#000,color:#fff
    style INSUJ fill:#336791,stroke:#000,color:#fff
    style RESP fill:#4caf50,stroke:#000,color:#fff
```

---

## 7. Workflow — Optimizare CV + Cover Letter

```mermaid
flowchart TD
    START([User pe JobDetail.jsx])
    START --> CHOICE{Acțiune}

    CHOICE -->|Optimize CV| OPT[POST /cv-optimizer/optimize/:job_id]
    CHOICE -->|Generate Cover Letter| CL[POST /cv-optimizer/cover-letter/:job_id<br/>+ optional motivation]

    OPT --> LOAD1[Load active ParsedResume<br/>+ ScrapedJob]
    CL --> LOAD2[Load active ParsedResume<br/>+ ScrapedJob]

    LOAD1 --> CHECK1{Resume + job exist?}
    LOAD2 --> CHECK2{Resume + job exist?}
    CHECK1 -->|nu| E404[404 Not Found]
    CHECK2 -->|nu| E404

    CHECK1 -->|da| BUILD_OPT[Build optimization prompt:<br/>- NO_FABRICATION rules<br/>- JD truncated to 500 tokens<br/>- CV serialized + wrapped]
    CHECK2 -->|da| BUILD_CL[Build cover letter prompt:<br/>- top 3 experiences<br/>- top 8 skills<br/>- JD truncated to 375 tokens<br/>- user_motivation if present]

    BUILD_OPT --> CACHE1{Prompt cache hit?}
    BUILD_CL --> CACHE2{Prompt cache hit?}
    CACHE1 -->|da| HIT_OPT[Return cached JSON]
    CACHE2 -->|da| HIT_CL[Return cached text]

    CACHE1 -->|nu| LLM_OPT[Gemini call<br/>temp=0.3<br/>json_object]
    CACHE2 -->|nu| LLM_CL[Gemini call<br/>temp=0.4<br/>plain text]

    LLM_OPT --> PYD[Pydantic validate<br/>OptimizedCV]
    LLM_CL --> LEN{len > 200?}

    PYD -->|fail| ERR_OPT[CVOptimizerError]
    PYD -->|ok| FAB[Fabrication scan:<br/>tokenize → filter stopwords →<br/>compare with original skills]
    FAB --> STORE_OPT[UPDATE user_jobs<br/>SET optimized_cv = JSON,<br/>potential_fabrications = list]

    LEN -->|nu| ERR_CL[Cover letter too short]
    LEN -->|da| STORE_CL[UPDATE user_jobs<br/>SET cover_letter = text]

    STORE_OPT --> CACHE_PUT1[Put in prompt cache]
    STORE_CL --> CACHE_PUT2[Put in prompt cache]
    HIT_OPT --> RESP_OPT[200 OK + OptimizedCV]
    HIT_CL --> RESP_CL[200 OK + cover_letter]
    CACHE_PUT1 --> RESP_OPT
    CACHE_PUT2 --> RESP_CL

    RESP_OPT --> EXPORT[Optional: GET /export-pdf]
    RESP_CL --> EXPORT
    EXPORT --> PDF[reportlab generate PDF<br/>+ Content-Disposition]
    PDF --> DOWNLOAD([User downloads PDF])

    style LLM_OPT fill:#4285f4,stroke:#000,color:#fff
    style LLM_CL fill:#4285f4,stroke:#000,color:#fff
    style FAB fill:#ff9800,stroke:#000,color:#000
    style PDF fill:#9c27b0,stroke:#000,color:#fff
```

---

## 8. Workflow — Authentication (JWT)

```mermaid
flowchart LR
    subgraph "Register"
        R1[POST /api/auth/register<br/>email + password + name] --> R2{Email unique?}
        R2 -->|nu| R3[409 Email exists]
        R2 -->|da| R4[Hash password<br/>bcrypt cost=12]
        R4 --> R5[INSERT INTO users]
        R5 --> R6[201 Created + UserOut]
    end

    subgraph "Login"
        L1[POST /api/auth/login<br/>email + password] --> L2{Rate limit OK?<br/>5/min}
        L2 -->|nu| L3[429 Too Many]
        L2 -->|da| L4[SELECT user by email]
        L4 --> L5{User exists?}
        L5 -->|nu| L6[401 Invalid creds]
        L5 -->|da| L7{bcrypt.verify<br/>password}
        L7 -->|nu| L6
        L7 -->|da| L8[Sign JWT<br/>HS256<br/>exp 24h]
        L8 --> L9[200 OK +<br/>access_token]
    end

    subgraph "Protected request"
        P1[GET /api/me<br/>Bearer token] --> P2{Header present?}
        P2 -->|nu| P3[401]
        P2 -->|da| P4{JWT signature valid?}
        P4 -->|nu| P3
        P4 -->|da| P5{exp > now?}
        P5 -->|nu| P3
        P5 -->|da| P6[SELECT user by sub]
        P6 --> P7{User exists +<br/>not deleted?}
        P7 -->|nu| P3
        P7 -->|da| P8[Inject user în endpoint]
        P8 --> P9[200 OK + data]
    end

    R6 -.->|client stores token<br/>localStorage| L1
    L9 -.->|Authorization header| P1
```

---

## 9. Sequence Diagram — Generare materiale aplicare complete

```mermaid
sequenceDiagram
    actor U as User
    participant FE as React SPA
    participant API as FastAPI
    participant SVC as CVOptimizerService
    participant AG as CVOptimizerAgent
    participant CACHE as Prompt Cache
    participant GEM as Gemini API
    participant DB as PostgreSQL

    U->>FE: Click "Optimize CV"
    FE->>API: POST /cv-optimizer/optimize/{job_id}<br/>Authorization: Bearer JWT
    API->>API: Verify JWT + load user
    API->>SVC: optimize_cv_for_job(user, job, db)

    SVC->>DB: SELECT active ParsedResume
    DB-->>SVC: parsed_data JSON
    SVC->>DB: SELECT UserJob
    DB-->>SVC: user_job row

    SVC->>AG: optimize_cv_for_job(parsed_cv, JD, title, company)
    AG->>AG: sanitize + wrap + truncate JD
    AG->>AG: build system + user prompts
    AG->>CACHE: get(hash(prompts, model))

    alt Cache hit
        CACHE-->>AG: cached JSON
    else Cache miss
        AG->>GEM: chat.completions.create<br/>model=gemini-2.5-flash<br/>temp=0.3
        alt Rate limited
            GEM-->>AG: 429
            AG->>GEM: retry on gemini-2.0-flash
            GEM-->>AG: 200 JSON
        else Success
            GEM-->>AG: 200 JSON
        end
        AG->>AG: Pydantic validate OptimizedCV
        AG->>AG: detect_potential_fabrications()
        AG->>CACHE: put(hash, JSON)
    end

    AG-->>SVC: optimized_cv dict
    SVC->>DB: UPDATE user_jobs SET optimized_cv=...
    DB-->>SVC: row updated
    SVC-->>API: optimized_cv

    API-->>FE: 200 OK + JSON
    FE->>FE: Render diff + changes_summary
    FE->>U: Show "Review optimization"

    Note over U,FE: User clicks "Download PDF"
    U->>FE: Click Export PDF
    FE->>API: GET /cv-optimizer/cv-pdf/{job_id}
    API->>SVC: export_optimized_cv_pdf(...)
    SVC->>DB: SELECT optimized_cv
    DB-->>SVC: JSON
    SVC->>SVC: pdf_exporter.export_cv_to_pdf()
    SVC-->>API: (pdf_bytes, filename)
    API-->>FE: 200 + application/pdf
    FE->>U: Browser triggers download
```

---

## 10. State Diagram — UserJob status

```mermaid
stateDiagram-v2
    [*] --> new : INSERT on scan

    new --> saved : User clicks "Save"
    new --> hidden : User clicks "Hide"
    new --> applied : User clicks "Mark Applied"

    saved --> applied : User clicks "Mark Applied"
    saved --> hidden : User clicks "Hide"
    saved --> new : User clicks "Unsave"

    hidden --> new : User clicks "Unhide"
    hidden --> saved : User restores

    applied --> [*] : (terminal — sets applied_at)

    note right of applied
        applied_at timestamp set
        atomic via advisory lock
        prevents duplicate apply race
    end note

    note left of new
        match_score computed
        once on insert
    end note
```

---

## 11. Deployment Diagram

```mermaid
graph TB
    subgraph "Developer Machine"
        IDE[VS Code + Cursor]
        DOCKER[Docker Desktop]
    end

    subgraph "Docker Compose Network — local"
        FE_C["frontend container<br/>node:22-alpine<br/>vite dev :5173"]
        BE_C["backend container<br/>python:3.11-slim<br/>uvicorn :8000"]
        DB_C[("postgres:16-alpine<br/>:5432<br/>vol: pgdata")]
        REDIS_C[("redis:7-alpine<br/>:6379<br/>optional")]
        UP_VOL[(uploads/ volume)]
    end

    subgraph "GitHub Actions CI"
        LINT["Lint job<br/>Flake8 + Black + ESLint + Prettier"]
        BE_TEST["Backend tests<br/>pytest --cov<br/>postgres service"]
        FE_TEST["Frontend tests<br/>vitest run"]
        SEC["Security scan<br/>Trivy + pip-audit + npm audit"]
        INT["Integration tests<br/>full stack via httpx"]
        BUILD["Docker build<br/>+ smoke test"]
    end

    subgraph "Production (planned)"
        LB["Load balancer<br/>Caddy / Nginx<br/>TLS termination"]
        FE_PROD["Static SPA<br/>nginx :80<br/>built via npm run build"]
        BE_PROD["FastAPI<br/>uvicorn workers"]
        DB_PROD[("Managed PostgreSQL")]
        REDIS_PROD[("Managed Redis")]
    end

    EXT_GEMINI[Google Gemini API]
    EXT_ADZUNA[Adzuna API]

    IDE --> DOCKER
    DOCKER --> FE_C
    DOCKER --> BE_C
    DOCKER --> DB_C
    DOCKER --> REDIS_C
    BE_C --> DB_C
    BE_C --> REDIS_C
    BE_C --> UP_VOL
    BE_C --> EXT_GEMINI
    BE_C --> EXT_ADZUNA
    FE_C -->|proxy| BE_C

    LINT --> BE_TEST
    LINT --> FE_TEST
    BE_TEST --> INT
    FE_TEST --> INT
    INT --> BUILD
    SEC --> BUILD

    BUILD -.->|on main| LB
    LB --> FE_PROD
    LB --> BE_PROD
    BE_PROD --> DB_PROD
    BE_PROD --> REDIS_PROD
    BE_PROD --> EXT_GEMINI
    BE_PROD --> EXT_ADZUNA

    style EXT_GEMINI fill:#4285f4,stroke:#000,color:#fff
    style EXT_ADZUNA fill:#ff6b35,stroke:#000,color:#fff
    style DB_C fill:#336791,stroke:#000,color:#fff
    style DB_PROD fill:#336791,stroke:#000,color:#fff
```

---

## 12. UML — Class Diagram pentru AI Agents

```mermaid
classDiagram
    class CVProfilerAgent {
        -openai_client: AsyncOpenAI
        -models: tuple~str~
        -max_tokens: int = 2000
        -temperature: float = 0.1
        +parse(file_path, filename) Dict
        -_parse_with_gpt4(text, filename) ParsedCVData
        -_get_cv_parsing_prompt() str
        +get_parsing_stats() Dict
    }

    class CVOptimizerAgent {
        -client: AsyncOpenAI
        -models: tuple~str~
        -max_tokens: int = 3000
        -temperature: float = 0.3
        +optimize_cv_for_job(cv, jd, title, company) Dict
        +generate_cover_letter(cv, jd, title, company, name, motivation) str
        +get_optimization_suggestions(cv, jd) Dict
        -_build_cv_optimization_system_prompt() str
        -_build_cover_letter_system_prompt() str
        -_detect_potential_fabrications(skills, text) List
        -_looks_like_tech(token) bool
        -_make_api_call(...) Any
    }

    class InterviewCoachAgent {
        -client: AsyncOpenAI
        -models: tuple~str~
        +generate_questions(cv, jd) Dict
        +generate_cheat_sheet(jd) Dict
        +generate_full_prep(cv, jd) Dict
    }

    class JobScannerAgent {
        -adzuna_client: AdzunaClient
        +scan(user, db) ScanResult
        -_match_jobs_to_user(...)
        -_find_existing_scraped_job(...)
        -_compute_match_score(cv, job) int
    }

    class AdzunaClient {
        -app_id: str
        -app_key: str
        +search(query, location, page) List~Job~
    }

    class ParsedCVData {
        +str full_name
        +str email
        +str phone
        +str location
        +str summary
        +List~str~ skills
        +List~str~ technologies
        +List~Experience~ experience
        +List~Education~ education
        +List~str~ certifications
        +List~str~ languages
        +int total_years_experience
        +List~str~ senior_technologies
    }

    class OptimizedCV {
        +str summary
        +List~ExpEntry~ experience
        +List~str~ skills
        +List~EduEntry~ education
        +List~str~ optimized_keywords
        +List~str~ changes_summary
        +List~str~ potential_fabrications
    }

    CVProfilerAgent ..> ParsedCVData : produces
    CVOptimizerAgent ..> OptimizedCV : produces
    CVOptimizerAgent ..> ParsedCVData : consumes
    InterviewCoachAgent ..> ParsedCVData : consumes
    JobScannerAgent ..> AdzunaClient : uses
    JobScannerAgent ..> ParsedCVData : consumes for matching

    class _PromptSafety {
        <<utility>>
        +sanitize_user_text(text) str
        +wrap_user_content(label, content) str
    }

    class _TokenGuard {
        <<utility>>
        +estimate_tokens(text) int
        +truncate_for_budget(text, budget) TruncationResult
    }

    class _LLMRetry {
        <<utility>>
        +with_retry(coro_factory) Any
        +with_model_fallback(coro_factory, models) tuple
    }

    CVProfilerAgent ..> _PromptSafety
    CVOptimizerAgent ..> _PromptSafety
    CVOptimizerAgent ..> _TokenGuard
    CVProfilerAgent ..> _LLMRetry
    CVOptimizerAgent ..> _LLMRetry
```

---

## 13. Use-case diagram

```mermaid
graph TB
    USER([Job Seeker])
    ADMIN([Admin])

    subgraph "ProFolio Use Cases"
        UC1[Register / Login]
        UC2[Upload & parse CV]
        UC3[Set job preferences]
        UC4[Scan for jobs]
        UC5[View job matches]
        UC6[Optimize CV for job]
        UC7[Generate cover letter]
        UC8[Generate interview prep]
        UC9[View competitive benchmark]
        UC10[Mark job as applied]
        UC11[Export PDF]
        UC12[Submit feedback]
        UC13[Delete account / GDPR]
        UC14[View aggregated feedback]
        UC15[Trigger daily scan manually]
    end

    USER --> UC1
    USER --> UC2
    USER --> UC3
    USER --> UC4
    USER --> UC5
    USER --> UC6
    USER --> UC7
    USER --> UC8
    USER --> UC9
    USER --> UC10
    USER --> UC11
    USER --> UC12
    USER --> UC13

    ADMIN --> UC14
    ADMIN --> UC15

    UC6 -.includes.-> UC11
    UC7 -.includes.-> UC11
    UC6 -.requires.-> UC2
    UC7 -.requires.-> UC2
    UC4 -.requires.-> UC3
    UC9 -.requires.-> UC13
```

---

## 14. Cum vizualizezi diagramele

### În VS Code / Cursor
1. Instalează extensia **"Markdown Preview Mermaid Support"** (id: `bierner.markdown-mermaid`)
2. Deschide acest fișier și apasă `Cmd+Shift+V` (preview)

### Pe GitHub
Diagramele Mermaid se randează **automat** când vizualizezi fișierul `.md` pe github.com.

### Export ca PNG/SVG
```bash
npx -p @mermaid-js/mermaid-cli mmdc -i docs/architecture-diagrams.md -o diagram.png
```

### Live editor (debug)
[https://mermaid.live](https://mermaid.live) — paste any block între ` ```mermaid ` și verifică.
