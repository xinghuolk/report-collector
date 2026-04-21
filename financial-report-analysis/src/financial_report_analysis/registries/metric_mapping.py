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
        metric_id="operating_cost",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("operating cost", "cost of sales", "cost of revenue"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("营业成本",),
            "HK": ("cost of sales", "cost of revenue"),
        },
    ),
    MetricMappingDefinition(
        metric_id="operating_profit",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("operating profit", "profit from operations"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("营业利润",), "HK": ("profit from operations",)},
    ),
    MetricMappingDefinition(
        metric_id="gross_profit",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("gross profit",),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("营业毛利", "毛利润", "毛利"),
            "HK": (
                "gross profit",
                "gross profit for the period",
                "gross profit attributable to operations",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="net_profit",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=(
            "net profit",
            "profit for the period",
            "profit attributable to shareholders",
            "profit attributable to equity holders",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("净利润",),
            "HK": (
                "profit for the period",
                "profit attributable to shareholders",
                "profit attributable to equity holders",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="n_income_attr_p",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=(
            "net profit attributable to owners of the parent",
            "profit attributable to owners of the parent",
            "profit attributable to equity holders of the company",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("归属于母公司股东的净利润", "归属于上市公司股东的净利润"),
            "HK": (
                "profit attributable to owners of the parent",
                "profit attributable to equity holders of the company",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="basic_eps",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement", "key_metrics", "metrics"),
        normalized_row_labels=(
            "basic earnings per share",
            "earnings per share - basic",
            "basic eps",
        ),
        period_scope="duration",
        value_type="per_share",
        unit_expectation="per_share_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("基本每股收益",),
            "HK": (
                "basic earnings per share",
                "earnings per share - basic",
                "basic eps",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="finance_exp",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("finance expense", "finance expenses", "finance costs"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("财务费用",),
            "HK": ("finance costs", "finance expenses"),
        },
    ),
    MetricMappingDefinition(
        metric_id="total_profit",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("total profit", "profit before tax"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("利润总额",), "HK": ("profit before tax",)},
    ),
    MetricMappingDefinition(
        metric_id="income_tax",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=("income tax", "income tax expense", "tax expense"),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={"CN": ("所得税费用",), "HK": ("income tax expense",)},
    ),
    MetricMappingDefinition(
        metric_id="minority_gain",
        statement_type="income_statement",
        allowed_table_kinds=("income_statement",),
        normalized_row_labels=(
            "minority interest profit",
            "profit attributable to non-controlling interests",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("少数股东损益",),
            "HK": ("profit attributable to non-controlling interests",),
        },
    ),
    MetricMappingDefinition(
        metric_id="operating_cash_flow",
        statement_type="cash_flow_statement",
        allowed_table_kinds=("cash_flow_statement",),
        normalized_row_labels=(
            "operating cash flow",
            "net cash from operating activities",
            "net cash generated from operating activities",
            "net cash used in operating activities",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("经营活动产生的现金流量净额",),
            "HK": (
                "net cash from operating activities",
                "net cash generated from operating activities",
                "net cash used in operating activities",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="c_pay_acq_const_fiolta",
        statement_type="cash_flow_statement",
        allowed_table_kinds=("cash_flow_statement",),
        normalized_row_labels=(
            "capital expenditure cash outflow",
            "payments for acquisition of property, plant and equipment",
            "payments for acquisition of property, plant and equipment and intangible assets",
            "payments for acquisition and construction of long-term assets",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="non_negative",
        aliases_by_market={
            "CN": ("购建固定资产、无形资产和其他长期资产支付的现金",),
            "HK": (
                "payments for acquisition of property, plant and equipment",
                "payments for acquisition of property, plant and equipment and intangible assets",
                "payments for acquisition and construction of long-term assets",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="depr_fa_coga_dpba",
        statement_type="cash_flow_statement",
        allowed_table_kinds=("cash_flow_statement",),
        normalized_row_labels=(
            "depreciation of fixed assets",
            "depreciation of property, plant and equipment",
            "depreciation of fixed assets oil and gas assets and productive biological assets",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="non_negative",
        aliases_by_market={
            "CN": ("固定资产折旧",),
            "HK": (
                "depreciation of property, plant and equipment",
                "depreciation of fixed assets oil and gas assets and productive biological assets",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="amort_intang_assets",
        statement_type="cash_flow_statement",
        allowed_table_kinds=("cash_flow_statement",),
        normalized_row_labels=(
            "amortisation of intangible assets",
            "amortization of intangible assets",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="non_negative",
        aliases_by_market={
            "CN": ("无形资产摊销",),
            "HK": (
                "amortisation of intangible assets",
                "amortization of intangible assets",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="lt_amort_deferred_exp",
        statement_type="cash_flow_statement",
        allowed_table_kinds=("cash_flow_statement",),
        normalized_row_labels=(
            "amortisation of long-term deferred expenses",
            "amortization of long-term deferred expenses",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="non_negative",
        aliases_by_market={
            "CN": ("长期待摊费用摊销",),
            "HK": (
                "amortisation of long-term deferred expenses",
                "amortization of long-term deferred expenses",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="c_pay_dist_dpcp_int_exp",
        statement_type="cash_flow_statement",
        allowed_table_kinds=("cash_flow_statement",),
        normalized_row_labels=(
            "cash paid for dividends or interest",
            "dividends paid",
            "dividends and interest paid",
            "cash paid for distribution of dividends or profits and interest expenses",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="non_negative",
        aliases_by_market={
            "CN": ("分配股利、利润或偿付利息支付的现金",),
            "HK": (
                "dividends paid",
                "dividends and interest paid",
                "cash paid for distribution of dividends or profits and interest expenses",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="investing_cash_flow",
        statement_type="cash_flow_statement",
        allowed_table_kinds=("cash_flow_statement",),
        normalized_row_labels=(
            "investing cash flow",
            "net cash from investing activities",
            "net cash generated from investing activities",
            "net cash used in investing activities",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("投资活动产生的现金流量净额",),
            "HK": (
                "net cash generated from investing activities",
                "net cash used in investing activities",
            ),
        },
    ),
    MetricMappingDefinition(
        metric_id="financing_cash_flow",
        statement_type="cash_flow_statement",
        allowed_table_kinds=("cash_flow_statement",),
        normalized_row_labels=(
            "financing cash flow",
            "net cash from financing activities",
            "net cash generated from financing activities",
            "net cash used in financing activities",
        ),
        period_scope="duration",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("筹资活动产生的现金流量净额",),
            "HK": (
                "net cash generated from financing activities",
                "net cash used in financing activities",
            ),
        },
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
    MetricMappingDefinition(
        metric_id="equity",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=("equity", "total equity", "total shareholders' equity"),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("所有者权益合计", "股东权益合计"),
            "HK": ("total equity", "total shareholders' equity"),
        },
    ),
    MetricMappingDefinition(
        metric_id="equity_attributable_to_owners",
        statement_type="balance_sheet",
        allowed_table_kinds=("balance_sheet",),
        normalized_row_labels=(
            "equity attributable to owners of the parent",
            "equity attributable to equity holders of the company",
        ),
        period_scope="point_in_time",
        value_type="amount",
        unit_expectation="currency_amount",
        sign_rule="allow_negative",
        aliases_by_market={
            "CN": ("归属于母公司股东权益", "归属于母公司所有者权益"),
            "HK": (
                "equity attributable to owners of the parent",
                "equity attributable to equity holders of the company",
            ),
        },
    ),
)
