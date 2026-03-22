"""Trends analysis routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db

trends_bp = Blueprint("trends_bp", __name__, url_prefix="/api/trends")

MONTH_LABELS = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

DIMENSION_COLUMNS = {
    "category": "COALESCE(spending_category, 'Uncategorized / Direct Voucher')",
    "department": "COALESCE(department_canonical, 'Unknown')",
    "procurement": "COALESCE(procurement_type, 'Unknown')",
    "dv_subcategory": "COALESCE(dv_subcategory, 'Unclassified')",
    "vendor": "COALESCE(vendor_name, 'Unknown')",
    "dv_vendor": "COALESCE(vendor_name, 'Unknown')",
}


def _safe_query(sql, params=None):
    """Execute a query and return results as list of dicts, or empty on error."""
    try:
        con = get_db()
        if params:
            result = con.execute(sql, params)
        else:
            result = con.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []


def _build_date_filter(start_date, end_date, prefix=""):
    """Build date filter conditions and params list."""
    col = f"{prefix}check_date" if prefix else "check_date"
    conditions = ""
    params = []
    param_idx = 1
    if start_date:
        conditions += f" AND {col} >= CAST(${param_idx} AS TIMESTAMP)"
        params.append(start_date)
        param_idx += 1
    if end_date:
        conditions += f" AND {col} <= CAST(${param_idx} AS TIMESTAMP)"
        params.append(end_date)
        param_idx += 1
    return conditions, params


def _get_dimension_col(dimension):
    """Return the SQL column expression for a dimension, defaulting to category."""
    return DIMENSION_COLUMNS.get(dimension, DIMENSION_COLUMNS["category"])


def _get_dimension_extra_filter(dimension):
    """Return extra WHERE clause needed for certain dimensions."""
    if dimension in ("dv_subcategory", "dv_vendor"):
        return " AND contract_type = 'direct_voucher'"
    return ""


def _serialize_rows(rows):
    """Convert any date/datetime values in rows to strings for JSON."""
    for row in rows:
        for key, val in row.items():
            if hasattr(val, "isoformat"):
                row[key] = val.isoformat()
    return rows


@trends_bp.route("/timeseries", methods=["GET"])
def timeseries():
    """Return monthly spending broken down by the selected dimension."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    dimension = request.args.get("dimension", "category")
    top_n = int(request.args.get("top_n", "8"))

    date_conditions, date_params = _build_date_filter(start_date, end_date)
    dim_col = _get_dimension_col(dimension)
    dim_filter = _get_dimension_extra_filter(dimension)

    # Step 1: Get top N items by total spending
    top_items = _safe_query(
        f"""
        SELECT
            {dim_col} AS name,
            SUM(amount) AS total
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{dim_filter}{date_conditions}
        GROUP BY 1
        ORDER BY total DESC
        LIMIT {top_n}
        """,
        date_params if date_params else None,
    )

    top_names = [row["name"] for row in top_items]
    totals_by_name = {row["name"]: float(row["total"]) for row in top_items}

    if not top_names:
        return jsonify({
            "dimension": dimension,
            "series": [],
            "monthly_totals": [],
        })

    # Step 2: Get monthly data for each top item
    # Build IN clause with parameterized values
    in_start = len(date_params) + 1
    in_placeholders = ", ".join(f"${in_start + i}" for i in range(len(top_names)))
    monthly_params = list(date_params) + top_names

    monthly_data = _safe_query(
        f"""
        SELECT
            {dim_col} AS name,
            EXTRACT(YEAR FROM check_date)::INT AS year,
            EXTRACT(MONTH FROM check_date)::INT AS month,
            SUM(amount) AS amount,
            COUNT(*) AS count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{dim_filter}{date_conditions}
          AND {dim_col} IN ({in_placeholders})
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
        """,
        monthly_params,
    )

    # Organize into series
    series_map = {}
    for row in monthly_data:
        name = row["name"]
        if name not in series_map:
            series_map[name] = []
        series_map[name].append({
            "year": int(row["year"]),
            "month": int(row["month"]),
            "amount": float(row["amount"]),
            "count": int(row["count"]),
        })

    series = []
    for item in top_items:
        name = item["name"]
        series.append({
            "name": name,
            "data": series_map.get(name, []),
            "total": totals_by_name.get(name, 0),
        })

    # Step 3: Overall monthly totals
    monthly_totals_raw = _safe_query(
        f"""
        SELECT
            EXTRACT(YEAR FROM check_date)::INT AS year,
            EXTRACT(MONTH FROM check_date)::INT AS month,
            SUM(amount) AS amount,
            COUNT(*) AS count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{dim_filter}{date_conditions}
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        date_params if date_params else None,
    )

    monthly_totals = [
        {
            "year": int(r["year"]),
            "month": int(r["month"]),
            "amount": float(r["amount"]),
            "count": int(r["count"]),
        }
        for r in monthly_totals_raw
    ]

    return jsonify({
        "dimension": dimension,
        "series": series,
        "monthly_totals": monthly_totals,
    })


@trends_bp.route("/yoy", methods=["GET"])
def yoy():
    """Year-over-year comparison by the selected dimension."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    dimension = request.args.get("dimension", "category")
    top_n = int(request.args.get("top_n", "8"))

    date_conditions, date_params = _build_date_filter(start_date, end_date)
    dim_col = _get_dimension_col(dimension)
    dim_filter = _get_dimension_extra_filter(dimension)

    # Get available years
    years_raw = _safe_query(
        f"""
        SELECT DISTINCT EXTRACT(YEAR FROM check_date)::INT AS year
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{dim_filter}{date_conditions}
        ORDER BY year
        """,
        date_params if date_params else None,
    )
    years = [int(r["year"]) for r in years_raw]

    if not years:
        return jsonify({
            "dimension": dimension,
            "years": [],
            "items": [],
        })

    # Get top N items by total spending
    top_items = _safe_query(
        f"""
        SELECT
            {dim_col} AS name,
            SUM(amount) AS total
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{dim_filter}{date_conditions}
        GROUP BY 1
        ORDER BY total DESC
        LIMIT {top_n}
        """,
        date_params if date_params else None,
    )

    top_names = [row["name"] for row in top_items]

    if not top_names:
        return jsonify({
            "dimension": dimension,
            "years": years,
            "items": [],
        })

    # Get yearly data for top items
    in_start = len(date_params) + 1
    in_placeholders = ", ".join(f"${in_start + i}" for i in range(len(top_names)))
    yearly_params = list(date_params) + top_names

    yearly_data = _safe_query(
        f"""
        SELECT
            {dim_col} AS name,
            EXTRACT(YEAR FROM check_date)::INT AS year,
            SUM(amount) AS amount
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{dim_filter}{date_conditions}
          AND {dim_col} IN ({in_placeholders})
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        yearly_params,
    )

    # Organize by item
    yearly_map = {}
    for row in yearly_data:
        name = row["name"]
        if name not in yearly_map:
            yearly_map[name] = {}
        yearly_map[name][str(int(row["year"]))] = float(row["amount"])

    # Determine the two most recent full years for YoY calculation
    # (exclude the latest year if it might be partial)
    full_years = sorted(years)

    items = []
    for top_row in top_items:
        name = top_row["name"]
        by_year = yearly_map.get(name, {})
        total = float(top_row["total"])

        # Calculate YoY change between the two most recent full years
        yoy_change_pct = None
        is_new = False
        if len(full_years) >= 2:
            latest_yr = str(full_years[-1])
            prior_yr = str(full_years[-2])
            latest_val = by_year.get(latest_yr, 0)
            prior_val = by_year.get(prior_yr, 0)
            if prior_val and prior_val != 0:
                yoy_change_pct = round(
                    ((latest_val - prior_val) / prior_val) * 100, 1
                )
            elif latest_val > 0 and (not prior_val or prior_val == 0):
                is_new = True

        items.append({
            "name": name,
            "by_year": by_year,
            "total": total,
            "yoy_change_pct": yoy_change_pct,
            "is_new": is_new,
        })

    return jsonify({
        "dimension": dimension,
        "years": years,
        "items": items,
    })


@trends_bp.route("/patterns", methods=["GET"])
def patterns():
    """Spending pattern analysis — seasonality, growth, and anomalies."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    dimension = request.args.get("dimension", "category")
    top_n = int(request.args.get("top_n", "8"))

    date_conditions, date_params = _build_date_filter(start_date, end_date)
    dim_col = _get_dimension_col(dimension)
    dim_filter = _get_dimension_extra_filter(dimension)

    # --- Seasonality: average spending per calendar month across all years ---
    seasonality_raw = _safe_query(
        f"""
        SELECT
            sub.mo AS month,
            AVG(sub.monthly_total) AS avg_spending
        FROM (
            SELECT
                EXTRACT(YEAR FROM check_date)::INT AS yr,
                EXTRACT(MONTH FROM check_date)::INT AS mo,
                SUM(amount) AS monthly_total
            FROM payment_contract_joined
            WHERE is_annual_aggregate = false{date_conditions}
            GROUP BY 1, 2
        ) sub
        GROUP BY sub.mo
        ORDER BY sub.mo
        """,
        date_params if date_params else None,
    )

    seasonality = [
        {
            "month": int(r["month"]),
            "avg_spending": float(r["avg_spending"]),
            "label": MONTH_LABELS[int(r["month"])] if int(r["month"]) <= 12 else "",
        }
        for r in seasonality_raw
    ]

    # --- Quarterly spending ---
    quarterly_raw = _safe_query(
        f"""
        SELECT
            EXTRACT(YEAR FROM check_date)::INT AS year,
            EXTRACT(QUARTER FROM check_date)::INT AS quarter,
            SUM(amount) AS amount,
            COUNT(*) AS count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{date_conditions}
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        date_params if date_params else None,
    )

    quarterly = [
        {
            "year": int(r["year"]),
            "quarter": int(r["quarter"]),
            "amount": float(r["amount"]),
            "count": int(r["count"]),
        }
        for r in quarterly_raw
    ]

    # --- Growth: compare two most recent full years ---
    years_raw = _safe_query(
        f"""
        SELECT DISTINCT EXTRACT(YEAR FROM check_date)::INT AS year
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{date_conditions}
        ORDER BY year
        """,
        date_params if date_params else None,
    )
    all_years = [int(r["year"]) for r in years_raw]

    # For growth comparison, use the two most recent FULL years
    # (exclude current year if it's likely partial)
    import datetime
    current_year = datetime.date.today().year
    full_years = [y for y in all_years if y < current_year]

    growth = {}
    if len(full_years) >= 2:
        latest_year = full_years[-1]
        prior_year = full_years[-2]

        # Overall totals for the two years
        growth_totals_params = list(date_params) + [latest_year, prior_year]
        latest_idx = len(date_params) + 1
        prior_idx = len(date_params) + 2

        totals_raw = _safe_query(
            f"""
            SELECT
                EXTRACT(YEAR FROM check_date)::INT AS year,
                SUM(amount) AS total
            FROM payment_contract_joined
            WHERE is_annual_aggregate = false{date_conditions}
              AND EXTRACT(YEAR FROM check_date)::INT IN (${latest_idx}, ${prior_idx})
            GROUP BY 1
            """,
            growth_totals_params,
        )

        totals_map = {int(r["year"]): float(r["total"]) for r in totals_raw}
        latest_total = totals_map.get(latest_year, 0)
        prior_total = totals_map.get(prior_year, 0)
        growth_pct = (
            round(((latest_total - prior_total) / prior_total) * 100, 1)
            if prior_total != 0
            else None
        )

        # By dimension breakdown
        by_dim_raw = _safe_query(
            f"""
            SELECT
                {dim_col} AS name,
                EXTRACT(YEAR FROM check_date)::INT AS year,
                SUM(amount) AS total
            FROM payment_contract_joined
            WHERE is_annual_aggregate = false{dim_filter}{date_conditions}
              AND EXTRACT(YEAR FROM check_date)::INT IN (${latest_idx}, ${prior_idx})
            GROUP BY 1, 2
            ORDER BY total DESC
            """,
            growth_totals_params,
        )

        dim_year_map = {}
        for r in by_dim_raw:
            name = r["name"]
            yr = int(r["year"])
            if name not in dim_year_map:
                dim_year_map[name] = {}
            dim_year_map[name][yr] = float(r["total"])

        # Rank by combined total, take top_n
        dim_combined = []
        for name, year_vals in dim_year_map.items():
            latest_val = year_vals.get(latest_year, 0)
            prior_val = year_vals.get(prior_year, 0)
            dim_combined.append({
                "name": name,
                "latest": latest_val,
                "prior": prior_val,
                "combined": latest_val + prior_val,
            })
        dim_combined.sort(key=lambda x: x["combined"], reverse=True)

        by_dimension = []
        for item in dim_combined[:top_n]:
            change_pct = (
                round(((item["latest"] - item["prior"]) / item["prior"]) * 100, 1)
                if item["prior"] != 0
                else None
            )
            by_dimension.append({
                "name": item["name"],
                "latest": item["latest"],
                "prior": item["prior"],
                "change_pct": change_pct,
            })

        growth = {
            "latest_year": latest_year,
            "prior_year": prior_year,
            "latest_total": latest_total,
            "prior_total": prior_total,
            "growth_pct": growth_pct,
            "by_dimension": by_dimension,
        }

    # --- Spikes: months where spending > 1.5x the average for that calendar month ---
    spikes_raw = _safe_query(
        f"""
        WITH monthly AS (
            SELECT
                EXTRACT(YEAR FROM check_date)::INT AS year,
                EXTRACT(MONTH FROM check_date)::INT AS month,
                SUM(amount) AS amount
            FROM payment_contract_joined
            WHERE is_annual_aggregate = false{date_conditions}
            GROUP BY 1, 2
        ),
        month_avg AS (
            SELECT
                month,
                AVG(amount) AS avg_for_month
            FROM monthly
            GROUP BY month
        )
        SELECT
            m.year,
            m.month,
            m.amount,
            ma.avg_for_month,
            m.amount / ma.avg_for_month AS spike_ratio
        FROM monthly m
        JOIN month_avg ma ON m.month = ma.month
        WHERE m.amount > 1.5 * ma.avg_for_month
        ORDER BY spike_ratio DESC
        """,
        date_params if date_params else None,
    )

    # For each spike, find the top vendor
    spikes = []
    for r in spikes_raw:
        yr = int(r["year"])
        mo = int(r["month"])

        spike_params = list(date_params) + [yr, mo]
        yr_idx = len(date_params) + 1
        mo_idx = len(date_params) + 2

        top_vendor_raw = _safe_query(
            f"""
            SELECT vendor_name, SUM(amount) AS total
            FROM payment_contract_joined
            WHERE is_annual_aggregate = false{date_conditions}
              AND EXTRACT(YEAR FROM check_date)::INT = ${yr_idx}
              AND EXTRACT(MONTH FROM check_date)::INT = ${mo_idx}
            GROUP BY vendor_name
            ORDER BY total DESC
            LIMIT 1
            """,
            spike_params,
        )

        top_vendor = top_vendor_raw[0]["vendor_name"] if top_vendor_raw else None

        spikes.append({
            "year": yr,
            "month": mo,
            "amount": float(r["amount"]),
            "avg_for_month": float(r["avg_for_month"]),
            "spike_ratio": round(float(r["spike_ratio"]), 2),
            "top_vendor": top_vendor,
        })

    return jsonify({
        "seasonality": seasonality,
        "quarterly": quarterly,
        "growth": growth,
        "spikes": spikes,
    })
