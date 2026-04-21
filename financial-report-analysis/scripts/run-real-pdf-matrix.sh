#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TEST_PATHS=(
  "tests/integration/test_analysis_api.py"
  "tests/integration/test_semantic_recovery_regressions.py"
  "tests/integration/test_annual_structure_recovery.py"
  "tests/integration/test_table_structure_ingestion.py"
)

MARK_EXPR="${REAL_PDF_MARK_EXPR:-real_pdf}"
PER_TEST_TIMEOUT_SECONDS="${PER_TEST_TIMEOUT_SECONDS:-}"
LIST_ONLY=false

usage() {
  cat <<'USAGE'
Usage: scripts/run-real-pdf-matrix.sh [--list] [--] [pytest args...]

Runs real PDF integration tests one pytest node at a time, in collection order.

Options:
  --list    Print collected real PDF test node ids without running them.
  -h, --help
            Show this help text.

Environment:
  REAL_PDF_MARK_EXPR            Pytest marker expression to collect. Default: real_pdf
  PER_TEST_TIMEOUT_SECONDS      Optional timeout per test node, using timeout(1).

Examples:
  scripts/run-real-pdf-matrix.sh --list
  scripts/run-real-pdf-matrix.sh
  PER_TEST_TIMEOUT_SECONDS=600 scripts/run-real-pdf-matrix.sh -s
USAGE
}

while (($#)); do
  case "$1" in
    --list)
      LIST_ONLY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

mapfile -t TEST_NODES < <(
  uv run pytest "${TEST_PATHS[@]}" --collect-only -q -m "$MARK_EXPR" -o addopts= \
    | sed -n '/::/p'
)

if ((${#TEST_NODES[@]} == 0)); then
  echo "No tests collected for marker expression: $MARK_EXPR" >&2
  exit 1
fi

if [[ "$LIST_ONLY" == true ]]; then
  printf '%s\n' "${TEST_NODES[@]}"
  exit 0
fi

echo "Collected ${#TEST_NODES[@]} real PDF test nodes."
echo "Running sequentially with marker expression: $MARK_EXPR"

for index in "${!TEST_NODES[@]}"; do
  test_node="${TEST_NODES[$index]}"
  current=$((index + 1))
  start_epoch="$(date +%s)"

  printf '\n[%s/%s] %s\n' "$current" "${#TEST_NODES[@]}" "$test_node"

  if [[ -n "$PER_TEST_TIMEOUT_SECONDS" ]]; then
    timeout "${PER_TEST_TIMEOUT_SECONDS}s" uv run pytest "$test_node" -q -o addopts= "$@"
  else
    uv run pytest "$test_node" -q -o addopts= "$@"
  fi

  end_epoch="$(date +%s)"
  printf '[%s/%s] passed in %ss\n' \
    "$current" "${#TEST_NODES[@]}" "$((end_epoch - start_epoch))"
done

echo "Real PDF matrix passed: ${#TEST_NODES[@]} test nodes."
