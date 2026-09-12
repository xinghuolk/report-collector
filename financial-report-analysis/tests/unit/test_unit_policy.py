from financial_report_analysis.unit_policy import UnitPolicy


def test_unit_policy_separates_compute_and_presentation_units() -> None:
    policy = UnitPolicy()

    normalized = policy.normalize_report_value(
        1000.0,
        raw_unit="RMB'000",
        raw_currency="CNY",
    )
    presented = policy.to_presentation(
        normalized.normalized_value,
        normalized.normalized_currency,
    )

    assert normalized.normalized_currency == "CNY"
    assert normalized.normalized_unit == "CNY"
    assert normalized.normalized_value == 1000000.0
    assert presented.presentation_unit == "CNY"
    assert presented.presentation_policy_name == "default_phase1"
