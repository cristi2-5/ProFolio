"""
Health Endpoint Tests — Verifies /health returns correct status.

Tests:
    - Happy path: Returns 200 with correct structure.
    - Validates response contains expected fields.
"""

import pytest

from app.config import get_settings


@pytest.mark.asyncio
async def test_health_check_returns_200(client):
    """Test that /health endpoint returns 200 OK.

    Verifies:
        - Status code is 200.
        - Response body contains 'status': 'ok'.
        - Response body contains 'app' and 'environment' fields.
    """
    response = await client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_check_app_name(client):
    """Test that /health returns the correct app name."""
    response = await client.get("/health")
    data = response.json()
    assert data["app"] == get_settings().app_name


@pytest.mark.asyncio
async def test_health_check_environment(client):
    """Test that /health returns the environment setting."""
    response = await client.get("/health")
    data = response.json()
    assert data["environment"] == get_settings().environment
