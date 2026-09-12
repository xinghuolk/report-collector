.PHONY: test-fast test test-all test-real-pdf lint

test-fast:
	uv run pytest -m "not slow and not real_pdf and not ollama and not external"

test:
	uv run pytest -m "not slow"

test-all:
	uv run pytest

test-real-pdf:
	REAL_PDF_LIMIT=3 REAL_PDF_JOBS=2 PER_TEST_TIMEOUT_SECONDS=240 \
		./scripts/run-real-pdf-matrix.sh

lint:
	uv run ruff check src tests
