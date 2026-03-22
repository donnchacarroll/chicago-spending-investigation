"""Fetch Chicago contracts data from the City Data Portal."""

import pandas as pd

from backend.config import SODA_CONTRACTS, DATA_CACHE
from backend.external.soda_client import fetch_all


CONTRACTS_CACHE_PATH = DATA_CACHE / "contracts.parquet"


def fetch_contracts():
    """
    Fetch contracts from the Chicago Data Portal SODA API.

    Uses the contracts endpoint (rsxa-ify5) and caches as Parquet.
    Cleans the award_amount column to float.

    Returns:
        pd.DataFrame: Contracts data with cleaned award_amount.
    """
    print("Fetching contracts data ...")
    df = fetch_all(
        resource_url=SODA_CONTRACTS,
        cache_path=CONTRACTS_CACHE_PATH,
        max_age_hours=24,
    )

    if df.empty:
        print("  WARNING: No contracts data returned.")
        return df

    # Clean award_amount to float
    if "award_amount" in df.columns:
        df["award_amount"] = (
            df["award_amount"]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df["award_amount"] = pd.to_numeric(df["award_amount"], errors="coerce")
    else:
        print("  WARNING: 'award_amount' column not found in contracts data.")

    print(f"  Contracts loaded: {len(df):,} rows")
    return df
