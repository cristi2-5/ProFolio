"""
Auto-Apply Backend — FastAPI Application Entry Point.

Configures the FastAPI app with CORS, lifespan hooks, health check,
and all API routers. This is the single entry point for uvicorn.

Usage:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, async_session_factory, engine
from app.models.benchmark import BenchmarkScore
from app.models.feedback import Feedback
from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume

# Import all models to ensure they're registered with Base.metadata
from app.models.user import JobPreference, User
from app.routers import auth, benchmarks, cv_optimizer, feedback, jobs, resumes, tasks
from app.utils.rate_limit import limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Module-level scheduler — referenced by both lifespan and /ready endpoint.
scheduler = AsyncIOScheduler()


def _run_migrations(legacy_create_all_db: bool) -> None:
    """Apply alembic migrations to head. Sync function — invoke via asyncio.to_thread.

    If ``legacy_create_all_db`` is True, the caller has detected the DB was
    previously created via ``Base.metadata.create_all`` (tables exist but
    ``alembic_version`` is missing). We stamp head instead of upgrading so
    we don't replay migrations and hit "relation already exists".
    """
    from alembic import command
    from alembic.config import Config

    cfg_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(cfg_path))

    if legacy_create_all_db:
        command.stamp(cfg, "head")
        return

    command.upgrade(cfg, "head")


async def _detect_legacy_create_all_db() -> bool:
    """Return True if the DB has app tables but no ``alembic_version`` table."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        users_exists = await conn.scalar(
            text("SELECT to_regclass('public.users') IS NOT NULL")
        )
        alembic_exists = await conn.scalar(
            text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        )
    return bool(users_exists) and not bool(alembic_exists)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — startup/shutdown hooks.

    Startup:
        - Initialize database tables automatically.
        - Start APScheduler for daily job scan cron.
        - Log configuration (environment, DB connection status).

    Shutdown:
        - Shut down APScheduler gracefully.
        - Clean up resources (DB connections, HTTP clients).

    Args:
        app: The FastAPI application instance.
    """
    # --- Startup ---
    logger.info("🚀 Starting %s in %s mode", settings.app_name, settings.environment)
    logger.info("📦 Database: %s", settings.database_url.split("@")[-1])

    # Create database tables / apply migrations
    try:
        if settings.environment == "test":
            # Tests use SQLite + per-test session; alembic migrations not applied there.
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Test mode — schema created via metadata.create_all")
        else:
            legacy = await _detect_legacy_create_all_db()
            if legacy:
                logger.info(
                    "🔧 Detected legacy create_all DB (no alembic_version) — "
                    "stamping head instead of replaying migrations"
                )
            else:
                logger.info("🔧 Running alembic migrations to head...")
            await asyncio.to_thread(_run_migrations, legacy)
            logger.info("✅ Migrations applied")
    except Exception as e:
        logger.error("❌ Database initialization failed: %s", e)
        raise

    # --- APScheduler: daily job scan cron ---

    # Shared advisory-lock key used by both the cron job and the manual
    # POST /jobs/scan endpoint to prevent overlapping scans.
    from sqlalchemy import text as _text

    from app.routers.jobs import SCAN_ADVISORY_LOCK

    async def _daily_scan_job():
        """Cron callback: scan all users and discover new jobs.

        Wraps the scan in a Postgres advisory lock so a manual scan
        can't overlap with the cron, and so a long-running cron won't
        be re-entered if APScheduler fires it twice. The cron uses the
        blocking ``pg_advisory_lock`` (it's not user-facing — happy to
        wait its turn).
        """
        from app.agents.job_scanner import JobScannerAgent

        logger.info("⏰ APScheduler: starting daily job scan")
        try:
            async with async_session_factory() as db:
                dialect = getattr(db.bind, "dialect", None)
                use_lock = dialect is not None and dialect.name == "postgresql"
                if use_lock:
                    await db.execute(
                        _text("SELECT pg_advisory_lock(:k)").bindparams(
                            k=SCAN_ADVISORY_LOCK
                        )
                    )
                try:
                    agent = JobScannerAgent()
                    total = await agent.scan_all_users(db)
                    await db.commit()
                finally:
                    if use_lock:
                        await db.execute(
                            _text("SELECT pg_advisory_unlock(:k)").bindparams(
                                k=SCAN_ADVISORY_LOCK
                            )
                        )
            logger.info("✅ APScheduler: daily scan complete — %d new jobs", total)
        except Exception as exc:
            logger.error("❌ APScheduler: daily scan failed: %s", exc, exc_info=True)

    scheduler.add_job(
        _daily_scan_job,
        trigger="interval",
        hours=settings.job_scan_interval_hours,
        id="daily_job_scan",
        replace_existing=True,
        misfire_grace_time=3600,  # Allow up to 1h late if server was down
        max_instances=1,  # Never run two cron scans in parallel
        coalesce=True,  # If multiple fire times accumulate, run once
    )
    scheduler.start()
    logger.info(
        "📅 Job scan scheduler started — interval: %dh",
        settings.job_scan_interval_hours,
    )

    yield

    # --- Shutdown ---
    logger.info("🛑 Shutting down %s", settings.app_name)
    try:
        await asyncio.wait_for(
            asyncio.to_thread(scheduler.shutdown, wait=True),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        logger.warning("Scheduler shutdown exceeded 15s; forcing")
        scheduler.shutdown(wait=False)
    logger.info("✅ APScheduler stopped")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered job hunting platform with four autonomous agents: "
        "CV Profiler, Job Scanner, CV Optimizer, and Interview Coach."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    # Disable automatic 307 redirect on missing trailing slash. Behind a
    # docker-compose proxy the redirect's Location header points at the
    # Docker-internal host (e.g. http://backend:8000/...), which the
    # browser can't resolve — the browser sees "Failed to fetch". With
    # this off, both `/foo` and `/foo/` reach the route directly.
    redirect_slashes=False,
)

# Rate limiting — register slowapi limiter, middleware, and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS middleware — allows frontend (Vite dev server) to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(cv_optimizer.router)
app.include_router(benchmarks.router)
app.include_router(feedback.router)
app.include_router(tasks.router)


@app.get(
    "/health",
    tags=["System"],
    summary="Health check endpoint",
)
async def health_check():
    """Return application health status with database connectivity check.

    Pings the database with a single ``SELECT 1`` round-trip — fast (~ms)
    so liveness/readiness probes can call this every few seconds without
    measurable load. If the DB is unreachable we fail closed with a 503
    so upstream load balancers can pull the pod out of rotation.

    Returns:
        dict: ``{"status": "ok", "database": "ok", ...}`` on success.
        JSONResponse: 503 with ``{"status": "degraded", "database": "unreachable"}``
            if the DB ping fails.
    """
    db_ok = True
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Health check DB ping failed: %s", exc)
        db_ok = False

    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "unreachable",
                "app": settings.app_name,
                "environment": settings.environment,
            },
        )
    return {
        "status": "ok",
        "database": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


@app.get("/ready", tags=["System"], summary="Readiness probe")
async def ready_check():
    """Return 200 only when both DB and scheduler are ready."""
    db_ok = True
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    scheduler_ok = bool(scheduler and scheduler.running)
    if not (db_ok and scheduler_ok):
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "db": db_ok, "scheduler": scheduler_ok},
        )
    return {"status": "ready", "db": True, "scheduler": True}
