# Repository Guidelines

## Project Structure & Module Organization
This repository contains multiple report-collection tools:
- `report/`: main Python service (MCP + HTTP API). Core code is in `report/src/`, tests in `report/tests/`, and examples in `report/examples/`.
- `pdf-reader-mcp/`: TypeScript MCP server for PDF parsing. Source in `pdf-reader-mcp/src/`, tests in `pdf-reader-mcp/test/`, docs in `pdf-reader-mcp/docs/`.
- `cninfo/` and `cninfo_scraper/`: standalone CNINFO utilities and scripts.

Prefer adding new backend features under `report/src/` unless the change is specifically PDF-reader behavior.

## Build, Test, and Development Commands
Run commands from each subproject directory.

Python service (`report/`):
- `uv sync`: install dependencies from `pyproject.toml`.
- `uv run python -m src.main`: start the MCP server.
- `uv run python -m src.server --mode http --host 0.0.0.0 --port 8000`: run HTTP API locally.
- `uv run pytest`: run full test suite with coverage output.

TypeScript service (`pdf-reader-mcp/`):
- `pnpm install`: install dependencies.
- `pnpm run build`: compile TypeScript to `dist/`.
- `pnpm run test`: run Vitest tests.
- `pnpm run validate`: run format check, lint, and tests before PRs.

## Coding Style & Naming Conventions
Python (`report/`):
- 4-space indentation, type hints expected (`mypy` is configured with `disallow_untyped_defs = true`).
- Lint/format with Ruff (`line-length = 88`); keep modules snake_case and classes PascalCase.

TypeScript (`pdf-reader-mcp/`):
- Follow ESLint + Prettier defaults.
- Use camelCase for variables/functions, PascalCase for types/classes, and descriptive file names (for example `readPdf.ts`, `pathUtils.test.ts`).

## Testing Guidelines
- Python tests use `pytest` with markers (`unit`, `integration`, `slow`).
- Test naming should match `test_*.py` or `*_test.py`.
- TypeScript tests use Vitest with `*.test.ts` naming.
- No fixed coverage threshold is enforced, but new changes should include tests and avoid reducing existing coverage meaningfully.

## Commit & Pull Request Guidelines
- Follow Conventional Commits where practical (`feat:`, `fix:`, `chore:`). Existing history uses `feat:`/`fix:` prefixes consistently.
- Keep commits focused by subproject (avoid mixing unrelated `report/` and `pdf-reader-mcp/` changes in one commit).
- PR requirement: clear summary and scope.
- PR requirement: linked issue(s) when applicable.
- PR requirement: test evidence (for example `uv run pytest` or `pnpm run test`).
- PR requirement: API/behavior examples for user-facing changes (request/response snippets or screenshots for docs/UI).
