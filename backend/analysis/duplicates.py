"""Duplicate payment detection for Chicago spending payments.

Identifies exact and near-duplicate payments based on matching
vendor, amount, and date proximity.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from backend.config import DUPLICATE_NEAR_DAYS


def detect_duplicates(con) -> pd.DataFrame:
    """Detect exact and near-duplicate payments.

    Exact duplicates: same amount, vendor_name, and check_date but
    different voucher_number (non-aggregate only).

    Near duplicates: same amount and vendor_name within
    DUPLICATE_NEAR_DAYS days of each other.

    Args:
        con: A DuckDB connection with the payments table loaded.

    Returns:
        DataFrame of flagged duplicate payments with columns:
        voucher_number, vendor_name, amount, check_date,
        duplicate_voucher, flag_type, confidence, description, risk_score.
    """
    # Exact duplicates: same amount + vendor + date, different voucher
    exact_query = """
    SELECT
        a.voucher_number,
        a.vendor_name,
        a.amount,
        a.check_date,
        b.voucher_number AS duplicate_voucher
    FROM payments a
    INNER JOIN payments b
        ON a.vendor_name = b.vendor_name
       AND a.amount = b.amount
       AND a.check_date = b.check_date
       AND a.voucher_number < b.voucher_number
    WHERE a.is_annual_aggregate = false
      AND b.is_annual_aggregate = false
      AND a.amount IS NOT NULL
      AND a.check_date IS NOT NULL
    ORDER BY a.amount DESC
    """

    # Near duplicates: same amount + vendor within N days, excluding exact matches
    near_query = f"""
    SELECT
        a.voucher_number,
        a.vendor_name,
        a.amount,
        a.check_date,
        b.voucher_number AS duplicate_voucher
    FROM payments a
    INNER JOIN payments b
        ON a.vendor_name = b.vendor_name
       AND a.amount = b.amount
       AND a.voucher_number < b.voucher_number
       AND a.check_date != b.check_date
       AND ABS(DATEDIFF('day', a.check_date, b.check_date)) <= {DUPLICATE_NEAR_DAYS}
    WHERE a.is_annual_aggregate = false
      AND b.is_annual_aggregate = false
      AND a.amount IS NOT NULL
      AND a.check_date IS NOT NULL
    ORDER BY a.amount DESC
    """

    exact_df = con.execute(exact_query).fetchdf()
    near_df = con.execute(near_query).fetchdf()

    empty_cols = [
        "voucher_number", "vendor_name", "amount", "check_date",
        "duplicate_voucher", "flag_type", "confidence", "description",
        "risk_score",
    ]

    if exact_df.empty and near_df.empty:
        return pd.DataFrame(columns=empty_cols)

    # Tag exact duplicates
    if not exact_df.empty:
        exact_df["flag_type"] = "DUPLICATE_PAYMENT"
        exact_df["confidence"] = "high"
        exact_df["risk_score"] = 85.0
        exact_df["description"] = exact_df.apply(
            lambda r: (
                f"Exact duplicate: ${r['amount']:,.2f} to {r['vendor_name']} "
                f"on {r['check_date']} (vouchers {r['voucher_number']} "
                f"and {r['duplicate_voucher']})"
            ),
            axis=1,
        )

    # Tag near duplicates
    if not near_df.empty:
        near_df["flag_type"] = "DUPLICATE_PAYMENT"
        near_df["confidence"] = "medium"
        near_df["risk_score"] = 60.0
        near_df["description"] = near_df.apply(
            lambda r: (
                f"Near duplicate: ${r['amount']:,.2f} to {r['vendor_name']} "
                f"within {DUPLICATE_NEAR_DAYS} days "
                f"(vouchers {r['voucher_number']} and {r['duplicate_voucher']})"
            ),
            axis=1,
        )

    result = pd.concat([exact_df, near_df], ignore_index=True)

    return result[empty_cols]
