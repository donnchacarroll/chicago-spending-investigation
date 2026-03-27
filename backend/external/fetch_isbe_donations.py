"""Fetch Illinois State Board of Elections campaign contribution data."""

import re
import time
import pandas as pd
import requests
from pathlib import Path

from backend.config import DATA_CACHE

ISBE_BASE = "https://elections.il.gov/campaigndisclosuredatafiles"
ISBE_CACHE_DIR = DATA_CACHE / "isbe"

# Minimum year for receipts (matches our 2023+ data scope)
MIN_YEAR = 2023


def _download_isbe_file(filename, cache_path, max_age_hours=168):
    """Download a tab-delimited file from ISBE, with caching."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            print(f"  Cache hit: {cache_path.name} ({age_hours:.1f}h old)")
            return cache_path

    url = f"{ISBE_BASE}/{filename}"
    print(f"  Downloading {url} ...")
    r = requests.get(url, timeout=300, stream=True)
    r.raise_for_status()

    with open(cache_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

    size_mb = cache_path.stat().st_size / 1e6
    print(f"  Downloaded {size_mb:.1f} MB -> {cache_path}")
    return cache_path


def _load_committees():
    """Load and cache the ISBE committees lookup."""
    parquet_path = ISBE_CACHE_DIR / "committees.parquet"

    if parquet_path.exists():
        age_hours = (time.time() - parquet_path.stat().st_mtime) / 3600
        if age_hours < 168:
            return pd.read_parquet(parquet_path)

    txt_path = _download_isbe_file("Committees.txt", ISBE_CACHE_DIR / "Committees.txt")
    df = pd.read_csv(txt_path, sep="\t", dtype=str, on_bad_lines="skip", encoding="latin-1")
    # Keep only the columns we need
    df = df[["ID", "Name"]].rename(columns={"ID": "committee_id", "Name": "committee_name"})
    df.to_parquet(parquet_path, index=False)
    print(f"  Committees: {len(df):,} records")

    # Remove raw text file
    if txt_path.exists():
        txt_path.unlink()
        print(f"  Cleaned up raw Committees.txt")

    return df


def _load_receipts_filtered():
    """Load ISBE receipts, filtered to MIN_YEAR+, and cache as parquet."""
    parquet_path = ISBE_CACHE_DIR / f"receipts_{MIN_YEAR}_plus.parquet"

    if parquet_path.exists():
        age_hours = (time.time() - parquet_path.stat().st_mtime) / 3600
        if age_hours < 168:
            print(f"  Cache hit: {parquet_path.name} ({age_hours:.1f}h old)")
            return pd.read_parquet(parquet_path)

    txt_path = _download_isbe_file("Receipts.txt", ISBE_CACHE_DIR / "Receipts.txt")

    print(f"  Parsing receipts (filtering to {MIN_YEAR}+) ...")
    # Read in chunks to handle large file
    chunks = []
    cols_to_use = [
        "ID", "CommitteeID", "LastOnlyName", "FirstName",
        "RcvDate", "Amount", "Occupation", "Employer",
        "City", "State", "Zip",
    ]

    for chunk in pd.read_csv(
        txt_path, sep="\t", dtype=str, on_bad_lines="skip",
        usecols=cols_to_use, chunksize=100_000,
        encoding="latin-1",
    ):
        # Parse date and filter by year
        chunk["RcvDate"] = pd.to_datetime(chunk["RcvDate"], errors="coerce")
        chunk = chunk[chunk["RcvDate"].dt.year >= MIN_YEAR]
        if not chunk.empty:
            chunks.append(chunk)

    if not chunks:
        print(f"  WARNING: No receipts found for {MIN_YEAR}+")
        return pd.DataFrame()

    df = pd.concat(chunks, ignore_index=True)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

    # Clean up
    df = df.rename(columns={
        "LastOnlyName": "last_name",
        "FirstName": "first_name",
        "CommitteeID": "committee_id",
        "RcvDate": "date",
        "Amount": "amount",
        "Occupation": "occupation",
        "Employer": "employer",
        "City": "city",
        "State": "state",
    })

    df.to_parquet(parquet_path, index=False)
    print(f"  Receipts ({MIN_YEAR}+): {len(df):,} records, ${df['amount'].sum()/1e6:.1f}M total")

    # Remove raw text file to save disk space
    if txt_path.exists():
        size_mb = txt_path.stat().st_size / 1e6
        txt_path.unlink()
        print(f"  Cleaned up raw Receipts.txt ({size_mb:.0f} MB)")

    return df


def _clean_vendor_name(vendor):
    """Simplify vendor name for matching."""
    clean = re.sub(
        r'\b(LLC|INC|CORP|LTD|CO\.|COMPANY|L\.P\.|LP|NFP|CORPORATION|INCORPORATED)\b\.?',
        '', vendor, flags=re.IGNORECASE
    ).strip().rstrip(',').rstrip('.')
    return re.sub(r'\s+', ' ', clean).strip().upper()


def fetch_isbe_vendor_donations(vendor_names, max_vendors=50):
    """
    Match ISBE campaign contributions against a list of vendor names.

    Searches by both donor name (LastOnlyName) and employer.
    Returns a DataFrame matching the FEC donations schema.
    """
    print("  Loading ISBE data ...")
    receipts = _load_receipts_filtered()
    if receipts.empty:
        return pd.DataFrame()

    committees = _load_committees()
    comm_lookup = dict(zip(committees["committee_id"], committees["committee_name"]))

    # Uppercase columns for matching
    receipts["last_name_upper"] = receipts["last_name"].fillna("").str.upper()
    receipts["employer_upper"] = receipts["employer"].fillna("").str.upper()

    all_donations = []

    for i, vendor in enumerate(vendor_names[:max_vendors]):
        clean = _clean_vendor_name(vendor)
        if len(clean) < 3:
            continue

        # Search by donor name (company donations)
        name_matches = receipts[receipts["last_name_upper"].str.contains(clean, na=False, regex=False)]

        for _, row in name_matches.iterrows():
            all_donations.append({
                "donor_name": f"{row.get('last_name', '')} {row.get('first_name', '')}".strip(),
                "donor_employer": row.get("employer", ""),
                "donor_city": row.get("city", ""),
                "donor_state": row.get("state", ""),
                "amount": row.get("amount", 0),
                "date": str(row["date"].date()) if pd.notna(row.get("date")) else "",
                "recipient_committee": comm_lookup.get(str(row.get("committee_id", "")), ""),
                "recipient_id": str(row.get("committee_id", "")),
                "election_cycle": row["date"].year if pd.notna(row.get("date")) else None,
                "matched_vendor": vendor,
                "match_type": "company_name",
                "source": "isbe",
            })

        # Search by employer (employee donations)
        emp_matches = receipts[receipts["employer_upper"].str.contains(clean, na=False, regex=False)]

        for _, row in emp_matches.iterrows():
            all_donations.append({
                "donor_name": f"{row.get('last_name', '')} {row.get('first_name', '')}".strip(),
                "donor_employer": row.get("employer", ""),
                "donor_city": row.get("city", ""),
                "donor_state": row.get("state", ""),
                "amount": row.get("amount", 0),
                "date": str(row["date"].date()) if pd.notna(row.get("date")) else "",
                "recipient_committee": comm_lookup.get(str(row.get("committee_id", "")), ""),
                "recipient_id": str(row.get("committee_id", "")),
                "election_cycle": row["date"].year if pd.notna(row.get("date")) else None,
                "matched_vendor": vendor,
                "match_type": "employer",
                "source": "isbe",
            })

        if (i + 1) % 10 == 0:
            print(f"    ISBE: Processed {i + 1}/{min(len(vendor_names), max_vendors)} vendors "
                  f"({len(all_donations):,} matches so far) ...")

    if all_donations:
        df = pd.DataFrame(all_donations)
        # Deduplicate (same receipt matched by both name and employer)
        df = df.drop_duplicates(subset=["donor_name", "amount", "date", "recipient_id", "matched_vendor"])
        return df

    return pd.DataFrame()
