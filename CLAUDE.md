# CLAUDE.md — Chicago Spending Investigation Dashboard

## Project Overview
Full-stack web application for investigating Chicago city spending, contracts, salaries, and political donation data. Designed to surface inefficient government spending, identify anomalies, and provide transparency into how public funds are used. All payment data is scoped to 2023 and later.

## Superpowers Integration
- Use the Superpowers plugin for non-trivial development work.
- Workflow: brainstorm → plan → implement → review.
- Skip planning only for trivial changes (typo fixes, single-line edits).

## Tech Stack
- **Frontend**: Vite + React 19 + TypeScript + React Router v7
- **Styling**: Tailwind CSS v3 (dark theme, custom dashboard palette)
- **State Management**: React useState/useEffect (no external state library)
- **Backend**: Flask (Python 3.9) + Flask-CORS
- **Database**: DuckDB (file-based, rebuilt from ETL pipeline)
- **Data Sources**: Chicago Data Portal SODA API (payments CSV, contracts, salaries, budget ordinance), FEC API (political donations)
- **ETL**: Custom Python pipeline (`backend/etl/build_db.py`) — ingests CSV, fetches APIs, enriches, runs analysis, builds DuckDB
- **Caching**: Parquet files in `backend/data/cache/`
- **No authentication** — public-facing read-only dashboard

## Project Structure
```
├── backend/
│   ├── app.py                    # Flask app factory
│   ├── config.py                 # Paths, API URLs, thresholds
│   ├── api/
│   │   ├── db.py                 # DuckDB connection management
│   │   ├── routes_overview.py    # Dashboard summary
│   │   ├── routes_payments.py    # Payment search/detail
│   │   ├── routes_vendors.py     # Vendor analysis
│   │   ├── routes_departments.py # Department stats + True Cost
│   │   ├── routes_contracts.py   # Contract analysis
│   │   ├── routes_categories.py  # Spending categories
│   │   ├── routes_trends.py      # Time-series data
│   │   ├── routes_alerts.py      # Risk alerts
│   │   ├── routes_network.py     # Vendor network analysis
│   │   └── routes_donations.py   # Political donation matching
│   ├── etl/
│   │   ├── build_db.py           # Main ETL orchestrator
│   │   ├── ingest.py             # CSV parsing + cleaning
│   │   └── enrich.py             # Payment-contract joining
│   ├── external/
│   │   ├── soda_client.py        # SODA API client with caching
│   │   ├── fetch_contracts.py    # Contract data fetcher
│   │   ├── fetch_salaries.py     # Current salary snapshot
│   │   ├── fetch_budget_salaries.py  # Annual budget ordinance data
│   │   └── fetch_donations.py    # FEC donation data
│   ├── analysis/
│   │   ├── outliers.py           # Z-score outlier detection
│   │   ├── duplicates.py         # Duplicate payment detection
│   │   ├── splitting.py          # Payment splitting detection
│   │   ├── vendors.py            # Vendor concentration (HHI)
│   │   ├── contracts.py          # Contract compliance checks
│   │   ├── scoring.py            # Composite risk scoring
│   │   ├── categories.py         # Spending categorization
│   │   └── purpose_inference.py  # Payment purpose inference
│   └── data/
│       ├── cache/                # Parquet caches (gitignored)
│       └── processed/            # Processed data (gitignored)
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Router setup
│   │   ├── components/
│   │   │   ├── Layout.tsx        # Sidebar nav + date filter
│   │   │   ├── DataTable.tsx     # Reusable sortable table
│   │   │   └── RiskBadge.tsx     # Risk score display
│   │   ├── lib/
│   │   │   ├── api.ts            # API client + TypeScript types
│   │   │   ├── formatters.ts     # Currency/number formatting
│   │   │   └── DateFilterContext.tsx  # Global date filter state
│   │   └── pages/                # One file per tab
│   └── package.json
├── spending.duckdb               # Built database (gitignored, rebuilt by ETL)
├── chicago_payments.csv          # Source payment data (Chicago Data Portal export)
├── requirements.txt              # Python dependencies
└── .env                          # FEC_API_KEY (gitignored)
```

## Setup (from scratch)
```bash
# 1. Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Frontend
cd frontend && npm install && cd ..

# 3. Environment variables
#    Create .env in project root:
#    FEC_API_KEY=<your key from https://api.open.fec.gov/developers/>
#    (Optional — donation tab works without it but may be rate-limited)

# 4. Source data
#    chicago_payments.csv is included in the repo (33MB).
#    Originally exported from the Chicago Data Portal "Payments" dataset.
#    The ETL also fetches contracts, salaries, and budget data from the
#    SODA API at build time — no manual download needed for those.

# 5. Build the database
source .venv/bin/activate
python backend/etl/build_db.py       # ~2-5 min, fetches APIs + builds DuckDB

# 6. Run the app (two terminals)
python -m backend.app                 # Flask API on http://localhost:5001
cd frontend && npm run dev            # Vite dev on http://localhost:5173
```

## Development Commands
```bash
# Backend
source .venv/bin/activate
python backend/etl/build_db.py       # Rebuild database from scratch (~2-5 min)
python -m backend.app                 # Run Flask API (port 5001)

# Frontend
cd frontend
npm run dev                           # Vite dev server (port 5173, proxies API to 5001)
npm run build                         # Production build
npx tsc --noEmit                      # Type check
```

## Testing
When asked to run tests, run all of these checks:
```bash
# 1. Run all backend tests
source .venv/bin/activate && pytest

# 2. Run with verbose output
source .venv/bin/activate && pytest -v

# 3. Run a specific test file
source .venv/bin/activate && pytest backend/tests/test_outliers.py

# 4. TypeScript type check
cd frontend && npx tsc --noEmit

# 5. Frontend production build
cd frontend && npm run build

# 6. Python backend import check
source .venv/bin/activate && python -c "from backend.app import create_app; create_app()"
```

## Ports
- **5001**: Flask API backend
- **5173**: Vite frontend dev server (proxies `/api` to 5001 in dev mode)

## Key Concepts
- **True Cost View**: Allocates city-wide costs to departments using three tiers: confirmed (tagged payments), attributed (pension funds, single-dept vendors), estimated (shared costs by headcount). See Data Notes tab for full methodology.
- **Budget Salaries**: Annual salary data from Budget Ordinance datasets (2023-2025) + current employee snapshot (2026). These are budgeted positions, not actual payroll.
- **Risk Scoring**: Statistical anomaly detection (outliers, duplicates, splitting, concentration). Flags are indicators, not fraud conclusions.
- **Date Filtering**: Global date filter in sidebar applies to payment-based views. True Cost view has its own year selector.

## Coding Standards
- TypeScript strict mode, no `any`.
- Dark theme UI with Tailwind utility classes.
- API routes return JSON, use `_safe_query()` helper for DuckDB queries.
- DuckDB uses parameterized queries (`$1`, `$2`) — never string interpolation for user input.
- Frontend pages are self-contained single-file components.
- All data is read-only — no mutations, no auth.

## Data Integrity Notes
See the "Data Notes" tab in the app (`/methodology`) for comprehensive documentation of all caveats, approximations, estimates, and unknowns in the data analysis, plus recommendations for the city.