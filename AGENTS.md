# Repository Guidelines

## Project Structure & Module Organization
This repository is a small Python web app for daily recap recording.

- `src/server.py`: main HTTP server, request handling, validation, markdown generation, and file persistence.
- `fixtures/page.html` and `fixtures/forbidden.html`: HTML templates rendered by the server.
- `warehouse/` (runtime-generated): saved daily records as `warehouse/YYYY/MM/YYYY-MM-DD.md`.
- `README.md`: quick-start usage.
- `pyproject.toml` and `uv.lock`: project metadata and dependency lockfile (managed with `uv`).

Keep core business logic in `src/server.py` (or split into `src/` modules as complexity grows). Keep templates in `fixtures/`.

## Build, Test, and Development Commands
- `uv venv`: create a local virtual environment.
- `uv sync`: install dependencies from lockfile.
- `uv run python src/server.py --host 127.0.0.1 --port 8000`: start the app locally.
- `uv run python -m py_compile src/server.py`: fast syntax sanity check.

Use the URL printed at startup (includes `token`) for browser access.

## Coding Style & Naming Conventions
- Target Python `>=3.10` (see `pyproject.toml`).
- Follow PEP 8 with 4-space indentation and type hints for new/changed functions.
- Use `snake_case` for functions/variables, `PascalCase` for dataclasses/classes, and `UPPER_SNAKE_CASE` for constants.
- Prefer small helper functions for parsing/validation (matching current patterns like `_normalize_*`).
- Keep template placeholders explicit (for example `__TODAY__`, `__PLAN_ROWS__`).

## Testing Guidelines
There is no formal test suite yet. For now:
- run `uv run python -m py_compile src/server.py`;
- start the server and verify `GET /`, `GET /api/dates`, `GET /api/entry`, and `POST /submit`.

When adding tests, use `pytest` with files under `tests/` named `test_*.py`, grouped by behavior (for example `tests/test_entry_parsing.py`).

## Commit & Pull Request Guidelines
Git history is short; prefer Conventional Commit style used in repo (example: `chore(repo): switch to uv setup`).

- Commit format: `type(scope): concise summary` (`feat`, `fix`, `chore`, `docs`, `refactor`).
- PRs should include: purpose, key changes, manual verification steps, and screenshots for UI/template changes.
- Link related issues/tasks and call out any storage format changes under `warehouse/`.
