"""Vendor concentration analysis for Chicago spending payments.

Computes the Herfindahl-Hirschman Index (HHI) and top-vendor shares
per department to flag departments with highly concentrated spending.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd


def analyze_vendors(con) -> pd.DataFrame:
    """Analyze vendor concentration within departments.

    For each department, calculates:
    - HHI (Herfindahl-Hirschman Index) of vendor spending shares
    - Top vendor percentage share, top 3, and top 5
    Flags departments where HHI > 2500 (highly concentrated) or
    top vendor share > 50%.

    Args:
        con: A DuckDB connection with the payments table loaded.

    Returns:
        DataFrame of flagged concentrated departments with columns:
        department_name, hhi, top_vendor_name, top_vendor_pct,
        top3_pct, top5_pct, vendor_count, total_spend,
        flag_type, description, risk_score.
    """
    query = """
    WITH dept_vendor_totals AS (
        SELECT
            department_canonical AS department_name,
            vendor_name,
            SUM(amount) AS vendor_total
        FROM payments
        WHERE amount IS NOT NULL
          AND amount > 0
        GROUP BY department_canonical, vendor_name
    ),
    dept_totals AS (
        SELECT
            department_name,
            SUM(vendor_total) AS dept_total,
            COUNT(DISTINCT vendor_name) AS vendor_count
        FROM dept_vendor_totals
        GROUP BY department_name
        HAVING SUM(vendor_total) > 0
    ),
    vendor_shares AS (
        SELECT
            dv.department_name,
            dv.vendor_name,
            dv.vendor_total,
            dt.dept_total,
            dt.vendor_count,
            (dv.vendor_total / dt.dept_total * 100) AS share_pct,
            ROW_NUMBER() OVER (
                PARTITION BY dv.department_name
                ORDER BY dv.vendor_total DESC
            ) AS vendor_rank
        FROM dept_vendor_totals dv
        INNER JOIN dept_totals dt ON dv.department_name = dt.department_name
    ),
    hhi_calc AS (
        SELECT
            department_name,
            SUM(share_pct * share_pct) AS hhi
        FROM vendor_shares
        GROUP BY department_name
    ),
    top_vendors AS (
        SELECT
            department_name,
            MAX(CASE WHEN vendor_rank = 1 THEN vendor_name END) AS top_vendor_name,
            MAX(CASE WHEN vendor_rank = 1 THEN share_pct END) AS top_vendor_pct,
            SUM(CASE WHEN vendor_rank <= 3 THEN share_pct ELSE 0 END) AS top3_pct,
            SUM(CASE WHEN vendor_rank <= 5 THEN share_pct ELSE 0 END) AS top5_pct,
            MAX(vendor_count) AS vendor_count,
            MAX(dept_total) AS total_spend
        FROM vendor_shares
        GROUP BY department_name
    )
    SELECT
        tv.department_name,
        ROUND(h.hhi, 2) AS hhi,
        tv.top_vendor_name,
        ROUND(tv.top_vendor_pct, 2) AS top_vendor_pct,
        ROUND(tv.top3_pct, 2) AS top3_pct,
        ROUND(tv.top5_pct, 2) AS top5_pct,
        tv.vendor_count,
        ROUND(tv.total_spend, 2) AS total_spend
    FROM top_vendors tv
    INNER JOIN hhi_calc h ON tv.department_name = h.department_name
    WHERE h.hhi > 2500 OR tv.top_vendor_pct > 50
    ORDER BY h.hhi DESC
    """

    df = con.execute(query).fetchdf()

    result_cols = [
        "department_name", "hhi", "top_vendor_name", "top_vendor_pct",
        "top3_pct", "top5_pct", "vendor_count", "total_spend",
        "flag_type", "description", "risk_score",
    ]

    if df.empty:
        return pd.DataFrame(columns=result_cols)

    df["flag_type"] = "HIGH_CONCENTRATION"

    # Scale HHI to risk score: 2500 -> 0, 10000 -> 100
    # HHI max is 10000 (single vendor). 2500 is the "highly concentrated" threshold.
    df["risk_score"] = (
        (df["hhi"] - 2500) / (10000 - 2500) * 100
    ).clip(0, 100).round(1)

    # Boost score if top vendor share is also very high
    high_top_vendor = df["top_vendor_pct"] > 50
    df.loc[high_top_vendor, "risk_score"] = df.loc[high_top_vendor, "risk_score"].clip(
        lower=40.0
    )

    df["description"] = df.apply(
        lambda r: (
            f"{r['department_name']}: HHI={r['hhi']:.0f}, "
            f"top vendor {r['top_vendor_name']} has {r['top_vendor_pct']:.1f}% "
            f"of ${r['total_spend']:,.0f} total spend "
            f"({r['vendor_count']} vendors)"
        ),
        axis=1,
    )

    return df[result_cols]
