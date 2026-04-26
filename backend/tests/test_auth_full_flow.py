"""End-to-end auth lifecycle: register -> login -> me -> delete -> login fails."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_full_auth_lifecycle(client):
    # Use a unique email per run to avoid collisions with other tests in the suite
    unique = uuid.uuid4().hex[:10]
    email = f"flow-{unique}@example.com"
    password = "FlowPassCode123!"

    # Step 1: Register
    register_payload = {
        "email": email,
        "password": password,
        "full_name": "Flow Tester",
    }
    register_response = await client.post("/api/auth/register", json=register_payload)
    assert register_response.status_code == 201, register_response.text

    # Step 2: Login
    login_response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    assert token

    headers = {"Authorization": f"Bearer {token}"}

    # Step 3: GET /me
    me_response = await client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["email"] == email

    # Step 4: DELETE /me
    delete_response = await client.request(
        "DELETE",
        "/api/auth/me",
        headers=headers,
        json={"password": password},
    )
    assert delete_response.status_code == 204, delete_response.text

    # Step 5: Login again — should fail with 401
    relogin_response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert relogin_response.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_wrong_password(client):
    """DELETE /me with wrong password returns 401 and account survives."""
    unique = uuid.uuid4().hex[:10]
    email = f"keep-{unique}@example.com"
    password = "KeepPassCode123!"

    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": "Keeper"},
    )
    assert reg.status_code == 201

    login = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    bad_delete = await client.request(
        "DELETE",
        "/api/auth/me",
        headers=headers,
        json={"password": "TotallyWrongPass123!"},
    )
    assert bad_delete.status_code == 401

    # Account should still exist — re-login still works
    relogin = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert relogin.status_code == 200
