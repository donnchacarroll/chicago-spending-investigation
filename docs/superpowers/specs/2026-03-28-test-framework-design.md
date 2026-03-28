# Test Framework Design — Chicago Spending Dashboard

## Overview

Add a pytest-based test framework covering backend analysis modules and API routes. Frontend testing deferred — TypeScript strict mode and build checks provide sufficient coverage for the current thin UI layer.

## Goals

- Catch regressions in analysis logic (outlier detection, duplicate detection, risk scoring, etc.)
- Validate all API endpoints return correct status codes and expected JSON shapes
- Replace the ad-hoc smoke tests in CLAUDE.md with a proper test suite
- Keep it simple — no over-engineering for a single-developer read-only dashboard

## Non-Goals (Deferred)

- Frontend component/interaction tests
- E2E browser tests (Playwright/Cypress)
- Test data factories/generators
- Coverage enforcement

## Dependencies

Add to `requirements.txt`:
```
pytest
pytest-flask
```

## Directory Structure

```
backend/
  tests/
    conftest.py            # Test DB + Flask client fixtures
    fixtures/
      payments.csv         # ~50 rows with known properties
      contracts.csv        # ~10 contracts
      budget_salaries.csv  # ~20 salary records across departments
    test_outliers.py
    test_duplicates.py
    test_splitting.py
    test_vendors_analysis.py
    test_contracts_analysis.py
    test_scoring.py
    test_categories.py
    test_purpose_inference.py
    test_routes.py         # All API route integration tests
pytest.ini
```

Flat structure — no unit/integration subdirectories at this scale.

## Test Database Injection

All route modules use `from backend.api.db import get_db`, which creates a local name binding in each module. Simply patching `backend.api.db.get_db` would not affect these already-imported local names.

**Approach: add a module-level override in `db.py`.**

A small change to `backend/api/db.py`:

```python
_test_con = None  # Set by test fixtures to override the connection

def get_db():
    """Return a thread-local read-only DuckDB connection."""
    if _test_con is not None:
        return _test_con
    if not hasattr(_local, "con") or _local.con is None:
        _local.con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    return _local.con
```

Then in `conftest.py`:

```python
@pytest.fixture
def client(test_db):
    """Flask test client wired to the in-memory test database."""
    import backend.api.db as db_module
    db_module._test_con = test_db
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    db_module._test_con = None
```

One small production code change, one line in conftest, no route file modifications needed.

## Core Fixtures (`conftest.py`)

### `test_db` (session-scoped)

- Creates an in-memory DuckDB connection
- Loads fixture CSVs and creates all tables the app expects
- Runs a simplified enrichment to create `payment_contract_joined` (joins payments + contracts fixtures, adds `spending_category` and `dv_subcategory` columns)
- Runs the analysis modules in order — `detect_outliers(con)`, `detect_duplicates(con)`, `detect_splitting(con)`, `analyze_vendors(con)`, `analyze_contracts(con)` — concatenates their DataFrames into `all_flags_df`, then calls `compute_risk_scores(con, all_flags_df)` to populate `alerts`, `payment_risk_scores`, `vendor_risk_scores`, `department_risk_scores` tables. This validates the full analysis-to-scoring pipeline.
- Creates `budget_salaries` and `dept_salary_totals` tables from salary fixtures
- Creates stub `department_true_cost` and `department_cost_detail` tables
- Session-scoped (created once, shared across all tests) since the analysis modules and routes are read-only queries against it. `compute_risk_scores` writes tables during setup but tests only read them.

### `client` (function-scoped)

- Monkeypatches `get_db` to return `test_db`
- Creates Flask test client from `create_app()`
- Used by all route integration tests

### Required tables in test DB

These tables must exist for the route handlers to work:

| Table | Source | Notes |
|-------|--------|-------|
| `payments` | `fixtures/payments.csv` | Core payment records |
| `contracts` | `fixtures/contracts.csv` | Contract records |
| `payment_contract_joined` | Join of payments + contracts | See column list below |
| `budget_salaries` | `fixtures/budget_salaries.csv` | Annual salary data by department |
| `dept_salary_totals` | Derived from budget_salaries | Aggregated salary totals |
| `salaries` | Stub or small fixture | Current employee snapshot |
| `alerts` | Created by `compute_risk_scores()` | Risk flags |
| `payment_risk_scores` | Created by `compute_risk_scores()` | Per-payment scores |
| `vendor_risk_scores` | Created by `compute_risk_scores()` | Per-vendor scores |
| `department_risk_scores` | Created by `compute_risk_scores()` | Per-dept scores |
| `department_true_cost` | Stub with expected columns | True Cost view data |
| `department_cost_detail` | Stub with expected columns | Cost detail breakdown |
| `donations` | Stub with correct columns | Needs: `matched_vendor`, `amount`, `donor_name`, `donor_employer`, `donor_city`, `donor_state`, `date`, `recipient_committee`, `recipient_id`, `election_cycle`, `match_type`, `source` |

### `payment_contract_joined` minimum columns

This table is queried by most routes. The conftest join must produce at least these columns:

From payments: `voucher_number`, `amount`, `check_date`, `vendor_name`, `department_name`, `department_canonical`, `contract_number`, `contract_type`, `year`, `month`, `quarter`, `is_annual_aggregate`

From contracts join: `contract_type_desc`, `procurement_type`, `award_amount`, `purchase_order_description`

Added by enrichment: `spending_category`, `dv_subcategory`, `total_paid_per_contract`, `overspend_ratio`

The simplest approach: have `conftest.py` reference the real schema by running `DESCRIBE payment_contract_joined` against the production DB during development, then create the fixture table with matching columns.

## Fixture Data

Hand-crafted CSVs in `backend/tests/fixtures/` with known properties for deterministic assertions. Using CSV for all fixtures (consistent with DuckDB's native loading, avoids extra pandas JSON parsing).

### `payments.csv` (~50 rows)

Must include:
- Normal payments (baseline)
- One payment with amount 4+ std devs above mean (outlier detection)
- A duplicate pair (same vendor, amount, date)
- A splitting pattern (multiple payments just under threshold to same vendor)
- Payments across multiple departments, vendors, and dates
- Payments with and without matching contracts
- Column names matching the schema produced by `ingest.py`: `voucher_number`, `amount`, `check_date`, `vendor_name`, `department_name`, `department_canonical`, `contract_number`, `contract_type`, `year`, `is_annual_aggregate`, etc.

### `contracts.csv` (~10 contracts)

Must include:
- Active contract with matching payments (by contract_number)
- Expired contract
- Contract with payments exceeding its value (over-budget)
- Contract with no matching payments
- Columns matching SODA API schema: `contract_number`, `vendor_name`, `amount`, `start_date`, `end_date`, `contract_type_desc`, `procurement_type`, `award_amount`, `department`, `vendor_id`, `address_1`, `city`, `zip`, `purchase_order_contract_number`, `purchase_order_description`

### `budget_salaries.csv` (~20 records)

Must include:
- Records across 3-4 departments matching department names in payments fixtures
- Multiple years (2023, 2024)
- Columns: `department`, `year`, `employee_count`, `total_salary`

## Test Scope

### Analysis Module Tests (8 files)

Each analysis module gets its own test file with tests against fixture data:

| Module | Test File | Key Assertions |
|--------|-----------|----------------|
| `outliers.py` | `test_outliers.py` | Flags high Z-score payment, doesn't flag normal ones |
| `duplicates.py` | `test_duplicates.py` | Finds exact duplicate pair, ignores non-duplicates |
| `splitting.py` | `test_splitting.py` | Detects splitting pattern, ignores legitimate multiple payments |
| `vendors.py` | `test_vendors_analysis.py` | Calculates HHI correctly, flags concentrated spending |
| `contracts.py` | `test_contracts_analysis.py` | Flags expired/over-budget contracts (queries `payment_contract_joined`) |
| `scoring.py` | `test_scoring.py` | Composite score reflects individual flags; verifies `alerts` table is populated |
| `categories.py` | `test_categories.py` | `analyze_categories()` categorizes by `contract_type_desc`; `classify_dv_vendor()` maps vendor names to subcategories |
| `purpose_inference.py` | `test_purpose_inference.py` | `infer_purpose()` returns correct purpose, confidence, and explanation for known vendor patterns |

Each test file should have 3-6 tests covering the happy path and key edge cases.

Note: `scoring.py` (`compute_risk_scores`) writes tables (`alerts`, `*_risk_scores`) to the database. Since the test DB is session-scoped, `compute_risk_scores` runs once during fixture setup. Tests for scoring verify the written tables contain expected data. Tests for other modules read from the already-populated test DB.

### API Route Tests (1 file)

`test_routes.py` covers all 10 route modules. Endpoints grouped by their table dependencies:

**Core endpoints (depend on `payments`, `payment_contract_joined`):**
- `/api/overview/` — returns summary stats
- `/api/payments/` — list with search/filter
- `/api/vendors/` — vendor list and detail
- `/api/categories/` — spending categories
- `/api/trends/` — time-series data

**Risk endpoints (depend on `alerts`, `*_risk_scores`):**
- `/api/alerts/` — risk alert list

**Department endpoints (depend on `budget_salaries`, `department_true_cost`):**
- `/api/departments/` — department stats
- `/api/departments/true-cost` — True Cost view

**Contract endpoints (depend on `contracts`, `payment_contract_joined`):**
- `/api/contracts/` — contract analysis

**Network endpoints:**
- `/api/network/` — vendor clustering

**Donation endpoints (depend on `donations`):**
- `/api/donations/summary` — donation summary

Each endpoint: verify 200 status, check expected top-level JSON keys exist.

## Test Commands

```bash
# Run all tests
pytest

# Run a specific test file
pytest backend/tests/test_outliers.py

# Run with verbose output
pytest -v

# Run just route tests
pytest backend/tests/test_routes.py
```

## `pytest.ini`

```ini
[pytest]
testpaths = backend/tests
python_files = test_*.py
python_functions = test_*
```

## Updated CLAUDE.md Testing Section

Replace the current testing section with:

```bash
# Run all tests
source .venv/bin/activate && pytest

# Run with verbose output
source .venv/bin/activate && pytest -v

# TypeScript type check
cd frontend && npx tsc --noEmit

# Frontend production build
cd frontend && npm run build

# Python backend import check
source .venv/bin/activate && python -c "from backend.app import create_app; create_app()"
```
