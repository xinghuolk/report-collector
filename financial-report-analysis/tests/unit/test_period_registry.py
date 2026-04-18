from datetime import date

from financial_report_analysis.registries.period_registry import PeriodRegistry


def test_period_registry_reuses_existing_standard_period() -> None:
    registry = PeriodRegistry()

    first = registry.get_or_create_duration(
        fiscal_year=2024,
        reporting_scope="fy",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        accounting_standard="ifrs",
        disclosure_label_raw="FY2024",
    )
    second = registry.get_or_create_duration(
        fiscal_year=2024,
        reporting_scope="FY",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        accounting_standard="IFRS",
        disclosure_label_raw="Annual report 2024",
    )

    assert first is second
    assert first.period_id == second.period_id
    assert first.disclosure_label_raw == "FY2024"
    assert second.disclosure_label_raw == "FY2024"
    assert first.period_type == "DURATION"
    assert first.reporting_scope == "FY"
    assert first.accounting_standard == "IFRS"
    assert first.fiscal_period_index == 4
    assert first.adjusted_status == "ORIGINAL"
    assert first.is_stub_period is False
    assert first.period_metadata == {}
