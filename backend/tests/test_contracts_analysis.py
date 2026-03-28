"""Tests for contract compliance analysis."""

import pandas as pd
from backend.analysis.contracts import analyze_contracts


def test_contract_analysis_returns_results(test_db):
    """Should flag at least one contract issue."""
    results = analyze_contracts(test_db)
    assert len(results) > 0


def test_contract_overspend_detected(test_db):
    """Contract CT-003 should be flagged as overspent."""
    results = analyze_contracts(test_db)
    overspend_flags = results[results["flag_type"] == "CONTRACT_OVERSPEND"]
    assert len(overspend_flags) > 0, "Should detect at least one CONTRACT_OVERSPEND"
    vendors = overspend_flags["vendor_name"].tolist()
    assert "CONTRACT_VENDOR_C" in vendors


def test_contract_flag_types_valid(test_db):
    """Flag types should be CONTRACT_OVERSPEND or NO_CONTRACT_HIGH_VALUE."""
    results = analyze_contracts(test_db)
    valid_types = {"CONTRACT_OVERSPEND", "NO_CONTRACT_HIGH_VALUE"}
    assert set(results["flag_type"].unique()).issubset(valid_types)


def test_contract_risk_score_positive(test_db):
    """Flagged contracts should have risk_score > 0."""
    results = analyze_contracts(test_db)
    assert (results["risk_score"] > 0).all()


def test_no_contract_high_value_detected(test_db):
    """Direct voucher payments above $25,000 should be flagged."""
    results = analyze_contracts(test_db)
    no_contract_flags = results[results["flag_type"] == "NO_CONTRACT_HIGH_VALUE"]
    assert len(no_contract_flags) > 0, "Should detect NO_CONTRACT_HIGH_VALUE payments"
    # CHICAGO PENSION FUND payment of $500,000 should be flagged
    vendors = no_contract_flags["vendor_name"].tolist()
    assert "CHICAGO PENSION FUND" in vendors


def test_contract_returns_dataframe(test_db):
    """analyze_contracts should return a DataFrame."""
    results = analyze_contracts(test_db)
    assert isinstance(results, pd.DataFrame)


def test_contract_has_required_columns(test_db):
    """Result should have all expected columns."""
    results = analyze_contracts(test_db)
    expected = [
        "contract_number", "vendor_name", "department_name", "award_amount",
        "total_paid", "overspend_ratio", "amount", "flag_type", "description",
        "risk_score",
    ]
    for col in expected:
        assert col in results.columns, f"Missing column: {col}"


def test_contract_risk_score_bounded(test_db):
    """Risk scores should be between 0 and 100 inclusive."""
    results = analyze_contracts(test_db)
    assert (results["risk_score"] >= 0).all()
    assert (results["risk_score"] <= 100).all()
