"""Outlier detection for Chicago spending payments.

Flags individual payments whose amounts are statistical outliers
within their (department, vendor) group using z-score analysis.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from backend.config import OUTLIER_ZSCORE_THRESHOLD, MIN_PAYMENTS_FOR_ZSCORE


def detect_outliers(con) -> pd.DataFrame:
    """Detect payments with outlier amounts within each (department, vendor) group.

    For each (department_canonical, vendor_name) pair with at least
    MIN_PAYMENTS_FOR_ZSCORE non-aggregate payments, computes z-scores and
    flags any payment whose |z-score| exceeds OUTLIER_ZSCORE_THRESHOLD.

    Args:
        con: A DuckDB connection with the payments table loaded.

    Returns:
        DataFrame of flagged outlier payments with columns:
        voucher_number, vendor_name, department_name, amount,
        z_score, flag_type, description, risk_score.
    """
    query = f"""
    WITH group_stats AS (
        SELECT
            department_canonical,
            vendor_name,
            AVG(amount) AS mean_amount,
            STDDEV_SAMP(amount) AS std_amount,
            COUNT(*) AS payment_count,
            MIN(amount) AS min_amount,
            MAX(amount) AS max_amount,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) AS median_amount
        FROM payments
        WHERE is_annual_aggregate = false
          AND amount IS NOT NULL
        GROUP BY department_canonical, vendor_name
        HAVING COUNT(*) >= {MIN_PAYMENTS_FOR_ZSCORE}
           AND STDDEV_SAMP(amount) > 0
    ),
    scored AS (
        SELECT
            p.voucher_number,
            p.vendor_name,
            p.department_canonical AS department_name,
            p.amount,
            p.check_date,
            (p.amount - gs.mean_amount) / gs.std_amount AS z_score,
            gs.mean_amount AS group_mean,
            gs.std_amount AS group_std,
            gs.payment_count AS group_count,
            gs.min_amount AS group_min,
            gs.max_amount AS group_max,
            gs.median_amount AS group_median
        FROM payments p
        INNER JOIN group_stats gs
            ON p.department_canonical = gs.department_canonical
           AND p.vendor_name = gs.vendor_name
        WHERE p.is_annual_aggregate = false
          AND p.amount IS NOT NULL
    )
    SELECT
        voucher_number,
        vendor_name,
        department_name,
        amount,
        check_date,
        ROUND(z_score, 4) AS z_score,
        ROUND(group_mean, 2) AS group_mean,
        ROUND(group_std, 2) AS group_std,
        group_count,
        ROUND(group_min, 2) AS group_min,
        ROUND(group_max, 2) AS group_max,
        ROUND(group_median, 2) AS group_median
    FROM scored
    WHERE ABS(z_score) > {OUTLIER_ZSCORE_THRESHOLD}
    ORDER BY ABS(z_score) DESC
    """

    df = con.execute(query).fetchdf()

    result_cols = [
        "voucher_number", "vendor_name", "department_name", "amount",
        "z_score", "group_mean", "group_std", "group_count",
        "group_min", "group_max", "group_median",
        "flag_type", "description", "risk_score",
    ]

    if df.empty:
        return pd.DataFrame(columns=result_cols)

    df["flag_type"] = "OUTLIER_AMOUNT"

    # Scale z-score to 0-100 risk, capping at z=6
    # z=THRESHOLD -> 0, z=6 -> 100
    z_range = 6.0 - OUTLIER_ZSCORE_THRESHOLD
    df["risk_score"] = (
        (df["z_score"].abs() - OUTLIER_ZSCORE_THRESHOLD) / z_range * 100
    ).clip(0, 100).round(1)

    df["description"] = df.apply(
        lambda r: (
            f"Payment of ${r['amount']:,.2f} to {r['vendor_name']} "
            f"is {r['z_score']:.1f}x standard deviations from the norm. "
            f"Typical payments to this vendor: "
            f"${r['group_median']:,.2f} median, "
            f"${r['group_mean']:,.2f} avg "
            f"(range ${r['group_min']:,.2f}–${r['group_max']:,.2f} "
            f"across {r['group_count']} payments). "
            f"This payment is {r['amount'] / r['group_mean']:.1f}x the average."
        ),
        axis=1,
    )

    return df[result_cols]
