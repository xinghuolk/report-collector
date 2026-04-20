from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class MetricMappingDefinition:
    metric_id: str
    statement_type: str
    allowed_table_kinds: tuple[str, ...]
    normalized_row_labels: tuple[str, ...]
    period_scope: str
    value_type: str
    unit_expectation: str | None
    sign_rule: str
    aliases_by_market: Mapping[str, tuple[str, ...]]


class MetricMappingRegistry:
    def __init__(self, definitions: Iterable[MetricMappingDefinition]) -> None:
        self.definitions = tuple(definitions)

    def match(
        self,
        *,
        table_kind: str,
        normalized_row_label: str | None,
        value_time_shape: str | None,
        statement_scope_guess: str,
        market: str,
    ) -> MetricMappingDefinition | None:
        del statement_scope_guess
        if normalized_row_label is None:
            return None

        normalized_label = _normalize_label(normalized_row_label)
        normalized_market = market.upper()

        for definition in self.definitions:
            if table_kind not in definition.allowed_table_kinds:
                continue
            if not _value_time_shape_matches(
                expected=definition.period_scope,
                actual=value_time_shape,
            ):
                continue
            if normalized_label in _definition_labels(definition, market=normalized_market):
                return definition
        return None

    def get_metric_definition(self, metric_id: str) -> MetricMappingDefinition | None:
        for definition in self.definitions:
            if definition.metric_id == metric_id:
                return definition
        return None

    def iter_metric_definitions(self) -> tuple[MetricMappingDefinition, ...]:
        return self.definitions


def load_metric_registry(source: str | None = None) -> MetricMappingRegistry:
    if source is not None:
        raise NotImplementedError("external registry sources are not implemented yet")
    return MetricMappingRegistry(_DEFAULT_DEFINITIONS)


def get_metric_definition(metric_id: str) -> MetricMappingDefinition | None:
    return load_metric_registry().get_metric_definition(metric_id)


def iter_metric_definitions() -> tuple[MetricMappingDefinition, ...]:
    return load_metric_registry().iter_metric_definitions()


def _definition_labels(
    definition: MetricMappingDefinition,
    *,
    market: str,
) -> set[str]:
    labels = {_normalize_label(label) for label in definition.normalized_row_labels}
    for label in definition.aliases_by_market.get(market, ()):
        labels.add(_normalize_label(label))
    return labels


def _normalize_label(value: str) -> str:
    normalized = value.replace("_", " ")
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def _value_time_shape_matches(*, expected: str, actual: str | None) -> bool:
    if actual is None:
        return False
    normalized_actual = actual.strip().casefold().replace("-", "_")
    normalized_expected = expected.strip().casefold().replace("-", "_")
    if normalized_expected == "point_in_time":
        return normalized_actual in {"point_in_time", "point"}
    return normalized_actual == normalized_expected


_DEFAULT_DEFINITIONS = (
    MetricMappingDefinition(
        metric_id="revenue",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement", "metrics", "key_metrics"),
        normalized_row_labels=("revenue", "operating revenue"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("营业收入", "营业总收入"), "HK": ("revenue", "turnover")},
    ),
    MetricMappingDefinition(
        metric_id="operating_profit",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("operating profit",),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("营业利润",), "HK": ("profit from operations",)},
    ),
    MetricMappingDefinition(
        metric_id="net_profit",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("net profit", "profit for the period"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("净利润",), "HK": ("profit attributable to shareholders",)},
    ),
    MetricMappingDefinition(
        metric_id="operating_cash_flow",
        statement_type="cash_flow_statement",
        allowed_table_kinds=("cash_flow_statement",),
        normalized_row_labels=("operating cash flow",),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("经营活动产生的现金流量净额",), "HK": ("net cash from operating activities",)},
    ),
    MetricMappingDefinition(
        metric_id="cash",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("cash", "cash and cash equivalents"),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("货币资金", "现金及现金等价物"), "HK": ("cash and cash equivalents",)},
    ),
    MetricMappingDefinition(
        metric_id="total_assets",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("total assets",),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="non_negative",
        aliases_by_market={"CN": ("资产总计", "总资产"), "HK": ("total assets",)},
    ),
    MetricMappingDefinition(
        metric_id="total_liabilities",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("total liabilities",),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="non_negative",
        aliases_by_market={"CN": ("负债合计", "总负债"), "HK": ("total liabilities",)},
    ),
)
