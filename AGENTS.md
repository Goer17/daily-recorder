# Repository Guidelines

## Project Structure & Module Organization
- `src/server.py`: single Python entrypoint that serves the daily form UI and handles `/submit` writes.
- `record.sh`: launcher script; resolves real script path (supports direct run, symlink, and hardlink entry).
- `warehouse/YYYY/MM/YYYY-MM-DD.md`: generated daily records.
- `fixtures/template.md`: markdown template reference.

Keep runtime code in `src/`. Keep generated content in `warehouse/` only; do not mix generated files into `src/`.

## Build, Test, and Development Commands
- `./record.sh`: start the app with default port discovery (starting from `8000`).
- `python src/server.py --host 127.0.0.1 --port 8000`: run directly without wrapper.
- `python -m py_compile src/server.py`: quick syntax check before submitting changes.

After startup, open the printed URL, submit a form, and confirm a file is created under `warehouse/<year>/<month>/`.

## Coding Style & Naming Conventions
- Python: follow PEP 8, 4-space indentation, type hints for new/changed functions.
- Use `snake_case` for variables/functions, `UPPER_SNAKE_CASE` for constants.
- Keep request validation explicit and close to request handling logic.
- Bash (`record.sh`): keep `set -euo pipefail`; prefer quoted variables and defensive path handling.

## Testing Guidelines
This repository currently has no automated test suite. For now, validate changes with:
1. `python -m py_compile src/server.py`
2. manual submit flow in browser
3. output file content check in `warehouse/`

When adding tests, place them in `tests/` and use names like `test_<feature>.py`.

## Commit & Pull Request Guidelines
Git history is not available in this workspace, so use this recommended format:
- Commit messages: `type(scope): summary` (e.g., `fix(record): resolve hardlink root detection`).
- Keep commits focused; avoid mixing refactor + behavior changes.
- PRs should include: purpose, behavior change summary, manual verification steps, and sample output path (for example `warehouse/2026/03/2026-03-04.md`).

## Security & Configuration Tips
- Do not expose the server publicly unless needed; default `127.0.0.1` is preferred.
- Treat `warehouse/` content as user data; avoid destructive cleanup in feature branches.
