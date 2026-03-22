"""Category analysis routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db

categories_bp = Blueprint("categories_bp", __name__, url_prefix="/api/categories")


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


@categories_bp.route("/", methods=["GET"])
def categories_overview():
    """Return full category analysis with optional date filtering."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    date_conditions, date_params = _build_date_filter(start_date, end_date)

    # By spending category
    by_category = _safe_query(
        f"""
        SELECT
            COALESCE(spending_category, 'Uncategorized / Direct Voucher') AS category,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count,
            COUNT(DISTINCT vendor_name) AS vendor_count,
            AVG(amount) AS avg_payment
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{date_conditions}
        GROUP BY 1
        ORDER BY total_spending DESC
        """,
        date_params if date_params else None,
    )

    # By procurement type
    by_procurement = _safe_query(
        f"""
        SELECT
            COALESCE(procurement_type, 'Unknown') AS procurement_type,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count,
            COUNT(DISTINCT vendor_name) AS vendor_count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{date_conditions}
        GROUP BY 1
        ORDER BY total_spending DESC
        """,
        date_params if date_params else None,
    )

    # By contract type (top 30)
    by_contract_type = _safe_query(
        f"""
        SELECT
            COALESCE(contract_type_desc, 'N/A') AS contract_type,
            COALESCE(spending_category, 'Uncategorized / Direct Voucher') AS category,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false{date_conditions}
        GROUP BY 1, 2
        ORDER BY total_spending DESC
        LIMIT 30
        """,
        date_params if date_params else None,
    )

    # No-contract spending
    no_contract_rows = _safe_query(
        f"""
        SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false
          AND contract_type = 'direct_voucher'{date_conditions}
        """,
        date_params if date_params else None,
    )
    no_contract_spending = {
        "total": float(no_contract_rows[0]["total"]) if no_contract_rows else 0,
        "count": int(no_contract_rows[0]["count"]) if no_contract_rows else 0,
    }

    return jsonify({
        "by_category": by_category,
        "by_procurement": by_procurement,
        "by_contract_type": by_contract_type,
        "no_contract_spending": no_contract_spending,
    })


@categories_bp.route("/direct-vouchers", methods=["GET"])
def direct_voucher_breakdown():
    """Break down direct voucher payments by vendor subcategory."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    date_conditions, date_params = _build_date_filter(start_date, end_date)

    # By DV subcategory
    by_subcategory = _safe_query(
        f"""
        SELECT
            COALESCE(dv_subcategory, 'Unclassified') AS subcategory,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count,
            COUNT(DISTINCT vendor_name) AS vendor_count,
            AVG(amount) AS avg_payment
        FROM payment_contract_joined
        WHERE contract_type = 'direct_voucher'
          AND is_annual_aggregate = false{date_conditions}
        GROUP BY 1
        ORDER BY total_spending DESC
        """,
        date_params if date_params else None,
    )

    # Top vendors per subcategory (top 10 each)
    subcategory_name = request.args.get("subcategory")
    top_vendors = []
    if subcategory_name:
        sub_params = list(date_params) + [subcategory_name]
        sub_idx = len(date_params) + 1
        top_vendors = _safe_query(
            f"""
            SELECT
                vendor_name,
                SUM(amount) AS total_paid,
                COUNT(*) AS payment_count,
                AVG(amount) AS avg_payment
            FROM payment_contract_joined
            WHERE contract_type = 'direct_voucher'
              AND is_annual_aggregate = false
              AND COALESCE(dv_subcategory, 'Unclassified') = ${sub_idx}{date_conditions}
            GROUP BY vendor_name
            ORDER BY total_paid DESC
            LIMIT 25
            """,
            sub_params,
        )

    # Largest individual DV payments
    largest = _safe_query(
        f"""
        SELECT
            vendor_name,
            amount,
            check_date,
            department_canonical AS department_name,
            dv_subcategory AS subcategory,
            voucher_number
        FROM payment_contract_joined
        WHERE contract_type = 'direct_voucher'
          AND is_annual_aggregate = false{date_conditions}
        ORDER BY amount DESC
        LIMIT 30
        """,
        date_params if date_params else None,
    )
    for row in largest:
        if row.get("check_date"):
            row["check_date"] = str(row["check_date"])

    # Individual payments analysis
    individual_stats = _safe_query(
        f"""
        SELECT
            COUNT(*) AS payment_count,
            SUM(amount) AS total_spending,
            AVG(amount) AS avg_payment,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) AS median_payment
        FROM payment_contract_joined
        WHERE contract_type = 'direct_voucher'
          AND is_annual_aggregate = false
          AND dv_subcategory = 'Individual Payments'{date_conditions}
        """,
        date_params if date_params else None,
    )

    return jsonify({
        "by_subcategory": by_subcategory,
        "top_vendors": top_vendors,
        "largest_payments": largest,
        "individual_stats": individual_stats[0] if individual_stats else {},
    })


@categories_bp.route("/direct-vouchers/trends", methods=["GET"])
def dv_trends():
    """Trend analysis for direct voucher spending by subcategory over time."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    date_conditions, date_params = _build_date_filter(start_date, end_date)

    # Monthly spending by DV subcategory
    monthly = _safe_query(
        f"""
        SELECT
            EXTRACT(YEAR FROM check_date)::INT AS year,
            EXTRACT(MONTH FROM check_date)::INT AS month,
            COALESCE(dv_subcategory, 'Unclassified') AS subcategory,
            SUM(amount) AS total,
            COUNT(*) AS count
        FROM payment_contract_joined
        WHERE contract_type = 'direct_voucher'
          AND is_annual_aggregate = false{date_conditions}
        GROUP BY 1, 2, 3
        ORDER BY 1, 2
        """,
        date_params if date_params else None,
    )

    # YoY comparison by subcategory (two most recent full years)
    import datetime
    current_year = datetime.date.today().year
    yoy = _safe_query(
        f"""
        SELECT
            COALESCE(dv_subcategory, 'Unclassified') AS subcategory,
            SUM(CASE WHEN EXTRACT(YEAR FROM check_date) = {current_year - 2} THEN amount ELSE 0 END) AS prior_year,
            SUM(CASE WHEN EXTRACT(YEAR FROM check_date) = {current_year - 1} THEN amount ELSE 0 END) AS latest_year,
            SUM(amount) AS total
        FROM payment_contract_joined
        WHERE contract_type = 'direct_voucher'
          AND is_annual_aggregate = false{date_conditions}
        GROUP BY 1
        ORDER BY total DESC
        """,
        date_params if date_params else None,
    )

    for row in yoy:
        prior = row.get("prior_year", 0) or 0
        latest = row.get("latest_year", 0) or 0
        row["change_pct"] = round(((latest - prior) / prior) * 100, 1) if prior > 0 else None
    yoy_years = [current_year - 2, current_year - 1]

    # Fastest growing subcategories
    growing = sorted(
        [r for r in yoy if r.get("change_pct") is not None],
        key=lambda r: r["change_pct"],
        reverse=True,
    )

    # Top vendors in "Other Direct Voucher" (the unclassified residual)
    other_vendors = _safe_query(
        f"""
        SELECT vendor_name, SUM(amount) AS total_paid, COUNT(*) AS payment_count
        FROM payment_contract_joined
        WHERE contract_type = 'direct_voucher'
          AND is_annual_aggregate = false
          AND dv_subcategory = 'Other Direct Voucher'{date_conditions}
        GROUP BY vendor_name
        ORDER BY total_paid DESC
        LIMIT 20
        """,
        date_params if date_params else None,
    )

    return jsonify({
        "monthly": monthly,
        "yoy": yoy,
        "yoy_years": yoy_years,
        "growing": growing[:5],
        "declining": list(reversed(growing))[:5] if growing else [],
        "other_dv_top_vendors": other_vendors,
    })


@categories_bp.route("/<category_name>", methods=["GET"])
def category_detail(category_name):
    """Drill into a specific spending category."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    date_conditions, date_params = _build_date_filter(start_date, end_date)

    # Category filter param comes after date params
    cat_param_idx = len(date_params) + 1
    cat_condition = f" AND COALESCE(spending_category, 'Uncategorized / Direct Voucher') = ${cat_param_idx}"
    all_params = date_params + [category_name]

    base_where = f"is_annual_aggregate = false{date_conditions}{cat_condition}"

    # Top vendors in this category
    top_vendors = _safe_query(
        f"""
        SELECT
            vendor_name,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count
        FROM payment_contract_joined
        WHERE {base_where}
        GROUP BY vendor_name
        ORDER BY total_spending DESC
        LIMIT 20
        """,
        all_params,
    )

    # Top departments in this category
    top_departments = _safe_query(
        f"""
        SELECT
            department_canonical AS department_name,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count
        FROM payment_contract_joined
        WHERE {base_where}
        GROUP BY department_canonical
        ORDER BY total_spending DESC
        LIMIT 20
        """,
        all_params,
    )

    # Monthly trend
    monthly_trend = _safe_query(
        f"""
        SELECT
            DATE_TRUNC('month', check_date) AS month,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count
        FROM payment_contract_joined
        WHERE {base_where}
        GROUP BY month
        ORDER BY month
        """,
        all_params,
    )

    # Largest individual payments
    largest_payments = _safe_query(
        f"""
        SELECT
            voucher_number,
            vendor_name,
            department_canonical AS department_name,
            amount,
            check_date,
            purchase_order_description,
            contract_type_desc,
            procurement_type
        FROM payment_contract_joined
        WHERE {base_where}
        ORDER BY amount DESC
        LIMIT 25
        """,
        all_params,
    )

    # Summary stats
    summary = _safe_query(
        f"""
        SELECT
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count,
            COUNT(DISTINCT vendor_name) AS vendor_count,
            COUNT(DISTINCT department_canonical) AS department_count,
            AVG(amount) AS avg_payment
        FROM payment_contract_joined
        WHERE {base_where}
        """,
        all_params,
    )

    # Serialize dates
    for row in monthly_trend:
        if row.get("month"):
            row["month"] = str(row["month"])
    for row in largest_payments:
        if row.get("check_date"):
            row["check_date"] = str(row["check_date"])

    return jsonify({
        "category": category_name,
        "summary": summary[0] if summary else {},
        "top_vendors": top_vendors,
        "top_departments": top_departments,
        "monthly_trend": monthly_trend,
        "largest_payments": largest_payments,
    })
