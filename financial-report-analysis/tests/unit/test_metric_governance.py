from financial_report_analysis.registries import (
    CUSTOM_NAMESPACE,
    METRIC_GOVERNANCE_EXTENSION_KEY,
    PROVISIONAL_STATUS,
    STANDARD_NAMESPACE,
    STANDARD_STATUS,
    MetricRegistry,
    MetricRegistryEntry,
    automatic_governance_metadata,
    governance_metadata_from_registry_entry,
    is_auto_analysis_allowed,
    is_provisional_custom_metric,
    standard_governance_metadata,
)


def test_standard_registry_entry_metadata_allows_auto_analysis() -> None:
    registry = MetricRegistry(standard_metrics={"revenue": ["Revenue"]})

    entry = registry.resolve_metric(
        raw_label="Revenue",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="consumer",
        parent_metric_id=None,
    )
    metadata = governance_metadata_from_registry_entry(entry)

    assert metadata == {
        "registry_status": STANDARD_STATUS,
        "metric_namespace": STANDARD_NAMESPACE,
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": "standard_metric",
    }
    assert is_auto_analysis_allowed({METRIC_GOVERNANCE_EXTENSION_KEY: metadata}) is True


def test_custom_registry_entry_metadata_is_provisional_and_blocks_auto_analysis() -> None:
    registry = MetricRegistry(standard_metrics={"revenue": ["Revenue"]})

    entry = registry.resolve_metric(
        raw_label="Other income",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="consumer",
        parent_metric_id="revenue",
    )
    metadata = governance_metadata_from_registry_entry(entry)
    extensions = {METRIC_GOVERNANCE_EXTENSION_KEY: metadata}

    assert metadata == {
        "registry_status": PROVISIONAL_STATUS,
        "metric_namespace": CUSTOM_NAMESPACE,
        "review_required": True,
        "auto_analysis_allowed": False,
        "governance_reason": "provisional_custom_metric",
    }
    assert is_auto_analysis_allowed(extensions) is False
    assert is_provisional_custom_metric(extensions) is True


def test_provisional_registry_entry_metadata_is_custom_review_only() -> None:
    entry = MetricRegistryEntry(
        metric_id="revenue",
        raw_label="Revenue",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="consumer",
        parent_metric_id=None,
        is_custom=False,
        registry_status=PROVISIONAL_STATUS,
    )
    metadata = governance_metadata_from_registry_entry(entry)
    extensions = {METRIC_GOVERNANCE_EXTENSION_KEY: metadata}

    assert metadata == {
        "registry_status": PROVISIONAL_STATUS,
        "metric_namespace": CUSTOM_NAMESPACE,
        "review_required": True,
        "auto_analysis_allowed": False,
        "governance_reason": "provisional_custom_metric",
    }
    assert is_auto_analysis_allowed(extensions) is False
    assert is_provisional_custom_metric(extensions) is True


def test_unknown_registry_status_metadata_is_custom_review_only() -> None:
    entry = MetricRegistryEntry(
        metric_id="revenue",
        raw_label="Revenue",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="consumer",
        parent_metric_id=None,
        is_custom=False,
        registry_status="review_required",
    )
    metadata = governance_metadata_from_registry_entry(entry)
    extensions = {METRIC_GOVERNANCE_EXTENSION_KEY: metadata}

    assert metadata == {
        "registry_status": PROVISIONAL_STATUS,
        "metric_namespace": CUSTOM_NAMESPACE,
        "review_required": True,
        "auto_analysis_allowed": False,
        "governance_reason": "provisional_custom_metric",
    }
    assert is_auto_analysis_allowed(extensions) is False
    assert is_provisional_custom_metric(extensions) is True


def test_supported_metric_mapping_metadata_is_standard_and_allows_auto_analysis() -> None:
    metadata = standard_governance_metadata(reason="supported_metric_mapping")

    assert metadata == {
        "registry_status": STANDARD_STATUS,
        "metric_namespace": STANDARD_NAMESPACE,
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": "supported_metric_mapping",
    }
    assert is_auto_analysis_allowed({METRIC_GOVERNANCE_EXTENSION_KEY: metadata}) is True


def test_missing_or_malformed_governance_extension_is_conservative() -> None:
    assert automatic_governance_metadata({}) == {}
    assert is_auto_analysis_allowed({}) is False
    assert is_provisional_custom_metric({}) is False

    malformed_extensions = {
        METRIC_GOVERNANCE_EXTENSION_KEY: "standard",
    }

    assert automatic_governance_metadata(malformed_extensions) == {}
    assert is_auto_analysis_allowed(malformed_extensions) is False
    assert is_provisional_custom_metric(malformed_extensions) is False
