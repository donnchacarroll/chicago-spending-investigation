"""Orchestrator: ingest, enrich, and build the DuckDB database."""

import sys
from pathlib import Path

# Support running this file directly (python backend/etl/build_db.py)
# by ensuring the project root is on sys.path.
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import duckdb
import pandas as pd

from backend.config import DUCKDB_PATH, DATA_PROCESSED
from backend.etl.ingest import ingest_payments
from backend.etl.enrich import enrich_payments
from backend.external.fetch_contracts import fetch_contracts
from backend.analysis.outliers import detect_outliers
from backend.analysis.duplicates import detect_duplicates
from backend.analysis.splitting import detect_splitting
from backend.analysis.vendors import analyze_vendors
from backend.analysis.contracts import analyze_contracts
from backend.analysis.scoring import compute_risk_scores
from backend.analysis.categories import CATEGORY_MAP, classify_dv_vendor


def build_database():
    """
    Full pipeline: ingest CSV, fetch contracts, enrich, and load into DuckDB.
    """
    # Step 1: Ingest payments CSV
    print("=" * 60)
    print("STEP 1: Ingesting payments CSV")
    print("=" * 60)
    payments_df = ingest_payments()

    # Step 2: Fetch contracts from SODA API
    print()
    print("=" * 60)
    print("STEP 2: Fetching contracts from Chicago Data Portal")
    print("=" * 60)
    contracts_df = fetch_contracts()

    # Step 3: Enrich payments with contract data
    print()
    print("=" * 60)
    print("STEP 3: Enriching payments with contract data")
    print("=" * 60)
    enriched_df = enrich_payments(payments_df, contracts_df)

    # Step 4: Build DuckDB
    print()
    print("=" * 60)
    print("STEP 4: Building DuckDB database")
    print("=" * 60)

    # Remove existing DB to start fresh
    if DUCKDB_PATH.exists():
        DUCKDB_PATH.unlink()
        print(f"  Removed existing database at {DUCKDB_PATH}")

    con = duckdb.connect(str(DUCKDB_PATH))

    # Load payments table
    print("  Loading 'payments' table ...")
    con.execute("CREATE TABLE payments AS SELECT * FROM payments_df")
    row_count = con.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    print(f"    -> {row_count:,} rows")

    # Load contracts table
    print("  Loading 'contracts' table ...")
    con.execute("CREATE TABLE contracts AS SELECT * FROM contracts_df")
    row_count = con.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
    print(f"    -> {row_count:,} rows")

    # Load enriched joined table
    print("  Loading 'payment_contract_joined' table ...")
    con.execute("CREATE TABLE payment_contract_joined AS SELECT * FROM enriched_df")
    # Fix column name collision from merge (amount_x -> amount, drop amount_y)
    try:
        con.execute("ALTER TABLE payment_contract_joined RENAME COLUMN amount_x TO amount")
        con.execute("ALTER TABLE payment_contract_joined DROP COLUMN amount_y")
        print("    Fixed amount column naming (amount_x -> amount)")
    except Exception:
        pass  # columns may already be correct
    row_count = con.execute("SELECT COUNT(*) FROM payment_contract_joined").fetchone()[0]
    print(f"    -> {row_count:,} rows")

    # Add spending_category column using CATEGORY_MAP
    print("  Adding 'spending_category' column to payment_contract_joined ...")
    con.execute("ALTER TABLE payment_contract_joined ADD COLUMN spending_category VARCHAR")
    # Build a CASE expression from the category map
    case_branches = []
    for contract_type_val, category_val in CATEGORY_MAP.items():
        escaped_key = contract_type_val.replace("'", "''")
        escaped_val = category_val.replace("'", "''")
        case_branches.append(f"WHEN contract_type_desc = '{escaped_key}' THEN '{escaped_val}'")
    case_expr = " ".join(case_branches)
    con.execute(f"""
        UPDATE payment_contract_joined
        SET spending_category = CASE
            {case_expr}
            WHEN contract_type_desc IS NULL THEN 'Uncategorized / Direct Voucher'
            ELSE 'Other/Administrative'
        END
    """)
    cat_check = con.execute(
        "SELECT spending_category, COUNT(*) FROM payment_contract_joined GROUP BY spending_category ORDER BY COUNT(*) DESC LIMIT 5"
    ).fetchall()
    print(f"    -> Top categories: {cat_check}")

    # Add dv_subcategory for direct voucher payments
    print("  Classifying direct voucher payments by vendor type ...")
    con.execute("ALTER TABLE payment_contract_joined ADD COLUMN dv_subcategory VARCHAR")
    # Fetch DV vendor names and classify them in Python
    dv_vendors = con.execute(
        "SELECT DISTINCT vendor_name FROM payment_contract_joined WHERE contract_type = 'direct_voucher'"
    ).fetchall()
    vendor_categories = {row[0]: classify_dv_vendor(row[0]) for row in dv_vendors}
    # Build CASE expression
    dv_cases = []
    for vendor, cat in vendor_categories.items():
        escaped_vendor = vendor.replace("'", "''")
        escaped_cat = cat.replace("'", "''")
        dv_cases.append(f"WHEN vendor_name = '{escaped_vendor}' THEN '{escaped_cat}'")
    if dv_cases:
        dv_case_expr = " ".join(dv_cases)
        con.execute(f"""
            UPDATE payment_contract_joined
            SET dv_subcategory = CASE
                {dv_case_expr}
                ELSE NULL
            END
            WHERE contract_type = 'direct_voucher'
        """)
    dv_check = con.execute(
        "SELECT dv_subcategory, COUNT(*), ROUND(SUM(amount)/1e9, 2) as billions FROM payment_contract_joined WHERE contract_type = 'direct_voucher' AND is_annual_aggregate = false GROUP BY dv_subcategory ORDER BY SUM(amount) DESC"
    ).fetchall()
    print(f"    -> DV subcategories:")
    for row in dv_check:
        print(f"       {row[0]:30s} {row[1]:>8,} payments  ${row[2]}B")

    # Step 5: Run analysis modules
    print()
    print("=" * 60)
    print("STEP 5: Running analysis modules")
    print("=" * 60)

    all_flags = []

    print("  Running outlier detection ...")
    try:
        outliers = detect_outliers(con)
        print(f"    -> {len(outliers)} outliers flagged")
        if not outliers.empty:
            all_flags.append(outliers)
    except Exception as e:
        print(f"    -> ERROR: {e}")

    print("  Running duplicate detection ...")
    try:
        duplicates = detect_duplicates(con)
        print(f"    -> {len(duplicates)} duplicates flagged")
        if not duplicates.empty:
            all_flags.append(duplicates)
    except Exception as e:
        print(f"    -> ERROR: {e}")

    print("  Running payment splitting detection ...")
    try:
        splits = detect_splitting(con)
        print(f"    -> {len(splits)} split patterns flagged")
        if not splits.empty:
            all_flags.append(splits)
    except Exception as e:
        print(f"    -> ERROR: {e}")

    print("  Running vendor concentration analysis ...")
    try:
        vendor_flags = analyze_vendors(con)
        print(f"    -> {len(vendor_flags)} concentrated departments flagged")
        if not vendor_flags.empty:
            all_flags.append(vendor_flags)
    except Exception as e:
        print(f"    -> ERROR: {e}")

    print("  Running contract analysis ...")
    try:
        contract_flags = analyze_contracts(con)
        print(f"    -> {len(contract_flags)} contract issues flagged")
        if not contract_flags.empty:
            all_flags.append(contract_flags)
    except Exception as e:
        print(f"    -> ERROR: {e}")

    # Combine all flags
    if all_flags:
        combined_flags = pd.concat(all_flags, ignore_index=True)
    else:
        combined_flags = pd.DataFrame()

    print(f"\n  Total flags: {len(combined_flags)}")

    # Step 6: Compute risk scores
    print()
    print("=" * 60)
    print("STEP 6: Computing composite risk scores")
    print("=" * 60)

    try:
        stats = compute_risk_scores(con, combined_flags)
        print(f"  Payments scored: {stats.get('payments_scored', 0)}")
        print(f"  Vendors scored: {stats.get('vendors_scored', 0)}")
        print(f"  Departments scored: {stats.get('departments_scored', 0)}")
        if 'flag_type_counts' in stats:
            print(f"  Flag breakdown: {stats['flag_type_counts']}")
    except Exception as e:
        print(f"  ERROR computing risk scores: {e}")

    con.close()

    print()
    print("=" * 60)
    print(f"DONE. Database created at {DUCKDB_PATH}")
    print("Tables: payments, contracts, payment_contract_joined, alerts,")
    print("        payment_risk_scores, vendor_risk_scores, department_risk_scores")
    print("=" * 60)


if __name__ == "__main__":
    build_database()
