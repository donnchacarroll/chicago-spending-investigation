"""Shared pytest fixtures: in-memory DuckDB test database and Flask test client."""

import os
from pathlib import Path

import duckdb
import pandas as pd
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def test_db():
    """Session-scoped in-memory DuckDB with fixture data and analysis tables."""
    con = duckdb.connect(":memory:")

    # --- Load fixture CSVs ---
    payments_df = pd.read_csv(FIXTURES_DIR / "payments.csv")
    contracts_df = pd.read_csv(FIXTURES_DIR / "contracts.csv")
    budget_salaries_df = pd.read_csv(FIXTURES_DIR / "budget_salaries.csv")

    # Ensure check_date is datetime
    payments_df["check_date"] = pd.to_datetime(payments_df["check_date"])

    con.execute("CREATE TABLE payments AS SELECT * FROM payments_df")
    con.execute("CREATE TABLE contracts AS SELECT * FROM contracts_df")
    con.execute("CREATE TABLE budget_salaries AS SELECT * FROM budget_salaries_df")

    # Add contract_pdf struct column (NULL for all rows — CSV can't represent structs)
    con.execute("ALTER TABLE contracts ADD COLUMN contract_pdf STRUCT(url VARCHAR)")

    # --- Build payment_contract_joined (simplified enrichment) ---
    con.execute("""
        CREATE TABLE payment_contract_joined AS
        SELECT
            p.voucher_number,
            p.amount,
            p.check_date_raw,
            p.department_name_raw,
            p.contract_number,
            p.vendor_name,
            p.check_date,
            p.is_annual_aggregate,
            p.year,
            p.month,
            p.quarter,
            p.contract_type,
            p.department_canonical,
            c.award_amount,
            c.start_date AS contract_start,
            c.end_date AS contract_end,
            c.procurement_type,
            c.purchase_order_description,
            c.contract_type AS contract_type_desc,
            CAST(NULL AS INTEGER) AS overspend_ratio,
            CAST(NULL AS VARCHAR) AS spending_category,
            CAST(NULL AS VARCHAR) AS dv_subcategory
        FROM payments p
        LEFT JOIN contracts c ON p.contract_number = c.purchase_order_contract_number
    """)

    # Populate spending_category using the same CATEGORY_MAP as production
    from backend.analysis.categories import CATEGORY_MAP, classify_dv_vendor

    case_branches = []
    for contract_type_val, category_val in CATEGORY_MAP.items():
        escaped_key = contract_type_val.replace("'", "''")
        escaped_val = category_val.replace("'", "''")
        case_branches.append(
            f"WHEN contract_type_desc = '{escaped_key}' THEN '{escaped_val}'"
        )
    case_expr = " ".join(case_branches)
    con.execute(f"""
        UPDATE payment_contract_joined
        SET spending_category = CASE
            {case_expr}
            WHEN contract_type_desc IS NULL THEN 'Uncategorized / Direct Voucher'
            ELSE 'Other/Administrative'
        END
    """)

    # Populate dv_subcategory for direct voucher payments
    dv_vendors = con.execute(
        "SELECT DISTINCT vendor_name FROM payment_contract_joined "
        "WHERE contract_type = 'direct_voucher'"
    ).fetchall()
    for (vendor,) in dv_vendors:
        cat = classify_dv_vendor(vendor)
        escaped_vendor = vendor.replace("'", "''")
        escaped_cat = cat.replace("'", "''")
        con.execute(f"""
            UPDATE payment_contract_joined
            SET dv_subcategory = '{escaped_cat}'
            WHERE vendor_name = '{escaped_vendor}' AND contract_type = 'direct_voucher'
        """)

    # --- Flag intergovernmental vendors ---
    from backend.analysis.categories import is_intergovernmental_vendor
    con.execute("ALTER TABLE payment_contract_joined ADD COLUMN is_intergovernmental BOOLEAN DEFAULT false")
    con.execute("ALTER TABLE payments ADD COLUMN is_intergovernmental BOOLEAN DEFAULT false")
    all_vendors = con.execute("SELECT DISTINCT vendor_name FROM payment_contract_joined").fetchall()
    gov_vendors = [v for (v,) in all_vendors if is_intergovernmental_vendor(v)]
    if gov_vendors:
        placeholders = ", ".join(f"'{v.replace(chr(39), chr(39)+chr(39))}'" for v in gov_vendors)
        for table in ("payment_contract_joined", "payments"):
            con.execute(f"UPDATE {table} SET is_intergovernmental = true WHERE vendor_name IN ({placeholders})")

    # --- Compute total_paid_per_contract and overspend_ratio ---
    con.execute("ALTER TABLE payment_contract_joined ADD COLUMN total_paid_per_contract DOUBLE")
    con.execute("""
        UPDATE payment_contract_joined
        SET total_paid_per_contract = (
            SELECT SUM(p2.amount) FROM payment_contract_joined p2
            WHERE p2.contract_number = payment_contract_joined.contract_number
              AND p2.contract_number IS NOT NULL
              AND p2.contract_number != ''
        )
        WHERE contract_type = 'contract'
    """)
    con.execute("""
        UPDATE payment_contract_joined
        SET overspend_ratio = CASE
            WHEN award_amount > 0 THEN CAST(
                total_paid_per_contract / award_amount AS INTEGER)
            ELSE NULL
        END
        WHERE contract_type = 'contract'
    """)

    # --- Run analysis pipeline ---
    from backend.analysis.outliers import detect_outliers
    from backend.analysis.duplicates import detect_duplicates
    from backend.analysis.splitting import detect_splitting
    from backend.analysis.vendors import analyze_vendors
    from backend.analysis.contracts import analyze_contracts
    from backend.analysis.scoring import compute_risk_scores

    flags_dfs = []
    for detect_fn in [detect_outliers, detect_duplicates, detect_splitting,
                      analyze_vendors, analyze_contracts]:
        result = detect_fn(con)
        if result is not None and len(result) > 0:
            flags_dfs.append(result)

    if flags_dfs:
        all_flags_df = pd.concat(flags_dfs, ignore_index=True)
    else:
        all_flags_df = pd.DataFrame(
            columns=["flag_type", "description", "risk_score",
                     "vendor_name", "department_name", "voucher_number", "amount"]
        )

    compute_risk_scores(con, all_flags_df)

    # --- Salary and department tables ---
    con.execute("""
        CREATE TABLE dept_salary_totals AS
        SELECT department, year,
               CAST(employee_count AS BIGINT) AS employee_count,
               total_salary
        FROM budget_salaries
    """)

    con.execute("""
        CREATE TABLE salaries (
            name VARCHAR, job_titles VARCHAR, department VARCHAR,
            full_or_part_time VARCHAR, salary_or_hourly VARCHAR,
            annual_salary DOUBLE, typical_hours VARCHAR, hourly_rate VARCHAR
        )
    """)

    # Stub department_true_cost
    con.execute("""
        CREATE TABLE department_true_cost (
            year BIGINT, department_name VARCHAR, employee_count BIGINT,
            total_salary DOUBLE, confirmed_payments DOUBLE,
            confirmed_contracts DOUBLE, attributed_total DOUBLE,
            estimated_total DOUBLE, total_true_cost DOUBLE
        )
    """)
    con.execute("""
        INSERT INTO department_true_cost
        SELECT year, department, employee_count, total_salary,
               0.0, 0.0, 0.0, 0.0, total_salary
        FROM budget_salaries
    """)

    # Stub department_cost_detail
    con.execute("""
        CREATE TABLE department_cost_detail (
            year BIGINT, department_name VARCHAR, tier VARCHAR,
            source_vendor VARCHAR, amount DOUBLE, reason VARCHAR
        )
    """)

    # Stub donations table
    con.execute("""
        CREATE TABLE donations (
            donor_name VARCHAR, donor_employer VARCHAR,
            donor_city VARCHAR, donor_state VARCHAR,
            amount DOUBLE, date VARCHAR,
            recipient_committee VARCHAR, recipient_id VARCHAR,
            election_cycle BIGINT, matched_vendor VARCHAR,
            match_type VARCHAR, source VARCHAR
        )
    """)

    yield con
    con.close()


@pytest.fixture
def client(test_db):
    """Flask test client wired to the in-memory test database."""
    import backend.api.db as db_module

    db_module._test_con = test_db
    from backend.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    db_module._test_con = None
