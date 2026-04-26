# Local Development Runbook

A practical guide for working on ProFolio locally with Docker Compose.

## Daily workflow

- Bring up: `docker compose up --build`
- Tail logs: `docker compose logs -f backend` or `docker compose logs -f frontend`
- Stop: `Ctrl+C` then `docker compose down`

## Reset the database

- Wipe everything: `docker compose down -v`
- Bring back up: `docker compose up --build` (alembic migrations run automatically on boot)

## Seed peer data for benchmarking

The benchmarking feature compares your CV against ≥30 opted-in peers in your seniority/niche bucket. To unlock this in dev, seed 90 synthetic peers (30 junior + 30 mid + 30 senior, randomized across 5 niches):

```bash
docker compose exec backend python -m app.scripts.seed_peers
```

The script is idempotent — re-running won't duplicate. Peer emails are `peer000@profolio.seed` to `peer089@profolio.seed` (password: `PeerPass1!`). Filter them out of any production query with: `email NOT LIKE '%@profolio.seed'`.

## Running tests

- Backend (full suite): `docker compose exec backend pytest backend/tests/`
- Backend (verbose, single file): `docker compose exec backend pytest -v backend/tests/test_auth_endpoints.py`
- Frontend (Vitest): `docker compose exec frontend npm test`

## Inspecting the database

```bash
docker compose exec db psql -U autoapply -d autoapply_db
```

Then `\dt` to list tables, `SELECT * FROM users;` etc.

## Re-running alembic migrations manually

- Upgrade to head: `docker compose exec backend alembic upgrade head`
- Downgrade one step: `docker compose exec backend alembic downgrade -1`

Migrations are also run automatically on backend startup (Phase 9 change — was `Base.metadata.create_all`).

## Debugging a failing AI agent

- LLM calls go through `with_retry` in `backend/app/utils/llm_retry.py`.
- Errors classify to specific HTTP statuses (429 / 503 / 422 / 500) — check backend logs for the `AgentError` subclass that bubbled up.
- Increase logging: set `LOG_LEVEL=DEBUG` in `.env` and restart backend.
- For prompt-injection / sanitization issues, look at `backend/app/agents/_prompt_safety.py` and the BEGIN/END markers in agent prompts.

## Pointing at a different Gemini model

- Edit `.env`: change the model name in your config (the OpenAI-compat endpoint is configured per agent).
- Restart backend: `docker compose restart backend`.
- The OpenAI-compat endpoint and model name are configured in `backend/app/agents/cv_profiler.py` (and the other agents).

## Resetting a forgotten password (no email yet)

Until SMTP is wired, recover an account locally by hashing a new password and patching the row directly.

```bash
# 1. Generate a bcrypt hash for the new password.
docker compose exec backend python -c "from app.utils.security import hash_password; print(hash_password('newpassword123'))"

# 2. Open psql and patch the user row.
docker compose exec db psql -U autoapply -d autoapply_db
```

```sql
UPDATE users SET password_hash = '<the-bcrypt-hash>' WHERE email = 'you@example.com';
```

## Common errors

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `pg_isready: command not found` in healthcheck | Postgres image stale | `docker compose pull && docker compose up --build` |
| Backend can't reach DB | DB not yet healthy | Wait for `db` healthcheck to pass; check `docker compose logs db` |
| Frontend shows 401 immediately | JWT expired | Re-login. Tokens expire after 60min by default (`ACCESS_TOKEN_EXPIRE_MINUTES`) |
| LLM endpoints return 500 | OPENAI_API_KEY missing or invalid | Check `.env`; verify https://aistudio.google.com/app/apikey |
| Adzuna scan returns nothing | App ID/Key wrong, or Adzuna quota exhausted | Verify keys at https://developer.adzuna.com/ — free tier is 250 requests/month |
| Frontend hot reload not working | Volume mount stale | `docker compose down && docker compose up --build` |
