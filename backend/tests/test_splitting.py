"""Tests for payment splitting detection."""

import pandas as pd
from backend.analysis.splitting import detect_splitting


def test_splitting_detects_pattern(test_db):
    """Multiple payments just under threshold from same vendor should be flagged."""
    results = detect_splitting(test_db)
    assert len(results) > 0, "Should detect at least one splitting pattern"
    flagged_vendors = results["vendor_name"].tolist()
    assert "SPLIT_SERVICES_INC" in flagged_vendors


def test_splitting_flag_type(test_db):
    """Flagged rows should have flag_type SPLIT_PAYMENT."""
    results = detect_splitting(test_db)
    assert (results["flag_type"] == "SPLIT_PAYMENT").all()


def test_splitting_captures_count(test_db):
    """Splitting detection should report the number of split payments."""
    results = detect_splitting(test_db)
    split_rows = results[results["vendor_name"] == "SPLIT_SERVICES_INC"]
    assert len(split_rows) > 0
    # At least one window should show 3+ payments
    assert split_rows["payment_count"].max() >= 3


def test_splitting_risk_score_positive(test_db):
    """Flagged splits should have risk_score > 0."""
    results = detect_splitting(test_db)
    assert (results["risk_score"] > 0).all()


def test_splitting_returns_dataframe(test_db):
    """detect_splitting should return a DataFrame."""
    results = detect_splitting(test_db)
    assert isinstance(results, pd.DataFrame)


def test_splitting_has_required_columns(test_db):
    """Result should have all expected columns."""
    results = detect_splitting(test_db)
    expected = [
        "vendor_name", "department_name", "threshold", "payment_count",
        "total_amount", "date_range", "flag_type", "description", "risk_score",
    ]
    for col in expected:
        assert col in results.columns, f"Missing column: {col}"


def test_splitting_total_exceeds_threshold(test_db):
    """Total amount for each split pattern should exceed the threshold."""
    results = detect_splitting(test_db)
    for _, row in results.iterrows():
        assert row["total_amount"] > row["threshold"], (
            f"total_amount {row['total_amount']} should exceed threshold {row['threshold']}"
        )


def test_splitting_risk_score_bounded(test_db):
    """Risk scores should be between 0 and 100 inclusive."""
    results = detect_splitting(test_db)
    assert (results["risk_score"] >= 0).all()
    assert (results["risk_score"] <= 100).all()
