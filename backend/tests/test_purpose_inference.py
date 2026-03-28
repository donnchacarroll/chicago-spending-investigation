"""Tests for payment purpose inference."""

from backend.analysis.purpose_inference import infer_purpose


def test_infer_purpose_legal():
    """Legal vendor should return legal purpose."""
    result = infer_purpose("SMITH & JONES LAW FIRM", 50000.0)
    assert result["confidence"] in ("high", "medium", "low")
    assert "Legal" in result["purpose"] or "legal" in result["purpose"].lower()


def test_infer_purpose_pension():
    """Pension fund should return pension purpose."""
    result = infer_purpose("MUNICIPAL PENSION FUND", 1000000.0)
    assert "Pension" in result["purpose"] or "pension" in result["purpose"].lower()


def test_infer_purpose_returns_required_keys():
    """Result should contain purpose, confidence, reasoning, disclaimer."""
    result = infer_purpose("SOME VENDOR", 1000.0)
    for key in ("purpose", "confidence", "reasoning", "disclaimer"):
        assert key in result, f"Missing key: {key}"


def test_infer_purpose_unknown_vendor():
    """Unknown vendor should still return a result with a purpose string."""
    result = infer_purpose("XYZZY CORP", 500.0)
    assert isinstance(result["purpose"], str)
    assert len(result["purpose"]) > 0


def test_infer_purpose_confidence_valid_values():
    """Confidence should be one of the three valid strings."""
    result = infer_purpose("ACME INC", 1000.0)
    assert result["confidence"] in ("high", "medium", "low")


def test_infer_purpose_disclaimer_always_present():
    """Disclaimer should always be a non-empty string."""
    result = infer_purpose("ANY VENDOR", 999.0)
    assert isinstance(result["disclaimer"], str)
    assert len(result["disclaimer"]) > 0


def test_infer_purpose_reasoning_always_present():
    """Reasoning should always be a non-empty string."""
    result = infer_purpose("ANY VENDOR", 999.0)
    assert isinstance(result["reasoning"], str)
    assert len(result["reasoning"]) > 0


def test_infer_purpose_legal_high_confidence():
    """A clear law firm name should produce high confidence."""
    result = infer_purpose("LOEVY AND LOEVY ATTORNEYS", 75000.0)
    assert result["confidence"] == "high"


def test_infer_purpose_pension_high_confidence():
    """A clear pension fund name should produce high confidence."""
    result = infer_purpose("CHICAGO FIREMAN RETIREMENT FUND", 500000.0)
    assert result["confidence"] == "high"


def test_infer_purpose_with_spending_category():
    """If spending_category is provided (not uncategorized), it should be used."""
    result = infer_purpose(
        "SOME VENDOR", 10000.0,
        spending_category="Construction"
    )
    assert result["purpose"] == "Construction"
    assert result["confidence"] == "high"
