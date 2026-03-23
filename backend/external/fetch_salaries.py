"""Fetch Chicago employee salary data from the City Data Portal."""

import pandas as pd

from backend.config import SODA_SALARIES, DATA_CACHE
from backend.external.soda_client import fetch_all


SALARIES_CACHE_PATH = DATA_CACHE / "salaries.parquet"


def fetch_salaries():
    """
    Fetch employee salaries from the Chicago Data Portal SODA API.

    Uses the salaries endpoint (xzkq-xp2w) and caches as Parquet.
    Cleans the annual_salary column to float.

    Returns:
        pd.DataFrame: Salary data with cleaned annual_salary.
    """
    print("Fetching salary data ...")
    df = fetch_all(
        resource_url=SODA_SALARIES,
        cache_path=SALARIES_CACHE_PATH,
        max_age_hours=24,
    )

    if df.empty:
        print("  WARNING: No salary data returned.")
        return df

    # Clean annual_salary to float
    if "annual_salary" in df.columns:
        df["annual_salary"] = (
            df["annual_salary"]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        df["annual_salary"] = pd.to_numeric(df["annual_salary"], errors="coerce")
    else:
        print("  WARNING: 'annual_salary' column not found in salary data.")

    # Normalize department names to upper case for consistent matching
    if "department" in df.columns:
        df["department"] = df["department"].astype(str).str.strip().str.upper()

    print(f"  Salaries loaded: {len(df):,} rows")
    return df
