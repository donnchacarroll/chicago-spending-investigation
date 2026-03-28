"""Tests for duplicate payment detection."""

import pandas as pd
from backend.analysis.duplicates import detect_duplicates


def test_duplicate_finds_exact_match(test_db):
    """Two payments with same vendor, amount, date should be flagged."""
    results = detect_duplicates(test_db)
    assert len(results) > 0, "Should find at least one duplicate"
    flagged_vendors = results["vendor_name"].tolist()
    assert "DUPLICATE_CORP" in flagged_vendors


def test_duplicate_flag_type(test_db):
    """Flagged duplicates should have flag_type DUPLICATE_PAYMENT."""
    results = detect_duplicates(test_db)
    assert (results["flag_type"] == "DUPLICATE_PAYMENT").all()


def test_duplicate_has_matching_voucher(test_db):
    """Each flagged duplicate should reference the other voucher number."""
    results = detect_duplicates(test_db)
    dup_rows = results[results["vendor_name"] == "DUPLICATE_CORP"]
    assert len(dup_rows) >= 1
    assert dup_rows["duplicate_voucher"].notna().all()


def test_duplicate_risk_score_positive(test_db):
    """Flagged duplicates should have risk_score > 0."""
    results = detect_duplicates(test_db)
    assert (results["risk_score"] > 0).all()


def test_duplicate_exact_has_high_confidence(test_db):
    """Exact duplicates (same date) should have confidence 'high'."""
    results = detect_duplicates(test_db)
    dup_rows = results[results["vendor_name"] == "DUPLICATE_CORP"]
    assert len(dup_rows) >= 1
    assert (dup_rows["confidence"] == "high").all()


def test_duplicate_exact_risk_score(test_db):
    """Exact duplicate rows should have risk_score of 85.0."""
    results = detect_duplicates(test_db)
    exact_rows = results[results["confidence"] == "high"]
    assert len(exact_rows) >= 1
    assert (exact_rows["risk_score"] == 85.0).all()


def test_duplicate_returns_dataframe(test_db):
    """detect_duplicates should return a DataFrame."""
    results = detect_duplicates(test_db)
    assert isinstance(results, pd.DataFrame)


def test_duplicate_has_required_columns(test_db):
    """Result should have all expected columns."""
    results = detect_duplicates(test_db)
    expected = [
        "voucher_number", "vendor_name", "amount", "check_date",
        "duplicate_voucher", "flag_type", "confidence", "description", "risk_score",
    ]
    for col in expected:
        assert col in results.columns, f"Missing column: {col}"
