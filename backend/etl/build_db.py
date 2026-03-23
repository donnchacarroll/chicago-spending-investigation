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

    # ── Salary data and department true cost ──────────────────
    print()
    print("  Fetching salary data ...")
    salaries_df = fetch_salaries()
    con.execute("CREATE TABLE salaries AS SELECT * FROM salaries_df")
    sal_count = con.execute("SELECT COUNT(*) FROM salaries").fetchone()[0]
    print(f"    -> {sal_count:,} rows")

    print("  Building department true cost tables ...")

    # Step A: Salary totals by department
    con.execute("""
        CREATE TABLE dept_salary_totals AS
        SELECT department,
               COUNT(*) AS employee_count,
               SUM(CAST(annual_salary AS DOUBLE)) AS total_salary
        FROM salaries
        GROUP BY department
    """)

    # Step B: Confirmed payment totals (tagged to a department)
    con.execute("""
        CREATE TABLE dept_confirmed_payments AS
        SELECT department_canonical AS department_name,
               SUM(amount) AS confirmed_payments,
               COUNT(*) AS confirmed_count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false
          AND department_canonical IS NOT NULL
        GROUP BY department_canonical
    """)

    # Step C: Contract award totals by department (latest revision only)
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

    pension_rows = []
    for vendor, dept in PENSION_MAP.items():
        row = con.execute("""
            SELECT SUM(amount) AS total
            FROM payment_contract_joined
            WHERE vendor_name = $1
              AND is_annual_aggregate = false
              AND (department_canonical IS NULL OR department_canonical = '')
        """, [vendor]).fetchone()
        amt = row[0] if row[0] else 0
        if amt > 0:
            pension_rows.append((dept, vendor, amt, "pension_fund_mapping"))

    # Step E: Single-department vendor attribution
    # Find vendors where 90%+ of their contract value goes to one department
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

    # Attribute DV payments for single-department vendors
    single_dept_rows = []
    for vendor, dept in single_dept_map.items():
        row = con.execute("""
            SELECT SUM(amount) AS total
            FROM payment_contract_joined
            WHERE vendor_name = $1
              AND is_annual_aggregate = false
              AND (department_canonical IS NULL OR department_canonical = '')
        """, [vendor]).fetchone()
        amt = row[0] if row[0] else 0
        if amt > 0:
            single_dept_rows.append((dept, vendor, amt, "single_dept_vendor"))

    # Combine attributed rows
    all_attributed = pension_rows + single_dept_rows
    if all_attributed:
        attributed_df = pd.DataFrame(all_attributed, columns=[
            "department_name", "source_vendor", "amount", "reason"
        ])
    else:
        attributed_df = pd.DataFrame(columns=[
            "department_name", "source_vendor", "amount", "reason"
        ])

    # Step F: Proportional allocation of shared costs
    SHARED_COST_VENDORS = [
        "MUNICIPAL EMPLOYEE PENSION FD",
        "MUNICIPAL EMPLOYEES ANNUITY AND BENEFIT FUND OF CHICAGO",
        "LABORERS & RETIREMENT BOARD",
        "BLUE CROSS & BLUE SHIELD",
        "NATIONWIDE RETIREMENT SOLUTION",
        "AMALGAMATED BANK OF CHICAGO",
        "USI INSURANCE SERVICES LLC.",
    ]

    # Get total shared costs (unattributed DV payments from shared vendors)
    placeholders = ", ".join([f"${i+1}" for i in range(len(SHARED_COST_VENDORS))])
    shared_total_row = con.execute(f"""
        SELECT SUM(amount) AS total
        FROM payment_contract_joined
        WHERE vendor_name IN ({placeholders})
          AND is_annual_aggregate = false
          AND (department_canonical IS NULL OR department_canonical = '')
    """, SHARED_COST_VENDORS).fetchone()
    shared_total = shared_total_row[0] if shared_total_row[0] else 0

    # Get total headcount for proportional allocation
    total_headcount_row = con.execute(
        "SELECT SUM(employee_count) FROM dept_salary_totals"
    ).fetchone()
    total_headcount = total_headcount_row[0] if total_headcount_row[0] else 1

    # Build shared cost detail per vendor per department
    shared_rows = []
    for vendor in SHARED_COST_VENDORS:
        vrow = con.execute("""
            SELECT SUM(amount) AS total
            FROM payment_contract_joined
            WHERE vendor_name = $1
              AND is_annual_aggregate = false
              AND (department_canonical IS NULL OR department_canonical = '')
        """, [vendor]).fetchone()
        vendor_total = vrow[0] if vrow[0] else 0
        if vendor_total > 0:
            # Allocate proportionally by headcount
            depts = con.execute(
                "SELECT department, employee_count FROM dept_salary_totals"
            ).fetchall()
            for dept_name, emp_count in depts:
                share = (emp_count / total_headcount) * vendor_total
                if share > 0:
                    shared_rows.append((dept_name, vendor, share, "proportional_headcount"))

    if shared_rows:
        shared_df = pd.DataFrame(shared_rows, columns=[
            "department_name", "source_vendor", "amount", "reason"
        ])
    else:
        shared_df = pd.DataFrame(columns=[
            "department_name", "source_vendor", "amount", "reason"
        ])

    # ── Build department_cost_detail table ──
    detail_rows = []
    # Confirmed tier: from dept_confirmed_payments
    confirmed = con.execute(
        "SELECT department_name, confirmed_payments FROM dept_confirmed_payments"
    ).fetchall()
    for dept, amt in confirmed:
        detail_rows.append((dept, "confirmed", "TAGGED_PAYMENTS", amt, "department_tagged_payments"))

    # Confirmed contracts tier
    confirmed_c = con.execute(
        "SELECT department_name, confirmed_contracts FROM dept_confirmed_contracts"
    ).fetchall()
    for dept, amt in confirmed_c:
        detail_rows.append((dept, "confirmed", "CONTRACT_AWARDS", amt, "contract_awards"))

    # Attributed tier
    for _, row in attributed_df.iterrows():
        detail_rows.append((
            row["department_name"], "attributed", row["source_vendor"],
            row["amount"], row["reason"]
        ))

    # Estimated tier
    for _, row in shared_df.iterrows():
        detail_rows.append((
            row["department_name"], "estimated", row["source_vendor"],
            row["amount"], row["reason"]
        ))

    detail_df = pd.DataFrame(detail_rows, columns=[
        "department_name", "tier", "source_vendor", "amount", "reason"
    ])
    con.execute("CREATE TABLE department_cost_detail AS SELECT * FROM detail_df")

    # ── Build department_true_cost summary table ──
    # Aggregate by department across all tiers
    con.execute("""
        CREATE TABLE department_true_cost AS
        WITH attributed_totals AS (
            SELECT department_name, SUM(amount) AS attributed_total
            FROM department_cost_detail
            WHERE tier = 'attributed'
            GROUP BY department_name
        ),
        estimated_totals AS (
            SELECT department_name, SUM(amount) AS estimated_total
            FROM department_cost_detail
            WHERE tier = 'estimated'
            GROUP BY department_name
        )
        SELECT
            COALESCE(s.department, cp.department_name, cc.department_name) AS department_name,
            COALESCE(s.employee_count, 0) AS employee_count,
            COALESCE(s.total_salary, 0) AS total_salary,
            COALESCE(cp.confirmed_payments, 0) AS confirmed_payments,
            COALESCE(cc.confirmed_contracts, 0) AS confirmed_contracts,
            COALESCE(a.attributed_total, 0) AS attributed_total,
            COALESCE(e.estimated_total, 0) AS estimated_total,
            COALESCE(cp.confirmed_payments, 0)
                + COALESCE(a.attributed_total, 0)
                + COALESCE(e.estimated_total, 0) AS total_true_cost
        FROM dept_salary_totals s
        FULL OUTER JOIN dept_confirmed_payments cp ON UPPER(s.department) = UPPER(cp.department_name)
        FULL OUTER JOIN dept_confirmed_contracts cc ON UPPER(COALESCE(s.department, cp.department_name)) = UPPER(cc.department_name)
        LEFT JOIN attributed_totals a ON UPPER(COALESCE(s.department, cp.department_name)) = UPPER(a.department_name)
        LEFT JOIN estimated_totals e ON UPPER(COALESCE(s.department, cp.department_name)) = UPPER(e.department_name)
        ORDER BY total_true_cost DESC
    """)

    tc_count = con.execute("SELECT COUNT(*) FROM department_true_cost").fetchone()[0]
    print(f"    -> department_true_cost: {tc_count} departments")
    detail_count = con.execute("SELECT COUNT(*) FROM department_cost_detail").fetchone()[0]
    print(f"    -> department_cost_detail: {detail_count} rows")

    # ── Political donation data ─────────────────────────────
    print()
    print("  Fetching political donation data for top vendors ...")
    from backend.external.fetch_donations import fetch_vendor_donations

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

    donations_df = fetch_vendor_donations(top_vendor_names, max_vendors=30)
    if not donations_df.empty:
        con.execute("CREATE TABLE donations AS SELECT * FROM donations_df")
        don_count = con.execute("SELECT COUNT(*) FROM donations").fetchone()[0]
        print(f"    -> {don_count:,} donation records")
    else:
        # Create empty table so queries don't fail
        con.execute("""CREATE TABLE donations (
            donor_name VARCHAR, donor_employer VARCHAR, donor_city VARCHAR,
            donor_state VARCHAR, amount DOUBLE, date VARCHAR,
            recipient_committee VARCHAR, recipient_id VARCHAR,
            election_cycle VARCHAR, matched_vendor VARCHAR, match_type VARCHAR
        )""")
        print("    -> 0 donation records (API may be rate limited)")

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
    print("Tables: payments, contracts, payment_contract_joined, salaries, alerts,")
    print("        payment_risk_scores, vendor_risk_scores, department_risk_scores,")
    print("        department_true_cost, department_cost_detail, donations")
    print("=" * 60)


if __name__ == "__main__":
    build_database()
