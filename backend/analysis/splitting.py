"""Payment splitting detection for Chicago spending payments.

Identifies patterns where payments to the same vendor from the same
department are clustered just below a threshold, suggesting deliberate
splitting to avoid approval limits.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from backend.config import SPLITTING_THRESHOLDS, SPLITTING_WINDOW_DAYS


def detect_splitting(con) -> pd.DataFrame:
    """Detect potential payment splitting patterns.

    For each threshold in SPLITTING_THRESHOLDS, finds cases where the same
    vendor + department has multiple payments within a SPLITTING_WINDOW_DAYS
    window where individual amounts are below the threshold (but above 70%
    of it) and the sum exceeds the threshold.

    Args:
        con: A DuckDB connection with the payments table loaded.

    Returns:
        DataFrame of flagged splitting patterns with columns:
        vendor_name, department_name, threshold, payment_count,
        total_amount, date_range, flag_type, description, risk_score.
    """
    all_results = []

    for threshold in SPLITTING_THRESHOLDS:
        lower_bound = threshold * 0.7
        query = f"""
        WITH eligible_payments AS (
            SELECT
                vendor_name,
                department_canonical AS department_name,
                amount,
                check_date,
                voucher_number
            FROM payments
            WHERE is_annual_aggregate = false
              AND amount IS NOT NULL
              AND check_date IS NOT NULL
              AND amount < {threshold}
              AND amount >= {lower_bound}
        ),
        windowed AS (
            SELECT
                a.vendor_name,
                a.department_name,
                a.voucher_number,
                a.amount,
                a.check_date,
                COUNT(*) OVER w AS payment_count,
                SUM(a.amount) OVER w AS total_amount,
                MIN(a.check_date) OVER w AS window_start,
                MAX(a.check_date) OVER w AS window_end
            FROM eligible_payments a
            WINDOW w AS (
                PARTITION BY a.vendor_name, a.department_name
                ORDER BY a.check_date
                RANGE BETWEEN INTERVAL '{SPLITTING_WINDOW_DAYS}' DAY PRECEDING
                          AND CURRENT ROW
            )
        ),
        flagged AS (
            SELECT DISTINCT
                vendor_name,
                department_name,
                payment_count,
                total_amount,
                window_start,
                window_end
            FROM windowed
            WHERE payment_count >= 2
              AND total_amount > {threshold}
        )
        SELECT
            vendor_name,
            department_name,
            {threshold} AS threshold,
            payment_count,
            ROUND(total_amount, 2) AS total_amount,
            CONCAT(
                CAST(window_start AS VARCHAR), ' to ',
                CAST(window_end AS VARCHAR)
            ) AS date_range
        FROM flagged
        ORDER BY total_amount DESC
        """
        df = con.execute(query).fetchdf()
        if not df.empty:
            all_results.append(df)

    result_cols = [
        "vendor_name", "department_name", "threshold", "payment_count",
        "total_amount", "date_range", "flag_type", "description", "risk_score",
    ]

    if not all_results:
        return pd.DataFrame(columns=result_cols)

    result = pd.concat(all_results, ignore_index=True)

    result["flag_type"] = "SPLIT_PAYMENT"

    # Risk score: higher for more payments and higher ratio of total to threshold
    result["risk_score"] = result.apply(
        lambda r: min(
            100.0,
            (
                30  # base score for any split detection
                + (r["payment_count"] - 2) * 10  # more payments = more suspicious
                + (r["total_amount"] / r["threshold"] - 1) * 40  # how much over threshold
            ),
        ),
        axis=1,
    ).clip(0, 100).round(1)

    result["description"] = result.apply(
        lambda r: (
            f"{r['vendor_name']} received {r['payment_count']} payments "
            f"totaling ${r['total_amount']:,.2f} from {r['department_name']} "
            f"within {SPLITTING_WINDOW_DAYS} days, each just below "
            f"${r['threshold']:,} threshold ({r['date_range']})"
        ),
        axis=1,
    )

    return result[result_cols]
