from __future__ import annotations

import os
from pathlib import Path
import subprocess


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
    sample_pdf.parent.mkdir(parents=True, exist_ok=True)
    sample_pdf.touch()

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

    env = os.environ.copy()
    env["FRA_E2E_ENV_FILE"] = str(env_file)

    result = subprocess.run(
        [str(project_root / "scripts" / "run-real-pdf-e2e-evaluation.sh"), "--dry-run"],
        cwd=project_root,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert f"pdf_path={sample_pdf}" in result.stdout
    assert "market=HK" in result.stdout
    assert "stock_code=00001" in result.stdout
    assert "fiscal_year=2025" in result.stdout
