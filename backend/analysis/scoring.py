"""Composite risk scoring for Chicago spending investigation.

Aggregates flags from all analysis modules into per-payment,
per-vendor, and per-department risk scores, and stores results
in DuckDB tables.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from backend.config import RISK_WEIGHTS

# Map flag_type to the weight key used in RISK_WEIGHTS
_FLAG_WEIGHT_MAP = {
    "OUTLIER_AMOUNT": "outlier",
    "DUPLICATE_PAYMENT": "duplicate",
    "SPLIT_PAYMENT": "splitting",
    "CONTRACT_OVERSPEND": "contract_overspend",
    "NO_CONTRACT_HIGH_VALUE": "contract_overspend",
    "HIGH_CONCENTRATION": "vendor_concentration",
}


def compute_risk_scores(con, all_flags_df: pd.DataFrame) -> dict:
    """Compute composite risk scores from all analysis flags.

    Takes the combined DataFrame of flags from all modules and computes
    weighted composite scores for payments, vendors, and departments.
    Stores results in DuckDB tables and an alerts table.

    Args:
        con: A DuckDB connection.
        all_flags_df: Combined DataFrame from all analysis modules.
            Must contain at minimum: flag_type, risk_score.
            May also contain: voucher_number, vendor_name, department_name.

    Returns:
        dict with summary statistics including counts and score distributions.
    """
    if all_flags_df.empty:
        # Create empty tables for consistency
        con.execute("""
            CREATE OR REPLACE TABLE alerts (
                flag_type VARCHAR,
                description VARCHAR,
                risk_score DOUBLE,
                vendor_name VARCHAR,
                department_name VARCHAR,
                voucher_number VARCHAR,
                amount DOUBLE
            )
        """)
        con.execute("""
            CREATE OR REPLACE TABLE payment_risk_scores (
                voucher_number VARCHAR,
                composite_score DOUBLE,
                flag_count INTEGER
            )
        """)
        con.execute("""
            CREATE OR REPLACE TABLE vendor_risk_scores (
                vendor_name VARCHAR,
                composite_score DOUBLE,
                flag_count INTEGER
            )
        """)
        con.execute("""
            CREATE OR REPLACE TABLE department_risk_scores (
                department_name VARCHAR,
                composite_score DOUBLE,
                flag_count INTEGER
            )
        """)
        return {
            "total_flags": 0,
            "payments_scored": 0,
            "vendors_scored": 0,
            "departments_scored": 0,
        }

    # Apply weights to risk scores based on flag type
    all_flags_df = all_flags_df.copy()
    all_flags_df["weight"] = all_flags_df["flag_type"].map(
        lambda ft: RISK_WEIGHTS.get(_FLAG_WEIGHT_MAP.get(ft, ""), 0.15)
    )
    all_flags_df["weighted_score"] = all_flags_df["risk_score"] * all_flags_df["weight"]

    # Ensure expected columns exist (fill with None if missing)
    for col in ["voucher_number", "vendor_name", "department_name", "amount", "description"]:
        if col not in all_flags_df.columns:
            all_flags_df[col] = None

    # Store all flags in the alerts table
    alerts_df = all_flags_df[[
        "flag_type", "description", "risk_score", "vendor_name",
        "department_name", "voucher_number", "amount",
    ]].copy()
    con.execute("CREATE OR REPLACE TABLE alerts AS SELECT * FROM alerts_df")

    # --- Payment-level scores (by voucher_number) ---
    payment_flags = all_flags_df.dropna(subset=["voucher_number"])
    if not payment_flags.empty:
        payment_scores = (
            payment_flags
            .groupby("voucher_number")
            .agg(
                composite_score=("weighted_score", "sum"),
                flag_count=("flag_type", "count"),
            )
            .reset_index()
        )
        # Normalize composite score: cap at 100
        payment_scores["composite_score"] = (
            payment_scores["composite_score"].clip(0, 100).round(1)
        )
        con.execute(
            "CREATE OR REPLACE TABLE payment_risk_scores AS SELECT * FROM payment_scores"
        )
    else:
        con.execute("""
            CREATE OR REPLACE TABLE payment_risk_scores (
                voucher_number VARCHAR,
                composite_score DOUBLE,
                flag_count INTEGER
            )
        """)
    payments_scored = len(payment_scores) if not payment_flags.empty else 0

    # --- Vendor-level scores ---
    vendor_flags = all_flags_df.dropna(subset=["vendor_name"])
    if not vendor_flags.empty:
        vendor_scores = (
            vendor_flags
            .groupby("vendor_name")
            .agg(
                composite_score=("weighted_score", "mean"),
                flag_count=("flag_type", "count"),
            )
            .reset_index()
        )
        vendor_scores["composite_score"] = (
            vendor_scores["composite_score"].clip(0, 100).round(1)
        )
        con.execute(
            "CREATE OR REPLACE TABLE vendor_risk_scores AS SELECT * FROM vendor_scores"
        )
    else:
        con.execute("""
            CREATE OR REPLACE TABLE vendor_risk_scores (
                vendor_name VARCHAR,
                composite_score DOUBLE,
                flag_count INTEGER
            )
        """)
    # Remove intergovernmental vendors from risk scores
    try:
        con.execute("""
            DELETE FROM vendor_risk_scores
            WHERE vendor_name IN (
                SELECT DISTINCT vendor_name FROM payment_contract_joined
                WHERE is_intergovernmental = true
            )
        """)
    except Exception:
        pass  # Column may not exist in older databases

    vendors_scored = len(vendor_scores) if not vendor_flags.empty else 0

    # --- Department-level scores ---
    dept_flags = all_flags_df.dropna(subset=["department_name"])
    if not dept_flags.empty:
        dept_scores = (
            dept_flags
            .groupby("department_name")
            .agg(
                composite_score=("weighted_score", "mean"),
                flag_count=("flag_type", "count"),
            )
            .reset_index()
        )
        dept_scores["composite_score"] = (
            dept_scores["composite_score"].clip(0, 100).round(1)
        )
        con.execute(
            "CREATE OR REPLACE TABLE department_risk_scores AS SELECT * FROM dept_scores"
        )
    else:
        con.execute("""
            CREATE OR REPLACE TABLE department_risk_scores (
                department_name VARCHAR,
                composite_score DOUBLE,
                flag_count INTEGER
            )
        """)
    depts_scored = len(dept_scores) if not dept_flags.empty else 0

    return {
        "total_flags": len(all_flags_df),
        "payments_scored": payments_scored,
        "vendors_scored": vendors_scored,
        "departments_scored": depts_scored,
        "flag_type_counts": all_flags_df["flag_type"].value_counts().to_dict(),
        "avg_risk_score": round(all_flags_df["risk_score"].mean(), 1),
        "max_risk_score": round(all_flags_df["risk_score"].max(), 1),
    }
