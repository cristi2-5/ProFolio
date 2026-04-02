"""
Pytest Configuration and Shared Fixtures.

Provides a test client fixture using httpx.AsyncClient
for testing FastAPI endpoints without a running server.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Provide an async HTTP test client.

    Uses httpx ASGITransport to call FastAPI directly
    without needing a live server instance.

    Yields:
        AsyncClient: Configured test client scoped to the test function.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
