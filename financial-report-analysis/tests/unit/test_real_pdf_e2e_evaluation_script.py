from __future__ import annotations

import os
from pathlib import Path
import subprocess


def _isolated_env(**overrides: str) -> dict[str, str]:
    env = {
        key: value
        for key in ("PATH", "HOME", "USER", "TMPDIR")
        if (value := os.environ.get(key)) is not None
    }
    env.update(overrides)
    return env


def test_real_pdf_e2e_evaluation_script_loads_defaults_from_env_file(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    sample_pdf = (
        project_root.parent
        / "report"
        / "downloads"
        / "hk_stocks"
        / "00001"
        / "annual"
        / "2025_annual_en.pdf"
    )

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "FRA_OLLAMA_FALLBACK_E2E_MARKET=HK",
                "FRA_OLLAMA_FALLBACK_E2E_STOCK_CODE=00001",
                "FRA_OLLAMA_FALLBACK_E2E_FISCAL_YEAR=2025",
                "FRA_OLLAMA_FALLBACK_E2E_REPORT_TYPE=annual",
                "FRA_OLLAMA_FALLBACK_E2E_FILENAME=2025_annual_en.pdf",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(project_root / "scripts" / "run-real-pdf-e2e-evaluation.sh"), "--dry-run"],
        cwd=project_root,
        env=_isolated_env(FRA_E2E_ENV_FILE=str(env_file)),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert f"pdf_path={sample_pdf}" in result.stdout
    assert "market=HK" in result.stdout
    assert "stock_code=00001" in result.stdout
    assert "fiscal_year=2025" in result.stdout


def test_real_pdf_e2e_evaluation_script_supports_deterministic_report_mode(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [str(project_root / "scripts" / "run-real-pdf-e2e-evaluation.sh"), "--dry-run"],
        cwd=project_root,
        env=_isolated_env(
            FRA_E2E_DETERMINISTIC_ONLY="true",
            FRA_E2E_EXPECTED_METRIC_IDS=(
                "revenue,operating_cost,total_assets,operating_cash_flow"
            ),
            FRA_E2E_OUTPUT_DIR=str(tmp_path / "reports"),
        ),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert "deterministic_only=true" in result.stdout
    assert (
        "expected_metric_ids=revenue,operating_cost,total_assets,operating_cash_flow"
        in result.stdout
    )
    assert (
        "metric_report="
        f"{tmp_path}/reports/HK_00001_2025_annual_deterministic_metric_availability.md"
    ) in result.stdout
    assert (
        "summary="
        f"{tmp_path}/reports/HK_00001_2025_annual_deterministic_summary.txt"
    ) in result.stdout


def test_real_pdf_e2e_evaluation_script_process_env_overrides_env_file(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "FRA_E2E_DETERMINISTIC_ONLY=false",
                "FRA_E2E_EXPECTED_METRIC_IDS=wrong_metric",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(project_root / "scripts" / "run-real-pdf-e2e-evaluation.sh"), "--dry-run"],
        cwd=project_root,
        env=_isolated_env(
            FRA_E2E_ENV_FILE=str(env_file),
            FRA_E2E_DETERMINISTIC_ONLY="true",
            FRA_E2E_EXPECTED_METRIC_IDS=(
                "revenue,operating_cost,total_assets,operating_cash_flow"
            ),
        ),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert "deterministic_only=true" in result.stdout
    assert (
        "expected_metric_ids=revenue,operating_cost,total_assets,operating_cash_flow"
        in result.stdout
    )
    assert "wrong_metric" not in result.stdout
