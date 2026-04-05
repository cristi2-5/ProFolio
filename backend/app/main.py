"""
Auto-Apply Backend — FastAPI Application Entry Point.

Configures the FastAPI app with CORS, lifespan hooks, health check,
and all API routers. This is the single entry point for uvicorn.

Usage:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.routers import auth, benchmarks, cv_optimizer, jobs, resumes

# Import all models to ensure they're registered with Base.metadata
from app.models.user import User, JobPreference
from app.models.resume import ParsedResume
from app.models.job import ScrapedJob, UserJob
from app.models.benchmark import BenchmarkScore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager — startup/shutdown hooks.

    Startup:
        - Initialize database tables automatically.
        - Log configuration (environment, DB connection status).
        - Validate critical settings.

    Shutdown:
        - Clean up resources (DB connections, HTTP clients).

    Args:
        app: The FastAPI application instance.
    """
    # --- Startup ---
    logger.info("🚀 Starting %s in %s mode", settings.app_name, settings.environment)
    logger.info("📦 Database: %s", settings.database_url.split("@")[-1])

    # Create database tables automatically
    try:
        logger.info("🔧 Initializing database tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables ready!")
    except Exception as e:
        logger.error("❌ Database initialization failed: %s", e)
        raise

    yield
    # --- Shutdown ---
    logger.info("🛑 Shutting down %s", settings.app_name)


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
)

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


@app.get(
    "/health",
    tags=["System"],
    summary="Health check endpoint",
)
async def health_check() -> dict:
    """Return application health status.

    Returns:
        dict: Health status with app name and environment.
    """
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }
