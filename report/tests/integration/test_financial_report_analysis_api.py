from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import PDFHandlerSingleton


class _StubAnalysisHandler:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    async def extract_financial_report_analysis(
        self,
        request: dict[str, object],
    ) -> dict[str, object]:
        self.request = request
        return {
            "document": {
                "document_id": "/tmp/mock.pdf",
                "pdf_path": "/tmp/mock.pdf",
                "pdf_url": None,
                "market": "CN",
                "min_confidence": 0.8,
            },
            "canonical_fact_set_id": "/tmp/mock.pdf:canonical:v1",
            "derived_fact_set_id": "/tmp/mock.pdf:derived:v1",
            "validation_report_id": "/tmp/mock.pdf:validation:v1",
            "quality_gate": "review",
            "key_facts": [],
            "ttm_facts": [],
            "analysis_snapshot": {"summary": "", "blocked_items": []},
            "blocked_items": [],
        }


def test_report_extract_analysis_forwards_service_contract(monkeypatch) -> None:
    handler = _StubAnalysisHandler()

    async def fake_get_instance(cls) -> _StubAnalysisHandler:
        return handler

    async def fake_shutdown(cls) -> None:
        return None

    monkeypatch.setattr(
        PDFHandlerSingleton,
        "get_instance",
        classmethod(fake_get_instance),
    )
    monkeypatch.setattr(
        PDFHandlerSingleton,
        "shutdown",
        classmethod(fake_shutdown),
    )

    client = TestClient(create_app())

    response = client.post(
        "/api/v1/extract/analysis",
        json={
            "pdf_path": "/tmp/mock.pdf",
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    assert handler.request == {
        "pdf_path": "/tmp/mock.pdf",
        "pdf_url": None,
        "market": "CN",
        "min_confidence": 0.8,
    }
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["data"]["quality_gate"] == "review"
    assert payload["data"]["canonical_fact_set_id"] == "/tmp/mock.pdf:canonical:v1"


def test_report_extract_analysis_returns_bad_gateway_for_service_failure(
    monkeypatch,
) -> None:
    class _FailingHandler:
        async def extract_financial_report_analysis(
            self,
            request: dict[str, object],
        ) -> dict[str, object]:
            raise RuntimeError("analysis service unavailable")

    async def fake_get_instance(cls) -> _FailingHandler:
        return _FailingHandler()

    async def fake_shutdown(cls) -> None:
        return None

    monkeypatch.setattr(
        PDFHandlerSingleton,
        "get_instance",
        classmethod(fake_get_instance),
    )
    monkeypatch.setattr(
        PDFHandlerSingleton,
        "shutdown",
        classmethod(fake_shutdown),
    )

    client = TestClient(create_app())

    response = client.post(
        "/api/v1/extract/analysis",
        json={"pdf_path": "/tmp/mock.pdf", "market": "CN"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "analysis service unavailable"


def test_report_extract_analysis_preserves_upstream_quality_gate_and_blockers(
    monkeypatch,
) -> None:
    class _UnsupportedHandler:
        async def extract_financial_report_analysis(
            self,
            request: dict[str, object],
        ) -> dict[str, object]:
            return {
                "document": {
                    "document_id": "/tmp/hk-zh.pdf",
                    "pdf_path": "/tmp/hk-zh.pdf",
                    "pdf_url": None,
                    "market": "HK",
                    "language": "zh-Hant",
                },
                "canonical_fact_set_id": "/tmp/hk-zh.pdf:canonical:v1",
                "derived_fact_set_id": "/tmp/hk-zh.pdf:derived:v1",
                "validation_report_id": "/tmp/hk-zh.pdf:validation:v1",
                "quality_gate": "review",
                "key_facts": [],
                "ttm_facts": [],
                "analysis_snapshot": {
                    "summary": "",
                    "blocked_items": [
                        {
                            "code": "unsupported_in_phase1",
                            "status": "unsupported_in_phase1",
                        }
                    ],
                },
                "blocked_items": [
                    {
                        "code": "unsupported_in_phase1",
                        "status": "unsupported_in_phase1",
                    }
                ],
            }

    async def fake_get_instance(cls) -> _UnsupportedHandler:
        return _UnsupportedHandler()

    async def fake_shutdown(cls) -> None:
        return None

    monkeypatch.setattr(
        PDFHandlerSingleton,
        "get_instance",
        classmethod(fake_get_instance),
    )
    monkeypatch.setattr(
        PDFHandlerSingleton,
        "shutdown",
        classmethod(fake_shutdown),
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/extract/analysis",
        json={"pdf_path": "/tmp/hk-zh.pdf", "market": "HK"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["quality_gate"] == "review"
    assert payload["data"]["blocked_items"] == [
        {
            "code": "unsupported_in_phase1",
            "status": "unsupported_in_phase1",
        }
    ]
