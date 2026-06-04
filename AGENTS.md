# Repository Guidelines

## Project Structure & Module Organization

This repository contains a FastAPI backend and a Vite/React frontend.

- `backend/` holds Python code: `routers/` for API routes, `services/` for business logic, `db/` for migrations and connection handling, `llm/` for extraction clients and schemas, `utils/` for shared helpers, and `scripts/` for operational commands.
- `backend/tests/` mirrors backend domains with pytest suites.
- `frontend/src/` contains React code: `views/` for routed screens, `components/` for reusable UI, `test/` for setup, and CSS modules beside views.
- `docs/`, `_bmad/`, `_bmad-output/`, and `prompts/` store planning artifacts, generated documentation, and prompt assets.
- `docker-compose.yml` provisions local infrastructure, primarily PostgreSQL.

## Build, Test, and Development Commands

- `make setup` creates the backend virtualenv and installs dependencies.
- `make dev` or `npm run dev` runs Vite on port `5173` and FastAPI on `127.0.0.1:8000`.
- `make db-up` / `make db-down` start and stop Docker services.
- `npm run test` runs frontend Vitest, then backend pytest.
- `npm run test:frontend` runs only frontend tests.
- `npm run test:backend` runs `pytest` from `backend/`.
- `npm run lint` runs frontend ESLint.
- `cd frontend && npm run build` type-checks and builds the frontend.

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation, typed Pydantic models where appropriate, and snake_case module/function names. Keep routes under `backend/routers/` and domain behavior in `backend/services/`.

Frontend code uses TypeScript, React function components, 2-space indentation, PascalCase component/view files such as `ProfileView.tsx`, and CSS modules such as `ProfileView.module.css`. ESLint config lives in `frontend/.eslintrc.cjs`.

## Testing Guidelines

Backend tests use `pytest` and `pytest-asyncio`; put new tests under `backend/tests/` using `test_*.py` names. Frontend tests use Vitest with Testing Library; name files `*.test.tsx` near the view or component they cover. Add tests for route behavior, service logic, migrations, and user-visible UI states.

## Commit & Pull Request Guidelines

Recent commits use short imperative summaries, sometimes with a conventional prefix, for example `Add scheduled ingestion and diagnostics` or `feat: implement story 2-3 ingestion cockpit`. Keep commits focused on one behavior change.

Pull requests should include a clear summary, test results, linked issue or story when applicable, and screenshots for UI changes. Note new environment variables, migrations in `backend/db/migrations/`, or operational impacts.

## Security & Configuration Tips

Copy `.env.example` for local configuration and keep secrets out of git. Treat API keys, database URLs, email credentials, and provider tokens as local-only values. Use disabled-by-default provider flags when adding discovery integrations.
