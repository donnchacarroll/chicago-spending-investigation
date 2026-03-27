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
from backend.external.fetch_salaries import fetch_salaries
from backend.external.fetch_budget_salaries import fetch_budget_salaries
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

    # Load payments table (2023+ only)
    print("  Loading 'payments' table (2023+ only) ...")
    con.execute("CREATE TABLE payments AS SELECT * FROM payments_df WHERE year >= 2023")
    row_count = con.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    print(f"    -> {row_count:,} rows (filtered from {len(payments_df):,})")

    # Load contracts table
    print("  Loading 'contracts' table ...")
    con.execute("CREATE TABLE contracts AS SELECT * FROM contracts_df")
    row_count = con.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
    print(f"    -> {row_count:,} rows")

    # Load enriched joined table (2023+ only)
    print("  Loading 'payment_contract_joined' table (2023+ only) ...")
    con.execute("CREATE TABLE payment_contract_joined AS SELECT * FROM enriched_df WHERE year >= 2023")
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

    # ── Salary data and department true cost ──────────────────
    print()
    print("  Fetching budget salary data (per-year) ...")
    budget_salaries_df = fetch_budget_salaries()
    con.execute("CREATE TABLE budget_salaries AS SELECT * FROM budget_salaries_df")
    bs_count = con.execute("SELECT COUNT(*) FROM budget_salaries").fetchone()[0]
    years_covered = con.execute("SELECT DISTINCT year FROM budget_salaries ORDER BY year").fetchall()
    print(f"    -> {bs_count:,} rows, years: {[r[0] for r in years_covered]}")

    # Keep current salary snapshot for reference
    print("  Fetching current salary snapshot ...")
    salaries_df = fetch_salaries()
    con.execute("CREATE TABLE salaries AS SELECT * FROM salaries_df")
    sal_count = con.execute("SELECT COUNT(*) FROM salaries").fetchone()[0]
    print(f"    -> {sal_count:,} rows")

    print("  Building department true cost tables (per-year) ...")

    # Step A: Salary totals by department per year (from budget ordinance)
    con.execute("""
        CREATE TABLE dept_salary_totals AS
        SELECT department, year,
               CAST(employee_count AS BIGINT) AS employee_count,
               total_salary
        FROM budget_salaries
    """)

    # Step B: Confirmed payment totals by department per year
    con.execute("""
        CREATE TABLE dept_confirmed_payments AS
        SELECT department_canonical AS department_name,
               year,
               SUM(amount) AS confirmed_payments,
               COUNT(*) AS confirmed_count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false
          AND department_canonical IS NOT NULL
        GROUP BY department_canonical, year
    """)

    # Step C: Contract award totals by department (not per-year — awards are totals)
    con.execute("""
        CREATE TABLE dept_confirmed_contracts AS
        SELECT department AS department_name,
               SUM(CAST(award_amount AS DOUBLE)) AS confirmed_contracts,
               COUNT(*) AS contract_count
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY specification_number
                       ORDER BY revision_number DESC NULLS LAST
                   ) AS rn
            FROM contracts
            WHERE department IS NOT NULL
        ) sub
        WHERE rn = 1
        GROUP BY department
    """)

    # Step D: Pension fund mapping — attribute pension payments to departments
    PENSION_MAP = {
        "POLICEMENS A & B FUND": "CHICAGO POLICE DEPARTMENT",
        "FIREMENS ANNUITY BENEFIT FUND": "CHICAGO FIRE DEPARTMENT",
        "CHICAGO PATROLMEN'S FCU": "CHICAGO POLICE DEPARTMENT",
        "CHICAGO FIREMANS ASSN CREDIT": "CHICAGO FIRE DEPARTMENT",
    }

    # Step E: Single-department vendor attribution
    single_dept_vendors = con.execute("""
        WITH latest_contracts AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY specification_number
                       ORDER BY revision_number DESC NULLS LAST
                   ) AS rn
            FROM contracts
            WHERE department IS NOT NULL
        ),
        vendor_dept_totals AS (
            SELECT vendor_name,
                   department,
                   SUM(CAST(award_amount AS DOUBLE)) AS dept_total
            FROM latest_contracts
            WHERE rn = 1
            GROUP BY vendor_name, department
        ),
        vendor_totals AS (
            SELECT vendor_name,
                   SUM(dept_total) AS grand_total
            FROM vendor_dept_totals
            GROUP BY vendor_name
        )
        SELECT vdt.vendor_name, vdt.department, vdt.dept_total,
               vdt.dept_total / NULLIF(vt.grand_total, 0) AS share
        FROM vendor_dept_totals vdt
        JOIN vendor_totals vt ON vdt.vendor_name = vt.vendor_name
        WHERE vdt.dept_total / NULLIF(vt.grand_total, 0) >= 0.9
    """).fetchall()
    single_dept_map = {row[0]: row[1] for row in single_dept_vendors}

    # Combine pension + single-dept vendor maps for attribution
    attribution_map = {}
    for vendor, dept in PENSION_MAP.items():
        attribution_map[vendor] = (dept, "pension_fund_mapping")
    for vendor, dept in single_dept_map.items():
        if vendor not in attribution_map:
            attribution_map[vendor] = (dept, "single_dept_vendor")

    # Step F: Shared cost vendors for proportional allocation
    SHARED_COST_VENDORS = [
        "MUNICIPAL EMPLOYEE PENSION FD",
        "MUNICIPAL EMPLOYEES ANNUITY AND BENEFIT FUND OF CHICAGO",
        "LABORERS & RETIREMENT BOARD",
        "BLUE CROSS & BLUE SHIELD",
        "NATIONWIDE RETIREMENT SOLUTION",
        "AMALGAMATED BANK OF CHICAGO",
        "USI INSURANCE SERVICES LLC.",
    ]

    # Get available years from payments
    payment_years = [r[0] for r in con.execute(
        "SELECT DISTINCT year FROM payment_contract_joined WHERE is_annual_aggregate = false ORDER BY year"
    ).fetchall()]

    # ── Build department_cost_detail table (per-year) ──
    detail_rows = []

    for yr in payment_years:
        # Confirmed tier: tagged payments for this year
        confirmed = con.execute("""
            SELECT department_name, confirmed_payments
            FROM dept_confirmed_payments WHERE year = $1
        """, [yr]).fetchall()
        for dept, amt in confirmed:
            detail_rows.append((yr, dept, "confirmed", "TAGGED_PAYMENTS", amt, "department_tagged_payments"))

        # Attributed tier: pension + single-dept vendor payments for this year
        for vendor, (dept, reason) in attribution_map.items():
            row = con.execute("""
                SELECT SUM(amount) AS total
                FROM payment_contract_joined
                WHERE vendor_name = $1 AND year = $2
                  AND is_annual_aggregate = false
                  AND (department_canonical IS NULL OR department_canonical = '')
            """, [vendor, yr]).fetchone()
            amt = row[0] if row[0] else 0
            if amt > 0:
                detail_rows.append((yr, dept, "attributed", vendor, amt, reason))

        # Estimated tier: shared costs allocated by headcount for this year
        # Use this year's headcount from budget_salaries
        headcount_rows = con.execute("""
            SELECT department, employee_count FROM dept_salary_totals WHERE year = $1
        """, [yr]).fetchall()

        if not headcount_rows:
            # Fall back to nearest available year
            nearest = con.execute("""
                SELECT year FROM (SELECT DISTINCT year FROM dept_salary_totals)
                ORDER BY ABS(year - $1) LIMIT 1
            """, [yr]).fetchone()
            if nearest:
                headcount_rows = con.execute("""
                    SELECT department, employee_count FROM dept_salary_totals WHERE year = $1
                """, [nearest[0]]).fetchall()

        total_headcount = sum(r[1] for r in headcount_rows) or 1

        for vendor in SHARED_COST_VENDORS:
            vrow = con.execute("""
                SELECT SUM(amount) AS total
                FROM payment_contract_joined
                WHERE vendor_name = $1 AND year = $2
                  AND is_annual_aggregate = false
                  AND (department_canonical IS NULL OR department_canonical = '')
            """, [vendor, yr]).fetchone()
            vendor_total = vrow[0] if vrow[0] else 0
            if vendor_total > 0:
                for dept_name, emp_count in headcount_rows:
                    share = (emp_count / total_headcount) * vendor_total
                    if share > 0:
                        detail_rows.append((yr, dept_name, "estimated", vendor, share, "proportional_headcount"))

    detail_df = pd.DataFrame(detail_rows, columns=[
        "year", "department_name", "tier", "source_vendor", "amount", "reason"
    ])
    con.execute("CREATE TABLE department_cost_detail AS SELECT * FROM detail_df")

    # ── Build department_true_cost summary table (per-year) ──
    con.execute("""
        CREATE TABLE department_true_cost AS
        WITH yearly_attributed AS (
            SELECT year, department_name, SUM(amount) AS attributed_total
            FROM department_cost_detail
            WHERE tier = 'attributed'
            GROUP BY year, department_name
        ),
        yearly_estimated AS (
            SELECT year, department_name, SUM(amount) AS estimated_total
            FROM department_cost_detail
            WHERE tier = 'estimated'
            GROUP BY year, department_name
        ),
        yearly_confirmed AS (
            SELECT year, department_name, SUM(amount) AS confirmed_payments
            FROM department_cost_detail
            WHERE tier = 'confirmed' AND source_vendor = 'TAGGED_PAYMENTS'
            GROUP BY year, department_name
        ),
        all_dept_years AS (
            SELECT DISTINCT year, department_name FROM department_cost_detail
            UNION
            SELECT year, department FROM dept_salary_totals
        )
        SELECT
            ady.year,
            ady.department_name,
            COALESCE(s.employee_count, 0) AS employee_count,
            COALESCE(s.total_salary, 0) AS total_salary,
            COALESCE(yc.confirmed_payments, 0) AS confirmed_payments,
            COALESCE(cc.confirmed_contracts, 0) AS confirmed_contracts,
            COALESCE(ya.attributed_total, 0) AS attributed_total,
            COALESCE(ye.estimated_total, 0) AS estimated_total,
            COALESCE(yc.confirmed_payments, 0)
                + COALESCE(ya.attributed_total, 0)
                + COALESCE(ye.estimated_total, 0) AS total_true_cost
        FROM all_dept_years ady
        LEFT JOIN dept_salary_totals s
            ON UPPER(ady.department_name) = UPPER(s.department) AND ady.year = s.year
        LEFT JOIN yearly_confirmed yc
            ON ady.department_name = yc.department_name AND ady.year = yc.year
        LEFT JOIN dept_confirmed_contracts cc
            ON UPPER(ady.department_name) = UPPER(cc.department_name)
        LEFT JOIN yearly_attributed ya
            ON ady.department_name = ya.department_name AND ady.year = ya.year
        LEFT JOIN yearly_estimated ye
            ON ady.department_name = ye.department_name AND ady.year = ye.year
        ORDER BY ady.year, total_true_cost DESC
    """)

    tc_count = con.execute("SELECT COUNT(*) FROM department_true_cost").fetchone()[0]
    tc_years = con.execute("SELECT DISTINCT year FROM department_true_cost ORDER BY year").fetchall()
    print(f"    -> department_true_cost: {tc_count} rows, years: {[r[0] for r in tc_years]}")
    detail_count = con.execute("SELECT COUNT(*) FROM department_cost_detail").fetchone()[0]
    print(f"    -> department_cost_detail: {detail_count} rows")

    # ── Political donation data ─────────────────────────────
    print()
    print("  Fetching political donation data for top vendors ...")
    from backend.external.fetch_donations import fetch_vendor_donations
    from backend.external.fetch_isbe_donations import fetch_isbe_vendor_donations

    # Get top vendors by payment + contract value
    top_vendor_rows = con.execute("""
        SELECT vendor_name, SUM(amount) as total
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false AND amount > 0
        GROUP BY vendor_name
        ORDER BY total DESC
        LIMIT 30
    """).fetchall()
    top_vendor_names = [r[0] for r in top_vendor_rows]

    donation_frames = []

    # FEC (federal) donations
    print("  Fetching FEC (federal) donations ...")
    fec_df = fetch_vendor_donations(top_vendor_names, max_vendors=30)
    if not fec_df.empty:
        fec_df["source"] = "fec"
        donation_frames.append(fec_df)
        print(f"    -> FEC: {len(fec_df):,} records")

    # ISBE (Illinois state/local) donations
    print("  Fetching ISBE (Illinois state/local) donations ...")
    try:
        isbe_df = fetch_isbe_vendor_donations(top_vendor_names, max_vendors=30)
        if not isbe_df.empty:
            donation_frames.append(isbe_df)
            print(f"    -> ISBE: {len(isbe_df):,} records")
        else:
            print("    -> ISBE: 0 records")
    except Exception as e:
        print(f"    -> ISBE ERROR: {e}")

    if donation_frames:
        donations_df = pd.concat(donation_frames, ignore_index=True)
        con.execute("CREATE TABLE donations AS SELECT * FROM donations_df")
        don_count = con.execute("SELECT COUNT(*) FROM donations").fetchone()[0]
        fec_count = con.execute("SELECT COUNT(*) FROM donations WHERE source = 'fec'").fetchone()[0]
        isbe_count = con.execute("SELECT COUNT(*) FROM donations WHERE source = 'isbe'").fetchone()[0]
        print(f"    -> Total: {don_count:,} donation records (FEC: {fec_count:,}, ISBE: {isbe_count:,})")
    else:
        con.execute("""CREATE TABLE donations (
            donor_name VARCHAR, donor_employer VARCHAR, donor_city VARCHAR,
            donor_state VARCHAR, amount DOUBLE, date VARCHAR,
            recipient_committee VARCHAR, recipient_id VARCHAR,
            election_cycle VARCHAR, matched_vendor VARCHAR, match_type VARCHAR,
            source VARCHAR
        )""")
        print("    -> 0 donation records")

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
    print("Tables: payments, contracts, payment_contract_joined, salaries,")
    print("        budget_salaries, alerts, payment_risk_scores,")
    print("        vendor_risk_scores, department_risk_scores,")
    print("        department_true_cost, department_cost_detail, donations")
    print("=" * 60)


if __name__ == "__main__":
    build_database()
