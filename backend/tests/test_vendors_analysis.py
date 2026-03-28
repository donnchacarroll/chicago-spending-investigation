"""Tests for vendor concentration analysis (HHI)."""

import pandas as pd
from backend.analysis.vendors import analyze_vendors


def test_vendor_analysis_returns_results(test_db):
    """Should return concentration metrics for departments."""
    results = analyze_vendors(test_db)
    assert len(results) > 0


def test_vendor_hhi_in_valid_range(test_db):
    """HHI should be between 0 and 10000."""
    results = analyze_vendors(test_db)
    assert (results["hhi"] >= 0).all()
    assert (results["hhi"] <= 10000).all()


def test_vendor_flag_type(test_db):
    """Flagged departments should have flag_type HIGH_CONCENTRATION."""
    results = analyze_vendors(test_db)
    if len(results) > 0:
        assert (results["flag_type"] == "HIGH_CONCENTRATION").all()


def test_vendor_risk_score_positive(test_db):
    """Flagged rows should have risk_score > 0."""
    results = analyze_vendors(test_db)
    if len(results) > 0:
        assert (results["risk_score"] > 0).all()


def test_vendor_returns_dataframe(test_db):
    """analyze_vendors should return a DataFrame."""
    results = analyze_vendors(test_db)
    assert isinstance(results, pd.DataFrame)


def test_vendor_has_required_columns(test_db):
    """Result should have all expected columns."""
    results = analyze_vendors(test_db)
    expected = [
        "department_name", "hhi", "top_vendor_name", "top_vendor_pct",
        "top3_pct", "top5_pct", "vendor_count", "total_spend",
        "flag_type", "description", "risk_score",
    ]
    for col in expected:
        assert col in results.columns, f"Missing column: {col}"


def test_vendor_finance_dept_flagged(test_db):
    """FINANCE department should be flagged due to high vendor concentration."""
    results = analyze_vendors(test_db)
    dept_names = results["department_name"].tolist()
    assert "FINANCE" in dept_names, "FINANCE should be flagged for high concentration"


def test_vendor_concentration_threshold(test_db):
    """All flagged departments should have HHI > 2500 or top_vendor_pct > 50."""
    results = analyze_vendors(test_db)
    for _, row in results.iterrows():
        assert row["hhi"] > 2500 or row["top_vendor_pct"] > 50, (
            f"Department {row['department_name']} shouldn't be flagged: "
            f"HHI={row['hhi']}, top_vendor_pct={row['top_vendor_pct']}"
        )
