#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

DRY_RUN=false

usage() {
  cat <<'USAGE'
Usage: scripts/run-real-pdf-e2e-evaluation.sh [--dry-run]

Runs a repeatable real-PDF evaluation:
  1. Real PDF extract/persist/readback E2E.
  2. Real PDF Ollama fallback E2E.
  3. Turtle investment metric availability report.
  4. Availability status summary.

Configuration defaults are loaded from .env. Set FRA_E2E_ENV_FILE to use a
different env file. The default target is derived from:
  FRA_E2E_* first, then FRA_OLLAMA_FALLBACK_E2E_*, then FRA_REAL_PDF_E2E_*.

Supported overrides:
  FRA_E2E_MARKET
  FRA_E2E_STOCK_CODE
  FRA_E2E_FISCAL_YEAR
  FRA_E2E_REPORT_TYPE
  FRA_E2E_FILENAME
  FRA_E2E_PDF_PATH
  FRA_E2E_OUTPUT_DIR
  FRA_E2E_DETERMINISTIC_ONLY
  FRA_E2E_EXPECTED_METRIC_IDS

Options:
  --dry-run  Print resolved configuration without running tests or extraction.
  -h, --help Show this help text.
USAGE
}

while (($#)); do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

FRA_ENV_OVERRIDE_NAMES=(
  FRA_E2E_ENV_FILE
  FRA_E2E_MARKET
  FRA_E2E_STOCK_CODE
  FRA_E2E_FISCAL_YEAR
  FRA_E2E_REPORT_TYPE
  FRA_E2E_FILENAME
  FRA_E2E_PDF_PATH
  FRA_E2E_OUTPUT_DIR
  FRA_E2E_DETERMINISTIC_ONLY
  FRA_E2E_EXPECTED_METRIC_IDS
  FRA_OLLAMA_FALLBACK_E2E_MARKET
  FRA_OLLAMA_FALLBACK_E2E_STOCK_CODE
  FRA_OLLAMA_FALLBACK_E2E_FISCAL_YEAR
  FRA_OLLAMA_FALLBACK_E2E_REPORT_TYPE
  FRA_OLLAMA_FALLBACK_E2E_FILENAME
  FRA_REAL_PDF_E2E_MARKET
  FRA_REAL_PDF_E2E_STOCK_CODE
  FRA_REAL_PDF_E2E_FISCAL_YEAR
  FRA_REAL_PDF_E2E_REPORT_TYPE
  FRA_REAL_PDF_E2E_FILENAME
)
declare -A FRA_ENV_OVERRIDE_VALUES=()
FRA_ENV_OVERRIDE_SET=()
for env_name in "${FRA_ENV_OVERRIDE_NAMES[@]}"; do
  if [[ -v "$env_name" ]]; then
    FRA_ENV_OVERRIDE_SET+=("$env_name")
    FRA_ENV_OVERRIDE_VALUES["$env_name"]="${!env_name}"
  fi
done

ENV_FILE="${FRA_E2E_ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
for env_name in "${FRA_ENV_OVERRIDE_SET[@]}"; do
  printf -v "$env_name" '%s' "${FRA_ENV_OVERRIDE_VALUES[$env_name]}"
  export "$env_name"
done

MARKET="${FRA_E2E_MARKET:-${FRA_OLLAMA_FALLBACK_E2E_MARKET:-${FRA_REAL_PDF_E2E_MARKET:-HK}}}"
STOCK_CODE="${FRA_E2E_STOCK_CODE:-${FRA_OLLAMA_FALLBACK_E2E_STOCK_CODE:-${FRA_REAL_PDF_E2E_STOCK_CODE:-00001}}}"
FISCAL_YEAR="${FRA_E2E_FISCAL_YEAR:-${FRA_OLLAMA_FALLBACK_E2E_FISCAL_YEAR:-${FRA_REAL_PDF_E2E_FISCAL_YEAR:-2025}}}"
REPORT_TYPE="${FRA_E2E_REPORT_TYPE:-${FRA_OLLAMA_FALLBACK_E2E_REPORT_TYPE:-annual}}"
FILENAME="${FRA_E2E_FILENAME:-${FRA_OLLAMA_FALLBACK_E2E_FILENAME:-${FRA_REAL_PDF_E2E_FILENAME:-}}}"
OUTPUT_DIR="${FRA_E2E_OUTPUT_DIR:-.e2e-evaluation-reports}"
DETERMINISTIC_ONLY="${FRA_E2E_DETERMINISTIC_ONLY:-false}"
EXPECTED_METRIC_IDS="${FRA_E2E_EXPECTED_METRIC_IDS:-}"
REPORT_SUFFIX="metric_availability"
SUMMARY_SUFFIX="summary"
if [[ "$DETERMINISTIC_ONLY" == "true" ]]; then
  REPORT_SUFFIX="deterministic_metric_availability"
  SUMMARY_SUFFIX="deterministic_summary"
fi

if [[ -z "$FILENAME" ]]; then
  if [[ "$MARKET" == "CN" ]]; then
    FILENAME="${FISCAL_YEAR}_年度报告.pdf"
  else
    FILENAME="${FISCAL_YEAR}_annual_en.pdf"
  fi
fi

if [[ "$MARKET" == "CN" ]]; then
  MARKET_DIR="cn_stocks"
  REPORT_LANGUAGE="zh"
else
  MARKET_DIR="hk_stocks"
  REPORT_LANGUAGE="en"
fi

PDF_PATH="${FRA_E2E_PDF_PATH:-../report/downloads/${MARKET_DIR}/${STOCK_CODE}/${REPORT_TYPE}/${FILENAME}}"
REPORT_PATH="${OUTPUT_DIR}/${MARKET}_${STOCK_CODE}_${FISCAL_YEAR}_${REPORT_TYPE}_${REPORT_SUFFIX}.md"
SUMMARY_PATH="${OUTPUT_DIR}/${MARKET}_${STOCK_CODE}_${FISCAL_YEAR}_${REPORT_TYPE}_${SUMMARY_SUFFIX}.txt"

print_config() {
  printf 'env_file=%s\n' "$ENV_FILE"
  printf 'pdf_path=%s\n' "$(python -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).resolve())' "$PDF_PATH")"
  printf 'market=%s\n' "$MARKET"
  printf 'stock_code=%s\n' "$STOCK_CODE"
  printf 'fiscal_year=%s\n' "$FISCAL_YEAR"
  printf 'report_type=%s\n' "$REPORT_TYPE"
  printf 'filename=%s\n' "$FILENAME"
  printf 'output_dir=%s\n' "$OUTPUT_DIR"
  printf 'deterministic_only=%s\n' "$DETERMINISTIC_ONLY"
  printf 'expected_metric_ids=%s\n' "$EXPECTED_METRIC_IDS"
  printf 'metric_report=%s\n' "$REPORT_PATH"
  printf 'summary=%s\n' "$SUMMARY_PATH"
}

if [[ "$DRY_RUN" == true ]]; then
  print_config
  exit 0
fi

if [[ ! -f "$PDF_PATH" ]]; then
  echo "PDF not found: $PDF_PATH" >&2
  print_config >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

EXPECTED_METRIC_ARGS=()
if [[ -n "$EXPECTED_METRIC_IDS" ]]; then
  IFS=',' read -r -a EXPECTED_METRIC_ARRAY <<< "$EXPECTED_METRIC_IDS"
  for metric_id in "${EXPECTED_METRIC_ARRAY[@]}"; do
    metric_id="${metric_id//[[:space:]]/}"
    if [[ -n "$metric_id" ]]; then
      EXPECTED_METRIC_ARGS+=(--expected-metric-id "$metric_id")
    fi
  done
fi

echo "Resolved evaluation target:"
print_config

echo
echo "[1/3] Running real PDF extract/persist/readback E2E..."
FRA_REAL_PDF_E2E_MARKET="$MARKET" \
FRA_REAL_PDF_E2E_STOCK_CODE="$STOCK_CODE" \
FRA_REAL_PDF_E2E_FISCAL_YEAR="$FISCAL_YEAR" \
FRA_REAL_PDF_E2E_FILENAME="$FILENAME" \
uv run pytest tests/integration/test_real_pdf_extract_persist_e2e.py -q -rs

echo
echo "[2/3] Running real PDF Ollama fallback E2E..."
FRA_OLLAMA_FALLBACK_E2E_MARKET="$MARKET" \
FRA_OLLAMA_FALLBACK_E2E_STOCK_CODE="$STOCK_CODE" \
FRA_OLLAMA_FALLBACK_E2E_FISCAL_YEAR="$FISCAL_YEAR" \
FRA_OLLAMA_FALLBACK_E2E_REPORT_TYPE="$REPORT_TYPE" \
FRA_OLLAMA_FALLBACK_E2E_FILENAME="$FILENAME" \
uv run pytest \
  tests/integration/test_semantic_recovery_regressions.py::test_ollama_fallback_e2e_supports_replaceable_real_pdf \
  -q -rs

echo
echo "[3/3] Generating metric availability report..."
if [[ "$DETERMINISTIC_ONLY" == "true" ]]; then
  FRA_SEMANTIC_FALLBACK_ENABLED=false uv run python scripts/report_metric_availability.py \
    --pdf-path "$PDF_PATH" \
    --market "$MARKET" \
    "${EXPECTED_METRIC_ARGS[@]}" \
    --output "$REPORT_PATH"
else
  uv run python scripts/report_metric_availability.py \
    --pdf-path "$PDF_PATH" \
    --market "$MARKET" \
    "${EXPECTED_METRIC_ARGS[@]}" \
    --output "$REPORT_PATH"
fi

{
  echo "Metric availability summary"
  echo "report=$REPORT_PATH"
  awk -F'|' '
    /^\| [a-zA-Z0-9_]+ / {
      gsub(/^ +| +$/, "", $2)
      gsub(/^ +| +$/, "", $3)
      if ($2 != "metric_id") {
        count[$3]++
        total++
      }
    }
    END {
      printf "total=%d\n", total
      printf "present=%d\n", count["present"] + 0
      printf "absent=%d\n", count["absent"] + 0
      printf "not_surfaced=%d\n", count["not_surfaced"] + 0
    }
  ' "$REPORT_PATH"
  grep '^semantic_fallback_call_counts:' "$REPORT_PATH" || true
} | tee "$SUMMARY_PATH"

echo
echo "Evaluation complete."
echo "Metric report: $REPORT_PATH"
echo "Summary: $SUMMARY_PATH"
