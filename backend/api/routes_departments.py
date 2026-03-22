"""Department routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db

departments_bp = Blueprint("departments_bp", __name__, url_prefix="/api/departments")


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


@departments_bp.route("/", methods=["GET"])
def list_departments():
    """Return all departments with spending stats and risk scores."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    date_conditions = ""
    date_params = []
    param_idx = 1
    if start_date:
        date_conditions += f" AND p.check_date >= CAST(${param_idx} AS TIMESTAMP)"
        date_params.append(start_date)
        param_idx += 1
    if end_date:
        date_conditions += f" AND p.check_date <= CAST(${param_idx} AS TIMESTAMP)"
        date_params.append(end_date)
        param_idx += 1

    data = _safe_query(
        f"""
        SELECT
            p.department_canonical AS department_name,
            SUM(p.amount) AS total_spending,
            COUNT(DISTINCT p.vendor_name) AS vendor_count,
            COUNT(*) AS payment_count,
            COALESCE(d.composite_score, 0) AS risk_score
        FROM payments p
        LEFT JOIN department_risk_scores d ON p.department_canonical = d.department_name
        WHERE p.is_annual_aggregate = false{date_conditions}
        GROUP BY p.department_canonical, d.composite_score
        ORDER BY total_spending DESC
        """,
        date_params if date_params else None,
    )

    return jsonify({"departments": data})


@departments_bp.route("/<path:department_name>", methods=["GET"])
def department_detail(department_name):
    """Return detailed department information."""

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Build date conditions (starting after $1 for department_name)
    date_conditions = ""
    date_conditions_p = ""
    date_params = []
    param_idx = 2  # $1 is department_name
    if start_date:
        date_conditions += f" AND check_date >= CAST(${param_idx} AS TIMESTAMP)"
        date_conditions_p += f" AND p.check_date >= CAST(${param_idx} AS TIMESTAMP)"
        date_params.append(start_date)
        param_idx += 1
    if end_date:
        date_conditions += f" AND check_date <= CAST(${param_idx} AS TIMESTAMP)"
        date_conditions_p += f" AND p.check_date <= CAST(${param_idx} AS TIMESTAMP)"
        date_params.append(end_date)
        param_idx += 1

    # Summary stats
    summary_rows = _safe_query(
        f"""
        SELECT
            p.department_canonical AS department_name,
            SUM(p.amount) AS total_spending,
            COUNT(*) AS payment_count,
            COUNT(DISTINCT p.vendor_name) AS vendor_count,
            MIN(p.check_date) AS first_payment,
            MAX(p.check_date) AS last_payment,
            AVG(p.amount) AS avg_payment,
            COALESCE(d.composite_score, 0) AS risk_score,
            COALESCE(d.flag_count, 0) AS flag_count
        FROM payments p
        LEFT JOIN department_risk_scores d ON p.department_canonical = d.department_name
        WHERE p.department_canonical = $1 AND p.is_annual_aggregate = false{date_conditions_p}
        GROUP BY p.department_canonical, d.composite_score, d.flag_count
        """,
        [department_name] + date_params,
    )

    if not summary_rows:
        return jsonify({"error": "Department not found"}), 404

    summary = summary_rows[0]
    for date_key in ("first_payment", "last_payment"):
        if summary.get(date_key) is not None:
            summary[date_key] = str(summary[date_key])

    # Monthly spending trend
    monthly_trend = _safe_query(
        f"""
        SELECT year, month, SUM(amount) AS total, COUNT(*) AS count
        FROM payments
        WHERE department_canonical = $1 AND is_annual_aggregate = false{date_conditions}
        GROUP BY year, month
        ORDER BY year, month
        """,
        [department_name] + date_params,
    )

    # Top vendors
    top_vendors = _safe_query(
        f"""
        SELECT
            vendor_name,
            SUM(amount) AS total_paid,
            COUNT(*) AS payment_count
        FROM payments
        WHERE department_canonical = $1 AND is_annual_aggregate = false{date_conditions}
        GROUP BY vendor_name
        ORDER BY total_paid DESC
        LIMIT 20
        """,
        [department_name] + date_params,
    )

    # Vendor concentration metrics
    concentration = _safe_query(
        f"""
        WITH vendor_totals AS (
            SELECT
                vendor_name,
                SUM(amount) AS vendor_total
            FROM payments
            WHERE department_canonical = $1 AND is_annual_aggregate = false{date_conditions}
            GROUP BY vendor_name
        ),
        dept_total AS (
            SELECT SUM(vendor_total) AS grand_total FROM vendor_totals
        )
        SELECT
            COUNT(*) AS total_vendors,
            MAX(vt.vendor_total) AS max_vendor_spending,
            MAX(vt.vendor_total) / NULLIF(dt.grand_total, 0) AS top_vendor_share,
            -- HHI: sum of squared market shares
            SUM(POWER(vt.vendor_total / NULLIF(dt.grand_total, 0), 2)) AS hhi
        FROM vendor_totals vt, dept_total dt
        """,
        [department_name] + date_params,
    )

    # Flags
    flags = _safe_query(
        """
        SELECT flag_type, description, risk_score, vendor_name, amount, voucher_number
        FROM alerts
        WHERE department_name = $1
        ORDER BY risk_score DESC
        """,
        [department_name],
    )

    return jsonify({
        "summary": summary,
        "monthly_trend": monthly_trend,
        "top_vendors": top_vendors,
        "concentration": concentration[0] if concentration else {},
        "flags": flags,
    })
