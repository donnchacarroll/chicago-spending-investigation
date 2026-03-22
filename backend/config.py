"""Configuration for the Chicago Spending Investigation App."""

from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = Path(__file__).parent
DATA_RAW = BACKEND_DIR / "data" / "raw"
DATA_PROCESSED = BACKEND_DIR / "data" / "processed"
DATA_CACHE = BACKEND_DIR / "data" / "cache"
DUCKDB_PATH = PROJECT_ROOT / "spending.duckdb"
CSV_PATH = PROJECT_ROOT / "chicago_payments.csv"

# Ensure directories exist
DATA_RAW.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
DATA_CACHE.mkdir(parents=True, exist_ok=True)

# Chicago Data Portal SODA API
SODA_BASE = "https://data.cityofchicago.org/resource"
SODA_CONTRACTS = f"{SODA_BASE}/rsxa-ify5.json"
SODA_VENDORS = f"{SODA_BASE}/qzds-jfc2.json"
SODA_SALARIES = f"{SODA_BASE}/xzkq-xp2w.json"
SODA_TIF = f"{SODA_BASE}/umwj-yc4m.json"
SODA_PAGE_SIZE = 50000

# Analysis thresholds
OUTLIER_ZSCORE_THRESHOLD = 3.0
MIN_PAYMENTS_FOR_ZSCORE = 5
SPLITTING_THRESHOLDS = [10_000, 25_000, 50_000, 100_000]
SPLITTING_WINDOW_DAYS = 7
DUPLICATE_NEAR_DAYS = 3
CONTRACT_OVERSPEND_THRESHOLD = 0.10  # 10%
NO_CONTRACT_HIGH_VALUE = 25_000

# Risk score weights
RISK_WEIGHTS = {
    "outlier": 0.25,
    "duplicate": 0.20,
    "splitting": 0.20,
    "contract_overspend": 0.20,
    "vendor_concentration": 0.15,
}
