#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TEST_PATHS=(
  "tests/integration/test_analysis_api.py"
  "tests/integration/test_semantic_recovery_regressions.py"
  "tests/integration/test_annual_structure_recovery.py"
  "tests/integration/test_table_structure_ingestion.py"
)

MARK_EXPR="${REAL_PDF_MARK_EXPR:-real_pdf and not ollama and not external}"
PER_TEST_TIMEOUT_SECONDS="${PER_TEST_TIMEOUT_SECONDS:-}"
REAL_PDF_JOBS="${REAL_PDF_JOBS:-1}"
REAL_PDF_LIMIT="${REAL_PDF_LIMIT:-}"
ALLOW_OLLAMA_PARALLEL="${ALLOW_OLLAMA_PARALLEL:-false}"
REAL_PDF_LOG_DIR="${REAL_PDF_LOG_DIR:-.real-pdf-matrix-logs}"
LIST_ONLY=false

usage() {
  cat <<'USAGE'
Usage: scripts/run-real-pdf-matrix.sh [--list] [--] [pytest args...]

Runs real PDF integration tests by pytest node, with optional node-level parallelism.

Options:
  --list    Print collected real PDF test node ids without running them.
  -h, --help
            Show this help text.

Environment:
  REAL_PDF_MARK_EXPR            Pytest marker expression to collect.
                                Default: real_pdf and not ollama and not external
  PER_TEST_TIMEOUT_SECONDS      Optional timeout per test node, using timeout(1).
  REAL_PDF_JOBS                 Number of pytest nodes to run concurrently.
                                Default: 1.
  REAL_PDF_LIMIT                Optional maximum number of collected nodes to run.
                                Useful for smoke-checking a few real PDFs.
  ALLOW_OLLAMA_PARALLEL         Allow REAL_PDF_JOBS > 1 for ollama/external markers.
                                Default: false.
  REAL_PDF_LOG_DIR              Directory for per-node logs.
                                Default: .real-pdf-matrix-logs

Examples:
  scripts/run-real-pdf-matrix.sh --list
  scripts/run-real-pdf-matrix.sh
  REAL_PDF_JOBS=4 scripts/run-real-pdf-matrix.sh
  REAL_PDF_LIMIT=3 REAL_PDF_JOBS=2 scripts/run-real-pdf-matrix.sh
  REAL_PDF_MARK_EXPR='real_pdf and ollama' scripts/run-real-pdf-matrix.sh --list
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

if [[ -n "$REAL_PDF_LIMIT" ]]; then
  if ! [[ "$REAL_PDF_LIMIT" =~ ^[0-9]+$ ]] || ((REAL_PDF_LIMIT < 1)); then
    echo "Invalid REAL_PDF_LIMIT=$REAL_PDF_LIMIT; ignoring limit." >&2
  elif ((REAL_PDF_LIMIT < ${#TEST_NODES[@]})); then
    TEST_NODES=("${TEST_NODES[@]:0:REAL_PDF_LIMIT}")
  fi
fi

if [[ "$LIST_ONLY" == true ]]; then
  printf '%s\n' "${TEST_NODES[@]}"
  exit 0
fi

if ! [[ "$REAL_PDF_JOBS" =~ ^[0-9]+$ ]] || ((REAL_PDF_JOBS < 1)); then
  echo "Invalid REAL_PDF_JOBS=$REAL_PDF_JOBS; falling back to 1." >&2
  REAL_PDF_JOBS=1
fi

marker_expr_contains_positive_marker() {
  local marker="$1"
  local normalized_expr
  normalized_expr="$(printf '%s' " $MARK_EXPR " | tr '[:upper:]' '[:lower:]')"
  [[ "$normalized_expr" =~ (^|[^a-z0-9_])${marker}([^a-z0-9_]|$) ]] \
    && ! [[ "$normalized_expr" =~ not[[:space:]]+${marker} ]]
}

normalized_allow_parallel="$(printf '%s' "$ALLOW_OLLAMA_PARALLEL" | tr '[:upper:]' '[:lower:]')"
if ((REAL_PDF_JOBS > 1)) \
  && { marker_expr_contains_positive_marker "ollama" \
    || marker_expr_contains_positive_marker "external"; }; then
  if [[ "$normalized_allow_parallel" != "1" && "$normalized_allow_parallel" != "true" && "$normalized_allow_parallel" != "yes" && "$normalized_allow_parallel" != "on" ]]; then
    echo "Ollama/external marker detected; forcing REAL_PDF_JOBS=1. Set ALLOW_OLLAMA_PARALLEL=1 to override." >&2
    REAL_PDF_JOBS=1
  fi
fi

mkdir -p "$REAL_PDF_LOG_DIR"

sanitize_node_id() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9_.-' '_'
}

run_test_node() {
  local index="$1"
  local test_node="$2"
  shift 2
  local current=$((index + 1))
  local start_epoch
  local end_epoch
  local log_file
  local status

  start_epoch="$(date +%s)"
  log_file="$REAL_PDF_LOG_DIR/${current}_$(sanitize_node_id "$test_node").log"

  printf '\n[%s/%s] %s\n' "$current" "${#TEST_NODES[@]}" "$test_node"

  if [[ -n "$PER_TEST_TIMEOUT_SECONDS" ]]; then
    timeout "${PER_TEST_TIMEOUT_SECONDS}s" uv run pytest "$test_node" -q -o addopts= "$@" >"$log_file" 2>&1
    status=$?
  else
    uv run pytest "$test_node" -q -o addopts= "$@" >"$log_file" 2>&1
    status=$?
  fi

  end_epoch="$(date +%s)"
  if ((status == 0)); then
    printf '[%s/%s] passed in %ss (%s)\n' \
      "$current" "${#TEST_NODES[@]}" "$((end_epoch - start_epoch))" "$log_file"
  else
    printf '[%s/%s] failed in %ss (%s)\n' \
      "$current" "${#TEST_NODES[@]}" "$((end_epoch - start_epoch))" "$log_file" >&2
    cat "$log_file" >&2
  fi
  return "$status"
}

echo "Collected ${#TEST_NODES[@]} real PDF test nodes."
echo "Running with REAL_PDF_JOBS=$REAL_PDF_JOBS and marker expression: $MARK_EXPR"

if ((REAL_PDF_JOBS == 1)); then
  for index in "${!TEST_NODES[@]}"; do
    run_test_node "$index" "${TEST_NODES[$index]}" "$@"
  done
else
  failures=0
  for index in "${!TEST_NODES[@]}"; do
    while (( $(jobs -pr | wc -l) >= REAL_PDF_JOBS )); do
      if ! wait -n; then
        failures=1
      fi
    done

    run_test_node "$index" "${TEST_NODES[$index]}" "$@" &
  done

  while (( $(jobs -pr | wc -l) > 0 )); do
    if ! wait -n; then
      failures=1
    fi
  done
  if ((failures != 0)); then
    exit 1
  fi
fi

echo "Real PDF matrix passed: ${#TEST_NODES[@]} test nodes."
