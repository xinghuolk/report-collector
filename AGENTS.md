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

### Real PDF / Ollama Validation Strategy
- Do not use the full real-PDF matrix as the default close-out test for every change. Start with targeted unit tests and narrow mocked integration tests, then run the smallest relevant real-PDF node(s).
- The `financial-report-analysis/scripts/run-real-pdf-matrix.sh` matrix is expensive and should be reserved for final validation of extraction/fallback changes or when explicitly requested.
- The default real-PDF matrix intentionally excludes Ollama-backed nodes. Run Ollama-backed real-PDF tests only when semantic fallback behavior is in scope, and opt in explicitly with the script marker override.
- Run real-PDF and live Ollama validation serially, not in parallel. Use per-test timeouts and log output when running the matrix so partial results survive interruption.
- Current benchmark from the completed fallback-gating fix: HK `09987` Q3 row-label fallback calls were reduced from `124` to `11`, CN `601919` 2024 annual completed with `row_label = 2`, and the default real-PDF matrix passed `43` non-Ollama `real_pdf` nodes.
- If real-PDF validation becomes slow again, first inspect fallback call counts and gating before increasing timeouts or broadening the test matrix.
- For quick real-PDF smoke tests, prefer `REAL_PDF_LIMIT=3 REAL_PDF_JOBS=2 PER_TEST_TIMEOUT_SECONDS=240 financial-report-analysis/scripts/run-real-pdf-matrix.sh` from Git Bash. Ollama/external markers are forced back to one job unless `ALLOW_OLLAMA_PARALLEL=1` is explicitly set.
- For performance profiling, separate PDF/table extraction time from Ollama fallback time. A recent live-Ollama probe on HK `09987` Q3 measured `20.72s` total, `8.11s` Ollama row-label fallback, and `12.61s` non-Ollama pipeline time. A promoted row-label Ollama-only probe measured `12` calls in `7.96s` with median `0.67s` per call.
- `FRA_SEMANTIC_FALLBACK_MAX_CONCURRENCY=2` can be used for local Ollama concurrency experiments; keep the default at `1` for stable close-out validation.

## Commit & Pull Request Guidelines
- Follow Conventional Commits where practical (`feat:`, `fix:`, `chore:`). Existing history uses `feat:`/`fix:` prefixes consistently.
- Keep commits focused by subproject (avoid mixing unrelated `report/` and `pdf-reader-mcp/` changes in one commit).
- PR requirement: clear summary and scope.
- PR requirement: linked issue(s) when applicable.
- PR requirement: test evidence (for example `uv run pytest` or `pnpm run test`).
- PR requirement: API/behavior examples for user-facing changes (request/response snippets or screenshots for docs/UI).
