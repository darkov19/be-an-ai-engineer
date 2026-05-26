# Deferred Work

## Deferred from: code review of 1-1-local-monorepo-and-database-scaffold (2026-05-26)

- ~~`docker-compose.yml` uses deprecated `version: '3.8'` top-level key — Docker Compose v2+ emits a warning.~~ **RESOLVED 2026-05-26** — key removed.
- ~~Test app-state isolation: `backend/tests/conftest.py` shares a singleton `app` object across tests with no teardown to reset `app.state.pool`.~~ **RESOLVED 2026-05-26** — yield + teardown added to `app` fixture.
