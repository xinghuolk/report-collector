from __future__ import annotations

import json

import httpx

from financial_report_analysis.semantic_fallback.models import (
    CurrencyFallbackRequest,
    RowLabelFallbackRequest,
    SemanticFallbackResult,
    TableKindFallbackRequest,
    UnitFallbackRequest,
    supported_currency_outputs,
    supported_row_label_outputs,
    supported_table_kind_outputs,
    supported_unit_outputs,
)


class OllamaSemanticFallbackClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3.5:9b",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds

    def classify_table_kind(
        self,
        request: TableKindFallbackRequest,
    ) -> SemanticFallbackResult:
        prompt = (
            "Choose exactly one table kind label from this set: "
            f"{', '.join(supported_table_kind_outputs())}.\n"
            f"Title: {request.title_text}\n"
            f"Context: {request.local_context}\n"
            f"Deterministic candidates: {', '.join(request.deterministic_candidates) or 'none'}\n"
            "Return JSON with keys value and confidence."
        )
        payload = self._invoke(prompt)
        value = _normalize_choice(
            payload.get("value", ""),
            allowed=supported_table_kind_outputs(),
            default="unknown",
        )
        confidence = _parse_confidence(payload.get("confidence"))
        return SemanticFallbackResult(
            value=value,
            semantic_source="llm_fallback",
            semantic_confidence=confidence,
            fallback_reason=request.ambiguity_reason,
        )

    def normalize_row_label(
        self,
        request: RowLabelFallbackRequest,
    ) -> SemanticFallbackResult:
        prompt = (
            "Classify the financial statement row label into exactly one canonical "
            "label from this set: "
            f"{', '.join(supported_row_label_outputs())}.\n"
            "Use these mappings when they apply:\n"
            "- revenue, turnover, business revenue, core revenue -> revenue\n"
            "- operating income, operating profit, profit from operations -> operating_profit\n"
            "- gross profit, gross profit for the period, gross profit attributable to operations -> gross_profit\n"
            "- profit for the period, profit attributable to owners -> net_profit\n"
            "- net cash from operating activities, net cash generated from operating activities, net cash used in operating activities -> operating_cash_flow\n"
            "- net cash from investing activities, net cash generated from investing activities, net cash used in investing activities -> investing_cash_flow\n"
            "- net cash from financing activities, net cash generated from financing activities, net cash used in financing activities -> financing_cash_flow\n"
            "- cash and cash equivalents, funds on hand -> cash\n"
            "- total assets -> total_assets\n"
            "- total liabilities -> total_liabilities\n"
            "- total equity, total shareholders' equity -> equity\n"
            "- equity attributable to owners of the parent, equity attributable to equity holders of the company -> equity_attributable_to_owners\n"
            "- accounts receivable, accounts receivables, 应收账款 -> accounts_receiv\n"
            "- notes receivable, notes receivables, 应收票据 -> notes_receiv\n"
            "- other receivables, 其他应收款 -> oth_receiv\n"
            "- contract liabilities, 合同负债 -> contract_liab\n"
            "- payments received in advance, advances from customers, 预收款项 -> adv_receipts\n"
            "- accounts payable, 应付账款 -> acct_payable\n"
            "- notes payable, 应付票据 -> notes_payable\n"
            "Always choose none for non-metric variants such as:\n"
            "- revenue growth, revenue increase, growth rate, margin, ratio -> none\n"
            "- summary-style rows such as summary or overview lines -> none\n"
            "- free cash flow, net increase/decrease in cash and cash equivalents, cash flow ratio, cash flow trend, cash flow variance, subtotal -> none\n"
            "- 每股, 小计 -> none\n"
            "- accounts receivable financing, long-term receivables, employee compensation payable, taxes payable, bonds payable -> none\n"
            "- 应收款项融资, 长期应收款, 应付职工薪酬, 应交税费, 应付债券, 经营性应收项目的减少（增加以“－”号填列） -> none\n"
            "- deferred revenue -> none\n"
            "- net assets, book value, per-share equity, equity ratio -> none\n"
            "If the row label does not clearly match one of these meanings, choose none.\n"
            f"Table kind: {request.table_kind}\n"
            f"Raw label: {request.raw_label}\n"
            f"Context: {request.local_context}\n"
            f"Deterministic candidates: {', '.join(request.deterministic_candidates) or 'none'}\n"
            'Return exactly JSON like {"value":"revenue","confidence":0.95}.'
        )
        payload = self._invoke(prompt)
        value = _normalize_choice(
            payload.get("value", ""),
            allowed=supported_row_label_outputs(),
            default="none",
        )
        confidence = _parse_confidence(payload.get("confidence"))
        return SemanticFallbackResult(
            value=value,
            semantic_source="llm_fallback",
            semantic_confidence=confidence,
            fallback_reason=request.ambiguity_reason,
        )

    def interpret_currency(
        self,
        request: CurrencyFallbackRequest,
    ) -> SemanticFallbackResult:
        prompt = (
            "Classify the local financial-report currency marker into exactly one "
            f"value from this set: {', '.join(supported_currency_outputs())}.\n"
            "Only return CNY, HKD, USD, or unknown.\n"
            f"Raw text: {request.raw_text}\n"
            f"Context: {request.local_context}\n"
            f"Deterministic candidates: {', '.join(request.deterministic_candidates) or 'none'}\n"
            'Return exactly JSON like {"value":"HKD","confidence":0.95}.'
        )
        payload = self._invoke(prompt)
        value = _normalize_choice(
            payload.get("value", ""),
            allowed=supported_currency_outputs(),
            default="unknown",
            case="upper",
        )
        confidence = _parse_confidence(payload.get("confidence"))
        return SemanticFallbackResult(
            value=value,
            semantic_source="llm_fallback",
            semantic_confidence=confidence,
            fallback_reason=request.ambiguity_reason,
        )

    def interpret_unit(
        self,
        request: UnitFallbackRequest,
    ) -> SemanticFallbackResult:
        prompt = (
            "Classify the local financial-report unit marker into exactly one "
            f"value from this set: {', '.join(supported_unit_outputs())}.\n"
            "Only return yuan, thousand, million, billion, percent, or unknown.\n"
            "This is a local semantic interpretation only; do not infer propagation strategy.\n"
            f"Raw text: {request.raw_text}\n"
            f"Context: {request.local_context}\n"
            f"Deterministic candidates: {', '.join(request.deterministic_candidates) or 'none'}\n"
            'Return exactly JSON like {"value":"million","confidence":0.95}.'
        )
        payload = self._invoke(prompt)
        value = _normalize_choice(
            payload.get("value", ""),
            allowed=supported_unit_outputs(),
            default="unknown",
        )
        confidence = _parse_confidence(payload.get("confidence"))
        return SemanticFallbackResult(
            value=value,
            semantic_source="llm_fallback",
            semantic_confidence=confidence,
            fallback_reason=request.ambiguity_reason,
        )

    def _invoke(self, prompt: str) -> dict[str, object]:
        response = httpx.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "think": False,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        raw_response = payload.get("response", "{}")
        if isinstance(raw_response, str):
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError:
                parsed = {"value": raw_response}
            if isinstance(parsed, dict):
                return parsed
        return {}


def _normalize_choice(
    value: object,
    *,
    allowed: tuple[str, ...],
    default: str,
    case: str = "casefold",
) -> str:
    normalized = str(value).strip()
    if case == "upper":
        normalized = normalized.upper()
    else:
        normalized = normalized.casefold()
    return normalized if normalized in allowed else default


def _parse_confidence(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
