"""Auto-Apply ORM Models Package.

Exports all SQLAlchemy models for Alembic auto-discovery and
convenient imports throughout the application.
"""

from app.models.benchmark import BenchmarkScore  # noqa: F401
from app.models.job import ScrapedJob, UserJob  # noqa: F401
from app.models.resume import ParsedResume  # noqa: F401
from app.models.user import JobPreference, User  # noqa: F401
