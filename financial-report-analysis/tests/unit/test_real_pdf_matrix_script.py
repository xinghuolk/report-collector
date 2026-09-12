from __future__ import annotations

from pathlib import Path


def test_real_pdf_matrix_script_exposes_parallel_job_controls() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "run-real-pdf-matrix.sh"
    ).read_text(encoding="utf-8")

    assert "REAL_PDF_JOBS" in script
    assert "REAL_PDF_LIMIT" in script
    assert "ALLOW_OLLAMA_PARALLEL" in script
    assert "marker_expr_contains_positive_marker" in script
    assert "not[[:space:]]+" in script
    assert "shift 2" in script
    assert "Running sequentially" not in script
