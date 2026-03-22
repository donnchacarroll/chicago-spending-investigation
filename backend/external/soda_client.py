"""Generic SODA API client with pagination and Parquet caching."""

import time
from pathlib import Path

import pandas as pd
import requests

from backend.config import SODA_PAGE_SIZE


def fetch_all(resource_url, cache_path, max_age_hours=24):
    """
    Fetch all records from a SODA API endpoint with pagination.

    Uses $limit/$offset paging with SODA_PAGE_SIZE (50,000) per request.
    Results are cached as Parquet; if the cache is fresh, returns cached data.

    Args:
        resource_url: Full SODA API endpoint URL (e.g. https://data.cityofchicago.org/resource/xxxx-yyyy.json).
        cache_path: Path (str or Path) where the Parquet cache will be stored.
        max_age_hours: Maximum age of cache in hours before re-fetching. Default 24.

    Returns:
        pd.DataFrame with all records from the endpoint.
    """
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # Check cache freshness
    if cache_path.exists():
        age_seconds = time.time() - cache_path.stat().st_mtime
        age_hours = age_seconds / 3600
        if age_hours < max_age_hours:
            print(f"  Cache hit: {cache_path} ({age_hours:.1f}h old, limit {max_age_hours}h)")
            return pd.read_parquet(cache_path)
        else:
            print(f"  Cache stale: {cache_path} ({age_hours:.1f}h old, limit {max_age_hours}h)")

    # Paginated fetch
    all_records = []
    offset = 0
    limit = SODA_PAGE_SIZE

    print(f"  Fetching from {resource_url} ...")

    while True:
        params = {
            "$limit": limit,
            "$offset": offset,
        }
        response = requests.get(resource_url, params=params, timeout=120)
        response.raise_for_status()
        batch = response.json()

        if not batch:
            break

        all_records.extend(batch)
        print(f"    Fetched {len(all_records):,} records so far (offset={offset}) ...")
        offset += limit

        # If we got fewer than the limit, we've reached the end
        if len(batch) < limit:
            break

    print(f"  Total records fetched: {len(all_records):,}")

    if not all_records:
        df = pd.DataFrame()
    else:
        df = pd.DataFrame(all_records)

    # Cache as Parquet
    df.to_parquet(cache_path, index=False, engine="pyarrow")
    print(f"  Cached to {cache_path}")

    return df
