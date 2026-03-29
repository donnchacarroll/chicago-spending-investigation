"""Overview routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db

overview_bp = Blueprint("overview_bp", __name__, url_prefix="/api/overview")


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


@overview_bp.route("/", methods=["GET"])
def overview():
    """Return high-level dashboard statistics."""

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Build date conditions and params for payments table queries
    date_conditions = ""
    date_params = []
    param_idx = 1
    if start_date:
        date_conditions += f" AND check_date >= CAST(${param_idx} AS TIMESTAMP)"
        date_params.append(start_date)
        param_idx += 1
    if end_date:
        date_conditions += f" AND check_date <= CAST(${param_idx} AS TIMESTAMP)"
        date_params.append(end_date)
        param_idx += 1

    # Prefixed version for queries using p. alias
    date_conditions_p = date_conditions.replace("check_date", "p.check_date")

    # Total spending (non-aggregate only)
    total_spending_rows = _safe_query(
        f"SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE is_annual_aggregate = false{date_conditions}",
        date_params if date_params else None,
    )
    total_spending = total_spending_rows[0]["total"] if total_spending_rows else 0

    # Total payment count
    total_payments_rows = _safe_query(
        f"SELECT COUNT(*) AS cnt FROM payments WHERE is_annual_aggregate = false{date_conditions}",
        date_params if date_params else None,
    )
    total_payments = total_payments_rows[0]["cnt"] if total_payments_rows else 0

    # Flagged payments count (distinct voucher numbers in alerts)
    # Join to payments to apply date filter
    if date_params:
        flagged_rows = _safe_query(
            f"""SELECT COUNT(DISTINCT a.voucher_number) AS cnt
                FROM alerts a
                JOIN payments p ON a.voucher_number = p.voucher_number
                WHERE a.voucher_number IS NOT NULL AND p.is_annual_aggregate = false{date_conditions_p}""",
            date_params,
        )
    else:
        flagged_rows = _safe_query(
            "SELECT COUNT(DISTINCT voucher_number) AS cnt FROM alerts WHERE voucher_number IS NOT NULL"
        )
    flagged_payments_count = flagged_rows[0]["cnt"] if flagged_rows else 0

    # High-risk vendors (composite_risk_score > 75)
    high_risk_rows = _safe_query(
        "SELECT COUNT(*) AS cnt FROM vendor_risk_scores WHERE composite_score > 75"
    )
    high_risk_vendors_count = high_risk_rows[0]["cnt"] if high_risk_rows else 0

    # Departments count
    dept_rows = _safe_query(
        f"SELECT COUNT(DISTINCT department_canonical) AS cnt FROM payments WHERE is_annual_aggregate = false{date_conditions}",
        date_params if date_params else None,
    )
    departments_count = dept_rows[0]["cnt"] if dept_rows else 0

    # Date range (always show full range, not filtered)
    date_range_rows = _safe_query(
        "SELECT MIN(check_date) AS min_date, MAX(check_date) AS max_date FROM payments WHERE is_annual_aggregate = false"
    )
    if date_range_rows and date_range_rows[0]["min_date"] is not None:
        date_range = {
            "min": str(date_range_rows[0]["min_date"]),
            "max": str(date_range_rows[0]["max_date"]),
        }
    else:
        date_range = {"min": None, "max": None}

    # Spending by department (top 20)
    spending_by_department = _safe_query(
        f"""
        SELECT department_canonical AS department_name, SUM(amount) AS total_spending, COUNT(*) AS payment_count
        FROM payments
        WHERE is_annual_aggregate = false{date_conditions}
        GROUP BY department_canonical
        ORDER BY total_spending DESC
        LIMIT 20
        """,
        date_params if date_params else None,
    )

    # Spending by year
    spending_by_year = _safe_query(
        f"""
        SELECT year, SUM(amount) AS total_spending, COUNT(*) AS payment_count
        FROM payments
        WHERE is_annual_aggregate = false{date_conditions}
        GROUP BY year
        ORDER BY year
        """,
        date_params if date_params else None,
    )

    # Top vendors (top 20 with risk scores)
    top_vendors = _safe_query(
        f"""
        SELECT
            p.vendor_name,
            SUM(p.amount) AS total_paid,
            COUNT(*) AS payment_count,
            COALESCE(v.composite_score, 0) AS risk_score
        FROM payments p
        LEFT JOIN vendor_risk_scores v ON p.vendor_name = v.vendor_name
        WHERE p.is_annual_aggregate = false AND p.is_intergovernmental = false{date_conditions_p}
        GROUP BY p.vendor_name, v.composite_score
        ORDER BY total_paid DESC
        LIMIT 20
        """,
        date_params if date_params else None,
    )

    return jsonify({
        "total_spending": float(total_spending),
        "total_payments": int(total_payments),
        "flagged_payments_count": int(flagged_payments_count),
        "high_risk_vendors_count": int(high_risk_vendors_count),
        "departments_count": int(departments_count),
        "date_range": date_range,
        "spending_by_department": spending_by_department,
        "spending_by_year": spending_by_year,
        "top_vendors": top_vendors,
    })
