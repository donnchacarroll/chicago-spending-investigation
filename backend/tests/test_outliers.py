"""Tests for outlier detection (Z-score based anomaly flagging)."""

import pandas as pd
import pytest
from backend.analysis.outliers import detect_outliers


def test_outlier_returns_dataframe(test_db):
    """detect_outliers should return a DataFrame (empty or populated)."""
    results = detect_outliers(test_db)
    assert isinstance(results, pd.DataFrame)


def test_outlier_has_required_columns(test_db):
    """Result DataFrame should have the expected output columns."""
    results = detect_outliers(test_db)
    expected_cols = [
        "voucher_number", "vendor_name", "department_name", "amount",
        "z_score", "flag_type", "description", "risk_score",
    ]
    for col in expected_cols:
        assert col in results.columns, f"Missing column: {col}"


def test_outlier_flag_type_is_correct(test_db):
    """Any flagged rows should have flag_type OUTLIER_AMOUNT."""
    results = detect_outliers(test_db)
    if len(results) > 0:
        assert (results["flag_type"] == "OUTLIER_AMOUNT").all()


def test_outlier_has_positive_risk_score(test_db):
    """Any flagged outliers should have risk_score > 0."""
    results = detect_outliers(test_db)
    if len(results) > 0:
        assert (results["risk_score"] > 0).all()


def test_outlier_risk_score_bounded(test_db):
    """Risk scores should be between 0 and 100 inclusive."""
    results = detect_outliers(test_db)
    if len(results) > 0:
        assert (results["risk_score"] >= 0).all()
        assert (results["risk_score"] <= 100).all()


def test_outlier_z_score_exceeds_threshold(test_db):
    """Flagged payments should all have |z_score| > 3.0 (OUTLIER_ZSCORE_THRESHOLD)."""
    from backend.config import OUTLIER_ZSCORE_THRESHOLD
    results = detect_outliers(test_db)
    if len(results) > 0:
        assert (results["z_score"].abs() > OUTLIER_ZSCORE_THRESHOLD).all()


def test_outlier_description_populated(test_db):
    """Each flagged row should have a non-empty description."""
    results = detect_outliers(test_db)
    if len(results) > 0:
        assert results["description"].notna().all()
        assert (results["description"].str.len() > 0).all()
