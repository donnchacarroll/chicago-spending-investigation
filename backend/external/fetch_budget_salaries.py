"""Fetch Chicago Budget Ordinance salary data by year from the City Data Portal."""

import pandas as pd

from backend.config import SODA_BASE, DATA_CACHE, SODA_SALARIES
from backend.external.soda_client import fetch_all


# Budget Ordinance - Positions and Salaries dataset IDs by year
BUDGET_DATASETS = {
    2023: "pkjy-hzin",
    2024: "jeta-egyx",
    2025: "2bp7-w85v",
}

BUDGET_CACHE_DIR = DATA_CACHE / "budget_salaries"


def fetch_budget_salaries():
    """
    Fetch budget ordinance salary data for 2023-2025 and current salary
    snapshot for 2026. Returns a single DataFrame with columns:
    year, department, employee_count, total_salary.
    """
    all_years = []

    for year, dataset_id in BUDGET_DATASETS.items():
        print(f"  Fetching {year} budget ordinance ...")
        url = f"{SODA_BASE}/{dataset_id}.json"
        cache_path = BUDGET_CACHE_DIR / f"budget_{year}.parquet"

        df = fetch_all(
            resource_url=url,
            cache_path=cache_path,
            max_age_hours=168,  # weekly refresh
        )

        if df.empty:
            print(f"  WARNING: No budget data for {year}")
            continue

        # Aggregate by department
        dept_col = "department_description"
        if dept_col not in df.columns:
            # Older datasets may use different column names
            for alt in ["department", "department_name"]:
                if alt in df.columns:
                    dept_col = alt
                    break

        df["total_budgeted_amount"] = pd.to_numeric(
            df["total_budgeted_amount"].astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False),
            errors="coerce",
        )
        df["total_budgeted_unit"] = pd.to_numeric(df["total_budgeted_unit"], errors="coerce")

        # For employee count: only count Annual positions (Hourly rows have hours, not people)
        # Use total_budgeted_unit for Annual rows, count rows for Hourly
        if "budgeted_unit" in df.columns:
            annual = df[df["budgeted_unit"].str.strip().str.lower() == "annual"]
            hourly = df[df["budgeted_unit"].str.strip().str.lower() == "hourly"]
            annual_counts = annual.groupby(dept_col)["total_budgeted_unit"].sum()
            hourly_counts = hourly.groupby(dept_col).size()
            emp_counts = annual_counts.add(hourly_counts, fill_value=0).astype(int)
        else:
            emp_counts = df.groupby(dept_col)["total_budgeted_unit"].sum()

        salary_totals = df.groupby(dept_col)["total_budgeted_amount"].sum()

        dept_agg = pd.DataFrame({
            "employee_count": emp_counts,
            "total_salary": salary_totals,
        }).reset_index().rename(columns={dept_col: "department"})
        dept_agg["department"] = dept_agg["department"].str.strip().str.upper()
        dept_agg["year"] = year

        all_years.append(dept_agg)
        print(f"    {year}: {len(dept_agg)} departments, ${dept_agg['total_salary'].sum()/1e6:.1f}M total")

    # 2026: Fall back to current salary snapshot
    print("  Fetching current salary snapshot for 2026 ...")
    current_cache = DATA_CACHE / "salaries.parquet"
    current_df = fetch_all(
        resource_url=SODA_SALARIES,
        cache_path=current_cache,
        max_age_hours=24,
    )

    if not current_df.empty and "annual_salary" in current_df.columns:
        current_df["annual_salary"] = pd.to_numeric(
            current_df["annual_salary"].astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False),
            errors="coerce",
        )
        if "department" in current_df.columns:
            current_df["department"] = current_df["department"].str.strip().str.upper()
            dept_2026 = (
                current_df.groupby("department")
                .agg(
                    employee_count=("annual_salary", "count"),
                    total_salary=("annual_salary", "sum"),
                )
                .reset_index()
            )
            dept_2026["year"] = 2026
            all_years.append(dept_2026)
            print(f"    2026: {len(dept_2026)} departments, ${dept_2026['total_salary'].sum()/1e6:.1f}M total")

    if all_years:
        result = pd.concat(all_years, ignore_index=True)
    else:
        result = pd.DataFrame(columns=["year", "department", "employee_count", "total_salary"])

    return result[["year", "department", "employee_count", "total_salary"]]
