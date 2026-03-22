"""CSV cleaning pipeline for Chicago payments data."""

import re

import pandas as pd

from backend.config import CSV_PATH, DATA_PROCESSED


# Static mapping for department name canonicalization
DEPARTMENT_NAME_MAP = {
    "DEPT OF FLEET MGMT": "DEPARTMENT OF FLEET AND FACILITY MANAGEMENT",
    "DEPT OF FLEET & FACILITY MGMT": "DEPARTMENT OF FLEET AND FACILITY MANAGEMENT",
    "FLEET AND FACILITY MANAGEMENT": "DEPARTMENT OF FLEET AND FACILITY MANAGEMENT",
    "DEPT OF GENERAL SERVICES": "DEPARTMENT OF GENERAL SERVICES",
    "GENERAL SERVICES": "DEPARTMENT OF GENERAL SERVICES",
    "DEPT OF ASSETS INFORMATION AND SERVICES": "DEPARTMENT OF ASSETS, INFORMATION AND SERVICES",
    "DEPT OF ASSETS, INFORMATION AND SERVICES": "DEPARTMENT OF ASSETS, INFORMATION AND SERVICES",
    "ASSETS INFORMATION AND SERVICES": "DEPARTMENT OF ASSETS, INFORMATION AND SERVICES",
    "DEPT OF WATER MGMT": "DEPARTMENT OF WATER MANAGEMENT",
    "DEPT OF WATER MANAGEMENT": "DEPARTMENT OF WATER MANAGEMENT",
    "DEPT OF TRANSPORTATION": "DEPARTMENT OF TRANSPORTATION",
    "DEPT OF STREETS AND SANITATION": "DEPARTMENT OF STREETS AND SANITATION",
    "DEPT OF STREETS & SANITATION": "DEPARTMENT OF STREETS AND SANITATION",
    "DEPT OF FINANCE": "DEPARTMENT OF FINANCE",
    "DEPT OF BUILDINGS": "DEPARTMENT OF BUILDINGS",
    "DEPT OF AVIATION": "DEPARTMENT OF AVIATION",
    "DEPT OF PROCUREMENT SERVICES": "DEPARTMENT OF PROCUREMENT SERVICES",
    "DEPT OF PROCUREMENT": "DEPARTMENT OF PROCUREMENT SERVICES",
    "DEPT OF LAW": "DEPARTMENT OF LAW",
    "DEPT OF HUMAN RESOURCES": "DEPARTMENT OF HUMAN RESOURCES",
    "DEPT OF PLANNING AND DEVELOPMENT": "DEPARTMENT OF PLANNING AND DEVELOPMENT",
    "DEPT OF PLANNING & DEVELOPMENT": "DEPARTMENT OF PLANNING AND DEVELOPMENT",
    "DEPT OF PUBLIC HEALTH": "DEPARTMENT OF PUBLIC HEALTH",
    "DEPT OF CULTURAL AFFAIRS": "DEPARTMENT OF CULTURAL AFFAIRS AND SPECIAL EVENTS",
    "DEPT OF CULTURAL AFFAIRS AND SPECIAL EVENTS": "DEPARTMENT OF CULTURAL AFFAIRS AND SPECIAL EVENTS",
}


def _parse_amount(value):
    """Strip $ and commas from amount string and cast to float."""
    if pd.isna(value):
        return 0.0
    s = str(value).strip()
    s = s.replace("$", "").replace(",", "")
    # Handle parentheses for negative amounts e.g. ($1,234.56)
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_check_date(value):
    """Parse CHECK DATE which may be MM/DD/YYYY or a year-only string."""
    if pd.isna(value):
        return pd.NaT, False
    s = str(value).strip()

    # Year-only: 4 digits
    if re.fullmatch(r"\d{4}", s):
        return pd.Timestamp(year=int(s), month=1, day=1), True

    # Standard MM/DD/YYYY
    try:
        return pd.to_datetime(s, format="%m/%d/%Y"), False
    except (ValueError, TypeError):
        pass

    # Fallback: let pandas try to parse it
    try:
        return pd.to_datetime(s), False
    except (ValueError, TypeError):
        return pd.NaT, False


def _classify_contract(value):
    """Classify CONTRACT NUMBER: 'DV' → direct_voucher, numeric → contract, empty → none."""
    if pd.isna(value):
        return "none"
    s = str(value).strip()
    if s == "":
        return "none"
    if s.upper().startswith("DV"):
        return "direct_voucher"
    # Check if it looks numeric (allow leading zeros, dashes, etc.)
    cleaned = s.replace("-", "").replace(" ", "")
    if cleaned.isdigit():
        return "contract"
    return "none"


def _canonicalize_department(name):
    """Apply static mapping to normalize department names."""
    if pd.isna(name):
        return name
    upper = str(name).strip().upper()
    return DEPARTMENT_NAME_MAP.get(upper, str(name).strip())


def ingest_payments():
    """
    Read and clean chicago_payments.csv, output to Parquet.

    Returns:
        pd.DataFrame: Cleaned payments DataFrame.
    """
    print(f"Reading CSV from {CSV_PATH} ...")
    df = pd.read_csv(
        CSV_PATH,
        dtype=str,  # Read everything as string for controlled parsing
        low_memory=False,
    )

    print(f"  Loaded {len(df):,} rows")

    # --- Parse AMOUNT ---
    df["AMOUNT"] = df["AMOUNT"].apply(_parse_amount)

    # --- Parse CHECK DATE ---
    date_results = df["CHECK DATE"].apply(_parse_check_date)
    df["CHECK_DATE"] = date_results.apply(lambda x: x[0])
    df["is_annual_aggregate"] = date_results.apply(lambda x: x[1])

    # --- Derive time columns ---
    df["year"] = df["CHECK_DATE"].dt.year.astype("Int64")
    df["month"] = df["CHECK_DATE"].dt.month.astype("Int64")
    df["quarter"] = df["CHECK_DATE"].dt.quarter.astype("Int64")

    # --- Classify CONTRACT NUMBER ---
    df["contract_type"] = df["CONTRACT NUMBER"].apply(_classify_contract)

    # --- Canonicalize department names ---
    df["DEPARTMENT_NAME"] = df["DEPARTMENT NAME"].apply(_canonicalize_department)

    # --- Clean up column names to lowercase for consistency ---
    df = df.rename(columns={
        "VOUCHER NUMBER": "voucher_number",
        "AMOUNT": "amount",
        "CHECK DATE": "check_date_raw",
        "CHECK_DATE": "check_date",
        "DEPARTMENT NAME": "department_name_raw",
        "DEPARTMENT_NAME": "department_canonical",
        "CONTRACT NUMBER": "contract_number",
        "VENDOR NAME": "vendor_name",
    })

    # --- Write Parquet ---
    output_path = DATA_PROCESSED / "payments.parquet"
    print(f"  Writing Parquet to {output_path} ...")
    df.to_parquet(output_path, index=False, engine="pyarrow")
    print(f"  Done. {len(df):,} rows written.")

    return df
