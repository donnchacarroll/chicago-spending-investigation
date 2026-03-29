"""Tests for composite risk scoring."""


def test_alerts_table_populated(test_db):
    """compute_risk_scores should create a non-empty alerts table."""
    count = test_db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    assert count > 0, "alerts table should have rows after scoring"


def test_alerts_have_required_columns(test_db):
    """alerts table should have expected columns."""
    cols = [c[0] for c in test_db.execute("DESCRIBE alerts").fetchall()]
    for expected in ["flag_type", "description", "risk_score", "vendor_name"]:
        assert expected in cols, f"Missing column: {expected}"


def test_payment_risk_scores_populated(test_db):
    """payment_risk_scores should have entries for flagged payments."""
    count = test_db.execute("SELECT COUNT(*) FROM payment_risk_scores").fetchone()[0]
    assert count > 0


def test_vendor_risk_scores_populated(test_db):
    """vendor_risk_scores should have entries for flagged vendors."""
    count = test_db.execute("SELECT COUNT(*) FROM vendor_risk_scores").fetchone()[0]
    assert count > 0


def test_risk_scores_in_valid_range(test_db):
    """Composite scores should be non-negative."""
    rows = test_db.execute(
        "SELECT composite_score FROM payment_risk_scores"
    ).fetchall()
    for (score,) in rows:
        assert score >= 0, f"Negative score: {score}"


def test_alerts_flag_types_are_known(test_db):
    """All flag_type values in alerts should be from the known set."""
    known_types = {
        "OUTLIER_AMOUNT", "DUPLICATE_PAYMENT", "SPLIT_PAYMENT",
        "CONTRACT_OVERSPEND", "NO_CONTRACT_HIGH_VALUE", "HIGH_CONCENTRATION",
    }
    rows = test_db.execute("SELECT DISTINCT flag_type FROM alerts").fetchall()
    for (ft,) in rows:
        assert ft in known_types, f"Unknown flag_type: {ft}"


def test_department_risk_scores_table_exists(test_db):
    """department_risk_scores table should exist after scoring."""
    count = test_db.execute(
        "SELECT COUNT(*) FROM department_risk_scores"
    ).fetchone()[0]
    # Table may be empty if no dept-level flags, but should exist
    assert count >= 0


def test_alerts_vendor_name_populated(test_db):
    """Most alert rows should have a vendor_name."""
    rows = test_db.execute(
        "SELECT COUNT(*) FROM alerts WHERE vendor_name IS NOT NULL"
    ).fetchone()[0]
    assert rows > 0, "At least some alerts should have a vendor_name"


def test_vendor_risk_scores_excludes_intergovernmental(test_db):
    """Intergovernmental vendors should not have risk scores."""
    rows = test_db.execute(
        "SELECT vendor_name FROM vendor_risk_scores"
    ).fetchall()
    vendor_names = [r[0] for r in rows]
    assert "COOK COUNTY TREASURER" not in vendor_names
    assert "STATE OF ILLINOIS TREASURERS OFFICE" not in vendor_names
    assert "CHICAGO TRANSIT AUTHORITY" not in vendor_names


def test_vendor_risk_scores_composite_bounded(test_db):
    """Vendor composite scores should be between 0 and 100."""
    rows = test_db.execute(
        "SELECT composite_score FROM vendor_risk_scores"
    ).fetchall()
    for (score,) in rows:
        assert 0 <= score <= 100, f"Score out of range: {score}"
