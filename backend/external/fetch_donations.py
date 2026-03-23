"""Fetch political donation data from the FEC API."""
import time
import re
import os
import requests
import pandas as pd
from pathlib import Path
from backend.config import DATA_CACHE

FEC_BASE = "https://api.open.fec.gov/v1"
FEC_KEY = "DEMO_KEY"
CACHE_DIR = DATA_CACHE / "donations"


def search_fec_donations(search_term, search_type="name", per_page=100, max_pages=3):
    """Search FEC for donations by contributor name or employer.

    search_type: "name" searches contributor_name, "employer" searches contributor_employer
    Returns list of donation dicts.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{search_type}_{search_term.replace(' ', '_')[:50]}.parquet"

    # Check cache (24h)
    if cache_file.exists():
        age_hours = (time.time() - os.path.getmtime(cache_file)) / 3600
        if age_hours < 24:
            return pd.read_parquet(cache_file).to_dict('records')

    all_results = []
    params = {
        "api_key": FEC_KEY,
        "per_page": per_page,
        "sort": "-contribution_receipt_amount",
    }
    if search_type == "name":
        params["contributor_name"] = search_term
    else:
        params["contributor_employer"] = search_term
        params["contributor_state"] = "IL"  # Focus on Illinois

    for page_num in range(1, max_pages + 1):
        try:
            r = requests.get(f"{FEC_BASE}/schedules/schedule_a/", params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2)
                continue
            if r.status_code != 200:
                break
            data = r.json()
            results = data.get("results", [])
            if not results:
                break
            for item in results:
                all_results.append({
                    "donor_name": item.get("contributor_name", ""),
                    "donor_employer": item.get("contributor_employer", ""),
                    "donor_city": item.get("contributor_city", ""),
                    "donor_state": item.get("contributor_state", ""),
                    "amount": item.get("contribution_receipt_amount", 0),
                    "date": item.get("contribution_receipt_date", ""),
                    "recipient_committee": item.get("committee", {}).get("name", ""),
                    "recipient_id": item.get("committee", {}).get("committee_id", ""),
                    "election_cycle": item.get("two_year_transaction_period", ""),
                })
            # Check if there are more pages
            pagination = data.get("pagination", {})
            if not pagination.get("pages") or page_num >= pagination.get("pages", 1):
                break
            params["last_index"] = pagination.get("last_indexes", {}).get("last_index")
            params["last_contribution_receipt_amount"] = pagination.get("last_indexes", {}).get("last_contribution_receipt_amount")
            time.sleep(0.5)  # Be nice to the API
        except Exception:
            break

    # Cache results
    if all_results:
        df = pd.DataFrame(all_results)
        df.to_parquet(cache_file, index=False)

    return all_results


def fetch_vendor_donations(vendor_names, max_vendors=50):
    """Fetch donations for a list of vendor names.

    Searches by both company name and employer name.
    Returns a DataFrame with all found donations plus the matched vendor.
    """
    all_donations = []

    for i, vendor in enumerate(vendor_names[:max_vendors]):
        # Simplify vendor name for search (remove LLC, INC, etc.)
        clean = re.sub(
            r'\b(LLC|INC|CORP|LTD|CO\.|COMPANY|L\.P\.|LP|NFP)\b\.?',
            '', vendor, flags=re.IGNORECASE
        ).strip().rstrip(',').rstrip('.')
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) < 3:
            continue

        # Search by company name
        results = search_fec_donations(clean, search_type="name", max_pages=2)
        for r in results:
            r["matched_vendor"] = vendor
            r["match_type"] = "company_name"
        all_donations.extend(results)

        # Also search by employer (finds individual employees who donated)
        emp_results = search_fec_donations(clean, search_type="employer", max_pages=1)
        for r in emp_results:
            r["matched_vendor"] = vendor
            r["match_type"] = "employer"
        all_donations.extend(emp_results)

        if (i + 1) % 10 == 0:
            print(f"    Processed {i + 1}/{min(len(vendor_names), max_vendors)} vendors...")

        time.sleep(0.3)  # Rate limiting

    if all_donations:
        return pd.DataFrame(all_donations)
    return pd.DataFrame()
