# Test Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pytest-based test framework with fixture data, analysis module tests, and API route integration tests.

**Architecture:** Session-scoped in-memory DuckDB loaded with hand-crafted CSV fixtures. Analysis modules run during fixture setup to populate risk tables. Flask test client uses a `_test_con` override in `db.py` to bypass production DB. Flat test directory under `backend/tests/`.

**Tech Stack:** pytest, pytest-flask, DuckDB (in-memory), Flask test client

**Spec:** `docs/superpowers/specs/2026-03-28-test-framework-design.md`

---

### Task 1: Dependencies, config, and DB injection

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Modify: `backend/api/db.py`

- [ ] **Step 1: Add pytest dependencies to requirements.txt**

Add these two lines to the end of `requirements.txt`:

```
pytest
pytest-flask
```

- [ ] **Step 2: Install the new dependencies**

Run: `source .venv/bin/activate && pip install pytest pytest-flask`

- [ ] **Step 3: Create pytest.ini**

Create `pytest.ini` in project root:

```ini
[pytest]
testpaths = backend/tests
python_files = test_*.py
python_functions = test_*
```

- [ ] **Step 4: Add _test_con override to db.py**

Modify `backend/api/db.py` to support test DB injection. The current code:

```python
_local = threading.local()

def get_db():
    """Return a thread-local read-only DuckDB connection."""
    if not hasattr(_local, "con") or _local.con is None:
        _local.con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    return _local.con
```

Change to:

```python
_local = threading.local()
_test_con = None  # Set by test fixtures to override the connection


def get_db():
    """Return a thread-local read-only DuckDB connection."""
    if _test_con is not None:
        return _test_con
    if not hasattr(_local, "con") or _local.con is None:
        _local.con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    return _local.con
```

- [ ] **Step 5: Verify production still works**

Run: `source .venv/bin/activate && python -c "from backend.app import create_app; create_app(); print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini backend/api/db.py
git commit -m "Add pytest deps, config, and test DB injection support in db.py"
```

---

### Task 2: Create fixture CSV files

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/fixtures/payments.csv`
- Create: `backend/tests/fixtures/contracts.csv`
- Create: `backend/tests/fixtures/budget_salaries.csv`

- [ ] **Step 1: Create test directory and __init__.py**

```bash
mkdir -p backend/tests/fixtures
touch backend/tests/__init__.py
```

- [ ] **Step 2: Create payments.csv**

Create `backend/tests/fixtures/payments.csv` with ~50 rows. Must match the production schema exactly:

Columns: `voucher_number,amount,check_date_raw,department_name_raw,contract_number,vendor_name,check_date,is_annual_aggregate,year,month,quarter,contract_type,department_canonical`

Required test scenarios in the data:
- **Normal payments** (rows 1-30): Regular payments across departments FINANCE, POLICE, WATER, TRANSPORTATION with amounts $1,000-$50,000
- **Outlier setup** (rows 31-35): Vendor `EXTREME_VENDOR_LLC` in department FINANCE with 4 normal payments of $5,000 each, then one extreme payment of $9,999,999 (row 35). The outlier detector requires `MIN_PAYMENTS_FOR_ZSCORE = 5` payments per `(department_canonical, vendor_name)` group, so this vendor needs 5 total payments for the Z-score to be computed and the extreme one flagged
- **Duplicate pair** (rows 32-33): Same vendor `DUPLICATE_CORP`, same amount $25,000, same date 2023-06-15
- **Splitting pattern** (rows 36-42): Vendor `SPLIT_SERVICES_INC`, department POLICE, 7 payments of $9,500 each (just under $10,000 threshold), all within a 7-day window (matching `SPLITTING_WINDOW_DAYS = 7` from config.py). Use consecutive dates like 2023-06-01 through 2023-06-07
- **Contract payments** (rows 43-47): Payments with contract_number matching contracts.csv (e.g., `CT-001`, `CT-002`, `CT-003`), contract_type=`contract`. Ensure CT-003 has $15,000+ total to trigger overspend (award is $10,000)
- **Direct voucher** (rows 48-52): Payments with contract_type=`direct_voucher`, vendor names like `ACME LAW FIRM` (legal), `CHICAGO PENSION FUND` (pension), `CITY UTILITIES INC` (utilities)

All dates should be in 2023-2024. Use `check_date` as ISO format timestamps (e.g., `2023-06-15T00:00:00`). Set `is_annual_aggregate` to `false` for all except one row. Set `month` and `quarter` appropriately for the dates.

- [ ] **Step 3: Create contracts.csv**

Create `backend/tests/fixtures/contracts.csv` matching the production schema:

Columns: `purchase_order_description,purchase_order_contract_number,revision_number,specification_number,contract_type,approval_date,department,vendor_name,vendor_id,address_1,city,state,zip,award_amount,end_date,start_date,address_2,procurement_type`

Required rows:
- `CT-001`: Active contract, vendor `CONTRACT_VENDOR_A`, department FINANCE, award_amount $100,000, start 2023-01-01, end 2025-12-31, procurement_type `COMPETITIVE`
- `CT-002`: Expired contract, vendor `CONTRACT_VENDOR_B`, department POLICE, award_amount $50,000, start 2022-01-01, end 2022-12-31
- `CT-003`: Over-budget contract, vendor `CONTRACT_VENDOR_C`, department WATER, award_amount $10,000, start 2023-01-01, end 2025-12-31 (payments fixture should have $15,000+ paid against this)
- `CT-004`: No matching payments, vendor `ORPHAN_VENDOR`, department TRANSPORTATION, award_amount $200,000
- `CT-005` through `CT-010`: Additional contracts across departments, mix of procurement types (`SOLE SOURCE`, `COMPETITIVE`, `EMERGENCY`), some sharing address_1 `123 MAIN ST` and city `CHICAGO` (for network clustering tests)
- Vendors at same address: `CT-006` and `CT-007` should have the same `address_1`, `city`, `zip` but different `vendor_name` (for address cluster tests)

Note: The production schema has a `contract_pdf` STRUCT column, but the CSV won't have this. The conftest will add it as a NULL struct column after loading.

- [ ] **Step 4: Create budget_salaries.csv**

Create `backend/tests/fixtures/budget_salaries.csv`:

Columns: `department,year,employee_count,total_salary`

```csv
department,year,employee_count,total_salary
FINANCE,2023,150,12000000
FINANCE,2024,155,12500000
POLICE,2023,12000,1200000000
POLICE,2024,12100,1250000000
WATER,2023,2000,160000000
WATER,2024,2050,165000000
TRANSPORTATION,2023,1500,120000000
TRANSPORTATION,2024,1550,125000000
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/
git commit -m "Add test fixture CSV files for payments, contracts, and budget salaries"
```

---

### Task 3: Create conftest.py with test_db and client fixtures

**Files:**
- Create: `backend/tests/conftest.py`

**Reference:**
- Production schema: see `DESCRIBE` output of all tables in spec
- Enrichment logic: `backend/etl/enrich.py` (join payments + contracts)
- Scoring pipeline: `backend/analysis/scoring.py` (compute_risk_scores)
- DB module: `backend/api/db.py` (_test_con override)

- [ ] **Step 1: Write conftest.py**

Create `backend/tests/conftest.py`:

```python
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
    con.execute("""
        ALTER TABLE contracts ADD COLUMN contract_pdf STRUCT(url VARCHAR)
    """)

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

    # --- Compute total_paid_per_contract and overspend_ratio ---
    # analyze_contracts() queries total_paid_per_contract directly
    con.execute("""
        ALTER TABLE payment_contract_joined ADD COLUMN total_paid_per_contract DOUBLE
    """)
    con.execute("""
        UPDATE payment_contract_joined
        SET total_paid_per_contract = (
            SELECT SUM(p2.amount) FROM payment_contract_joined p2
            WHERE p2.contract_number = payment_contract_joined.contract_number
              AND p2.contract_number IS NOT NULL
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
    # Insert one row per department/year for route tests
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
```

- [ ] **Step 2: Verify fixtures load without errors**

Run: `source .venv/bin/activate && pytest --co -q`
Expected: Shows collected test files (0 tests at this point is fine, no errors)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "Add conftest.py with test_db and client fixtures"
```

---

### Task 4: Test outlier detection

**Files:**
- Create: `backend/tests/test_outliers.py`
- Reference: `backend/analysis/outliers.py` (function: `detect_outliers(con) -> pd.DataFrame`)

The outlier module queries the `payments` table, computes Z-scores per department, and flags payments where `z_score > 3`. Returns DataFrame with columns: `voucher_number`, `vendor_name`, `department_name`, `amount`, `z_score`, `group_mean`, `group_std`, `flag_type`, `description`, `risk_score`.

- [ ] **Step 1: Write tests**

Create `backend/tests/test_outliers.py`:

```python
"""Tests for outlier detection (Z-score based anomaly flagging)."""

from backend.analysis.outliers import detect_outliers


def test_outlier_flags_extreme_amount(test_db):
    """A payment with amount 4+ std devs above mean should be flagged."""
    results = detect_outliers(test_db)
    assert len(results) > 0, "Should flag at least one outlier"
    flagged_vendors = results["vendor_name"].tolist()
    assert "EXTREME_VENDOR_LLC" in flagged_vendors


def test_outlier_flag_type_is_correct(test_db):
    """All flagged rows should have flag_type OUTLIER_AMOUNT."""
    results = detect_outliers(test_db)
    assert (results["flag_type"] == "OUTLIER_AMOUNT").all()


def test_outlier_has_positive_risk_score(test_db):
    """Flagged outliers should have risk_score > 0."""
    results = detect_outliers(test_db)
    assert (results["risk_score"] > 0).all()


def test_outlier_normal_payments_not_flagged(test_db):
    """Normal payments within expected range should not be flagged."""
    results = detect_outliers(test_db)
    # Normal vendors from our fixtures should not appear
    flagged_vendors = set(results["vendor_name"].tolist())
    # At minimum, the bulk of our ~30 normal-amount vendors should not be flagged
    assert len(flagged_vendors) < 10, f"Too many vendors flagged: {flagged_vendors}"
```

- [ ] **Step 2: Run tests**

Run: `source .venv/bin/activate && pytest backend/tests/test_outliers.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_outliers.py
git commit -m "Add outlier detection tests"
```

---

### Task 5: Test duplicate detection

**Files:**
- Create: `backend/tests/test_duplicates.py`
- Reference: `backend/analysis/duplicates.py` (function: `detect_duplicates(con) -> pd.DataFrame`)

The duplicates module queries the `payments` table, self-joins to find payments with same vendor, amount, and date. Returns DataFrame with columns: `voucher_number`, `vendor_name`, `amount`, `check_date`, `duplicate_voucher`, `flag_type`, `confidence`, `description`, `risk_score`.

- [ ] **Step 1: Write tests**

Create `backend/tests/test_duplicates.py`:

```python
"""Tests for duplicate payment detection."""

from backend.analysis.duplicates import detect_duplicates


def test_duplicate_finds_exact_match(test_db):
    """Two payments with same vendor, amount, date should be flagged."""
    results = detect_duplicates(test_db)
    assert len(results) > 0, "Should find at least one duplicate"
    flagged_vendors = results["vendor_name"].tolist()
    assert "DUPLICATE_CORP" in flagged_vendors


def test_duplicate_flag_type(test_db):
    """Flagged duplicates should have flag_type DUPLICATE_PAYMENT."""
    results = detect_duplicates(test_db)
    assert (results["flag_type"] == "DUPLICATE_PAYMENT").all()


def test_duplicate_has_matching_voucher(test_db):
    """Each flagged duplicate should reference the other voucher number."""
    results = detect_duplicates(test_db)
    dup_rows = results[results["vendor_name"] == "DUPLICATE_CORP"]
    assert len(dup_rows) >= 1
    assert dup_rows["duplicate_voucher"].notna().all()


def test_duplicate_risk_score_positive(test_db):
    """Flagged duplicates should have risk_score > 0."""
    results = detect_duplicates(test_db)
    assert (results["risk_score"] > 0).all()
```

- [ ] **Step 2: Run tests**

Run: `source .venv/bin/activate && pytest backend/tests/test_duplicates.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_duplicates.py
git commit -m "Add duplicate detection tests"
```

---

### Task 6: Test splitting detection

**Files:**
- Create: `backend/tests/test_splitting.py`
- Reference: `backend/analysis/splitting.py` (function: `detect_splitting(con) -> pd.DataFrame`)

The splitting module queries the `payments` table, looks for patterns where a vendor receives multiple payments just under a threshold within a time window. Returns DataFrame with columns: `vendor_name`, `department_name`, `threshold`, `payment_count`, `total_amount`, `date_range`, `flag_type`, `description`, `risk_score`.

- [ ] **Step 1: Write tests**

Create `backend/tests/test_splitting.py`:

```python
"""Tests for payment splitting detection."""

from backend.analysis.splitting import detect_splitting


def test_splitting_detects_pattern(test_db):
    """Multiple payments just under threshold from same vendor should be flagged."""
    results = detect_splitting(test_db)
    assert len(results) > 0, "Should detect at least one splitting pattern"
    flagged_vendors = results["vendor_name"].tolist()
    assert "SPLIT_SERVICES_INC" in flagged_vendors


def test_splitting_flag_type(test_db):
    """Flagged rows should have flag_type SPLIT_PAYMENT."""
    results = detect_splitting(test_db)
    assert (results["flag_type"] == "SPLIT_PAYMENT").all()


def test_splitting_captures_count(test_db):
    """Splitting detection should report the number of split payments."""
    results = detect_splitting(test_db)
    split_row = results[results["vendor_name"] == "SPLIT_SERVICES_INC"]
    if len(split_row) > 0:
        assert split_row.iloc[0]["payment_count"] >= 3


def test_splitting_risk_score_positive(test_db):
    """Flagged splits should have risk_score > 0."""
    results = detect_splitting(test_db)
    assert (results["risk_score"] > 0).all()
```

- [ ] **Step 2: Run tests**

Run: `source .venv/bin/activate && pytest backend/tests/test_splitting.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_splitting.py
git commit -m "Add splitting detection tests"
```

---

### Task 7: Test vendor analysis

**Files:**
- Create: `backend/tests/test_vendors_analysis.py`
- Reference: `backend/analysis/vendors.py` (function: `analyze_vendors(con) -> pd.DataFrame`)

The vendors module queries the `payments` table, calculates HHI (Herfindahl-Hirschman Index) per department, and flags departments with high vendor concentration. Returns DataFrame with columns: `department_name`, `hhi`, `top_vendor_name`, `top_vendor_pct`, `flag_type`, `description`, `risk_score`.

- [ ] **Step 1: Write tests**

Create `backend/tests/test_vendors_analysis.py`:

```python
"""Tests for vendor concentration analysis (HHI)."""

from backend.analysis.vendors import analyze_vendors


def test_vendor_analysis_returns_results(test_db):
    """Should return concentration metrics for departments."""
    results = analyze_vendors(test_db)
    assert len(results) > 0


def test_vendor_hhi_in_valid_range(test_db):
    """HHI should be between 0 and 10000."""
    results = analyze_vendors(test_db)
    assert (results["hhi"] >= 0).all()
    assert (results["hhi"] <= 10000).all()


def test_vendor_flag_type(test_db):
    """Flagged departments should have flag_type HIGH_CONCENTRATION."""
    results = analyze_vendors(test_db)
    if len(results) > 0:
        assert (results["flag_type"] == "HIGH_CONCENTRATION").all()


def test_vendor_risk_score_positive(test_db):
    """Flagged rows should have risk_score > 0."""
    results = analyze_vendors(test_db)
    if len(results) > 0:
        assert (results["risk_score"] > 0).all()
```

- [ ] **Step 2: Run tests**

Run: `source .venv/bin/activate && pytest backend/tests/test_vendors_analysis.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_vendors_analysis.py
git commit -m "Add vendor concentration analysis tests"
```

---

### Task 8: Test contract analysis

**Files:**
- Create: `backend/tests/test_contracts_analysis.py`
- Reference: `backend/analysis/contracts.py` (function: `analyze_contracts(con) -> pd.DataFrame`)

The contracts module queries `payment_contract_joined` for overspend and `payments` for no-contract high-value. Returns DataFrame with columns: `contract_number`, `vendor_name`, `department_name`, `award_amount`, `total_paid`, `overspend_ratio`, `amount`, `flag_type`, `description`, `risk_score`.

- [ ] **Step 1: Write tests**

Create `backend/tests/test_contracts_analysis.py`:

```python
"""Tests for contract compliance analysis."""

from backend.analysis.contracts import analyze_contracts


def test_contract_analysis_returns_results(test_db):
    """Should flag at least one contract issue."""
    results = analyze_contracts(test_db)
    assert len(results) > 0


def test_contract_overspend_detected(test_db):
    """Contract CT-003 should be flagged as overspent."""
    results = analyze_contracts(test_db)
    overspend_flags = results[results["flag_type"] == "CONTRACT_OVERSPEND"]
    if len(overspend_flags) > 0:
        vendors = overspend_flags["vendor_name"].tolist()
        assert "CONTRACT_VENDOR_C" in vendors


def test_contract_flag_types_valid(test_db):
    """Flag types should be CONTRACT_OVERSPEND or NO_CONTRACT_HIGH_VALUE."""
    results = analyze_contracts(test_db)
    valid_types = {"CONTRACT_OVERSPEND", "NO_CONTRACT_HIGH_VALUE"}
    assert set(results["flag_type"].unique()).issubset(valid_types)


def test_contract_risk_score_positive(test_db):
    """Flagged contracts should have risk_score > 0."""
    results = analyze_contracts(test_db)
    assert (results["risk_score"] > 0).all()
```

- [ ] **Step 2: Run tests**

Run: `source .venv/bin/activate && pytest backend/tests/test_contracts_analysis.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_contracts_analysis.py
git commit -m "Add contract analysis tests"
```

---

### Task 9: Test scoring

**Files:**
- Create: `backend/tests/test_scoring.py`
- Reference: `backend/analysis/scoring.py` (function: `compute_risk_scores(con, all_flags_df) -> dict`)

The scoring module is already run during `test_db` fixture setup. Tests verify the tables it created (`alerts`, `payment_risk_scores`, `vendor_risk_scores`, `department_risk_scores`).

- [ ] **Step 1: Write tests**

Create `backend/tests/test_scoring.py`:

```python
"""Tests for composite risk scoring."""


def test_alerts_table_populated(test_db):
    """compute_risk_scores should create a non-empty alerts table."""
    count = test_db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    assert count > 0, "alerts table should have rows after scoring"


def test_alerts_have_required_columns(test_db):
    """alerts table should have expected columns."""
    cols = [c[0] for c in test_db.execute("DESCRIBE alerts").fetchall()]
    for expected in ["flag_type", "description", "risk_score", "vendor_name"]:
        assert expected in cols, f"Missing column: {expected}"


def test_payment_risk_scores_populated(test_db):
    """payment_risk_scores should have entries for flagged payments."""
    count = test_db.execute("SELECT COUNT(*) FROM payment_risk_scores").fetchone()[0]
    assert count > 0


def test_vendor_risk_scores_populated(test_db):
    """vendor_risk_scores should have entries for flagged vendors."""
    count = test_db.execute("SELECT COUNT(*) FROM vendor_risk_scores").fetchone()[0]
    assert count > 0


def test_risk_scores_in_valid_range(test_db):
    """Composite scores should be non-negative."""
    rows = test_db.execute(
        "SELECT composite_score FROM payment_risk_scores"
    ).fetchall()
    for (score,) in rows:
        assert score >= 0, f"Negative score: {score}"
```

- [ ] **Step 2: Run tests**

Run: `source .venv/bin/activate && pytest backend/tests/test_scoring.py -v`
Expected: All 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_scoring.py
git commit -m "Add risk scoring tests"
```

---

### Task 10: Test categories and purpose inference

**Files:**
- Create: `backend/tests/test_categories.py`
- Create: `backend/tests/test_purpose_inference.py`
- Reference: `backend/analysis/categories.py` (`classify_dv_vendor(vendor_name) -> str`, `analyze_categories(con) -> dict`)
- Reference: `backend/analysis/purpose_inference.py` (`infer_purpose(vendor_name, amount, ...) -> dict`)

- [ ] **Step 1: Write category tests**

Create `backend/tests/test_categories.py`:

```python
"""Tests for spending categorization."""

from backend.analysis.categories import classify_dv_vendor, analyze_categories


def test_classify_dv_vendor_legal():
    """Law firms should be classified as legal."""
    result = classify_dv_vendor("ACME LAW FIRM")
    assert "Legal" in result or "legal" in result.lower()


def test_classify_dv_vendor_pension():
    """Pension funds should be classified as pension."""
    result = classify_dv_vendor("CHICAGO PENSION FUND")
    assert "Pension" in result or "pension" in result.lower()


def test_classify_dv_vendor_unknown():
    """Unknown vendor should get a default category."""
    result = classify_dv_vendor("RANDOM UNKNOWN VENDOR XYZ")
    assert isinstance(result, str)
    assert len(result) > 0


def test_analyze_categories_returns_dict(test_db):
    """analyze_categories should return dict with expected keys."""
    result = analyze_categories(test_db)
    assert isinstance(result, dict)
    assert "by_category" in result
```

- [ ] **Step 2: Write purpose inference tests**

Create `backend/tests/test_purpose_inference.py`:

```python
"""Tests for payment purpose inference."""

from backend.analysis.purpose_inference import infer_purpose


def test_infer_purpose_legal():
    """Legal vendor should return legal purpose."""
    result = infer_purpose("SMITH & JONES LAW FIRM", 50000.0)
    assert result["confidence"] in ("high", "medium", "low")
    assert "Legal" in result["purpose"] or "legal" in result["purpose"].lower()


def test_infer_purpose_pension():
    """Pension fund should return pension purpose."""
    result = infer_purpose("MUNICIPAL PENSION FUND", 1000000.0)
    assert "Pension" in result["purpose"] or "pension" in result["purpose"].lower()


def test_infer_purpose_returns_required_keys():
    """Result should contain purpose, confidence, reasoning, disclaimer."""
    result = infer_purpose("SOME VENDOR", 1000.0)
    for key in ("purpose", "confidence", "reasoning", "disclaimer"):
        assert key in result, f"Missing key: {key}"


def test_infer_purpose_unknown_vendor():
    """Unknown vendor should still return a result with low confidence."""
    result = infer_purpose("XYZZY CORP", 500.0)
    assert isinstance(result["purpose"], str)
```

- [ ] **Step 3: Run tests**

Run: `source .venv/bin/activate && pytest backend/tests/test_categories.py backend/tests/test_purpose_inference.py -v`
Expected: All 8 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_categories.py backend/tests/test_purpose_inference.py
git commit -m "Add category and purpose inference tests"
```

---

### Task 11: Test API routes

**Files:**
- Create: `backend/tests/test_routes.py`
- Reference: All 10 route modules in `backend/api/routes_*.py`

This is the integration test file. Each test uses the `client` fixture (which injects `test_db` via `_test_con`). Tests verify endpoints return 200 and expected JSON keys.

- [ ] **Step 1: Write route tests**

Create `backend/tests/test_routes.py`:

```python
"""Integration tests for all API route endpoints."""


class TestOverviewRoutes:
    def test_overview(self, client):
        resp = client.get("/api/overview/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_spending" in data
        assert "total_payments" in data


class TestPaymentRoutes:
    def test_payments_list(self, client):
        resp = client.get("/api/payments/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "payments" in data
        assert "total" in data

    def test_payments_with_search(self, client):
        resp = client.get("/api/payments/?search=EXTREME")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "payments" in data


class TestVendorRoutes:
    def test_vendors_list(self, client):
        resp = client.get("/api/vendors/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "vendors" in data
        assert "total" in data

    def test_vendor_detail(self, client):
        resp = client.get("/api/vendors/EXTREME_VENDOR_LLC")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data


class TestDepartmentRoutes:
    def test_departments_list(self, client):
        resp = client.get("/api/departments/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "departments" in data

    def test_departments_true_cost(self, client):
        resp = client.get("/api/departments/true-cost")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "departments" in data

    def test_department_detail(self, client):
        resp = client.get("/api/departments/POLICE")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "summary" in data


class TestContractRoutes:
    def test_contracts_summary(self, client):
        resp = client.get("/api/contracts/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_contracts" in data

    def test_contracts_list(self, client):
        resp = client.get("/api/contracts/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "contracts" in data

    def test_repeat_overspenders(self, client):
        resp = client.get("/api/contracts/repeat-overspenders")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "vendors" in data


class TestCategoryRoutes:
    def test_categories(self, client):
        resp = client.get("/api/categories/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "by_category" in data

    def test_direct_vouchers(self, client):
        resp = client.get("/api/categories/direct-vouchers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "by_subcategory" in data


class TestTrendRoutes:
    def test_timeseries(self, client):
        resp = client.get("/api/trends/timeseries")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "series" in data

    def test_yoy(self, client):
        resp = client.get("/api/trends/yoy")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "items" in data

    def test_patterns(self, client):
        resp = client.get("/api/trends/patterns")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "seasonality" in data


class TestAlertRoutes:
    def test_alerts_list(self, client):
        resp = client.get("/api/alerts/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "alerts" in data

    def test_alerts_summary(self, client):
        resp = client.get("/api/alerts/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "by_flag_type" in data


class TestNetworkRoutes:
    def test_address_clusters(self, client):
        resp = client.get("/api/network/address-clusters")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "clusters" in data

    def test_vendor_aliases(self, client):
        resp = client.get("/api/network/vendor-aliases")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "aliases" in data

    def test_network_summary(self, client):
        resp = client.get("/api/network/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "address_clusters" in data


class TestDonationRoutes:
    def test_donations_summary(self, client):
        resp = client.get("/api/donations/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_donations" in data or "message" in data

    def test_donations_red_flags(self, client):
        resp = client.get("/api/donations/red-flags")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "flags" in data or "message" in data
```

- [ ] **Step 2: Run route tests**

Run: `source .venv/bin/activate && pytest backend/tests/test_routes.py -v`
Expected: All tests PASS (some may return empty data, but should return 200 with correct JSON keys)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_routes.py
git commit -m "Add API route integration tests"
```

---

### Task 12: Update CLAUDE.md and run full suite

**Files:**
- Modify: `CLAUDE.md` (testing section)

- [ ] **Step 1: Update CLAUDE.md testing section**

Replace the existing `## Testing` section in CLAUDE.md with:

```markdown
## Testing
```bash
# Run all backend tests
source .venv/bin/activate && pytest

# Run with verbose output
source .venv/bin/activate && pytest -v

# Run a specific test file
source .venv/bin/activate && pytest backend/tests/test_outliers.py

# TypeScript type check
cd frontend && npx tsc --noEmit

# Frontend production build
cd frontend && npm run build

# Python backend import check
source .venv/bin/activate && python -c "from backend.app import create_app; create_app()"
```
```

- [ ] **Step 2: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Run frontend checks too**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "Update CLAUDE.md testing section with pytest commands"
```

---

### Task 13: Fix any test failures

This is a catch-all task. After running the full suite, some tests may fail due to:
- Fixture data not matching analysis module expectations (e.g., thresholds, column names)
- Route endpoints querying columns not present in the test DB
- Analysis functions returning empty DataFrames for the fixture data

For each failure:
1. Read the error message
2. Check the analysis module source to understand what it expects
3. Fix the fixture data or test assertion accordingly
4. Re-run and verify

- [ ] **Step 1: Run full suite and capture output**

Run: `source .venv/bin/activate && pytest -v 2>&1 | head -100`

- [ ] **Step 2: Fix any failures (iterate as needed)**

- [ ] **Step 3: Final green run**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit fixes**

```bash
git add -u
git commit -m "Fix test failures from initial suite run"
```
