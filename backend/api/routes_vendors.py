"""Vendor routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db

vendors_bp = Blueprint("vendors_bp", __name__, url_prefix="/api/vendors")


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


SORT_COLUMNS = {
    "total_paid": "total_paid",
    "payment_count": "payment_count",
    "department_count": "department_count",
    "risk_score": "risk_score",
    "vendor_name": "vendor_name",
}


@vendors_bp.route("/", methods=["GET"])
def list_vendors():
    """Return paginated, searchable, sortable list of vendors with stats."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)
    offset = (page - 1) * per_page

    search = request.args.get("search", "").strip()
    sort_by = request.args.get("sort_by", "total_paid")
    sort_dir = request.args.get("sort_dir", "desc").lower()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Validate sort
    sort_col = SORT_COLUMNS.get(sort_by, "total_paid")
    sort_direction = "DESC" if sort_dir != "asc" else "ASC"

    params = []
    where_clause = "WHERE p.is_annual_aggregate = false"
    having_clause = ""

    if start_date:
        where_clause += " AND p.check_date >= CAST($" + str(len(params) + 1) + " AS TIMESTAMP)"
        params.append(start_date)

    if end_date:
        where_clause += " AND p.check_date <= CAST($" + str(len(params) + 1) + " AS TIMESTAMP)"
        params.append(end_date)

    if search:
        # Filter in HAVING since vendor_name is in GROUP BY
        having_clause = "HAVING p.vendor_name ILIKE $" + str(len(params) + 1)
        params.append(f"%{search}%")

    # Count query
    count_sql = f"""
        SELECT COUNT(*) AS total FROM (
            SELECT p.vendor_name
            FROM payments p
            {where_clause}
            GROUP BY p.vendor_name
            {having_clause}
        ) sub
    """
    count_rows = _safe_query(count_sql, params if params else None)
    total = count_rows[0]["total"] if count_rows else 0

    # Data query
    data_sql = f"""
        SELECT
            p.vendor_name,
            SUM(p.amount) AS total_paid,
            COUNT(*) AS payment_count,
            COUNT(DISTINCT p.department_canonical) AS department_count,
            COALESCE(v.composite_score, 0) AS risk_score
        FROM payments p
        LEFT JOIN vendor_risk_scores v ON p.vendor_name = v.vendor_name
        {where_clause}
        GROUP BY p.vendor_name, v.composite_score
        {having_clause}
        ORDER BY {sort_col} {sort_direction}
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
    """
    params.extend([per_page, offset])
    data = _safe_query(data_sql, params)

    return jsonify({
        "vendors": data,
        "total": int(total),
        "page": page,
        "per_page": per_page,
        "total_pages": (int(total) + per_page - 1) // per_page if per_page > 0 else 0,
    })


@vendors_bp.route("/<path:vendor_name>", methods=["GET"])
def vendor_detail(vendor_name):
    """Return detailed vendor information including stats, history, and flags."""

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Build date conditions for parameterized queries (starting after $1 for vendor_name)
    date_conditions = ""
    date_conditions_p = ""
    date_params = []
    param_idx = 2  # $1 is vendor_name
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
            p.vendor_name,
            SUM(p.amount) AS total_paid,
            COUNT(*) AS payment_count,
            COUNT(DISTINCT p.department_canonical) AS department_count,
            MIN(p.check_date) AS first_payment,
            MAX(p.check_date) AS last_payment,
            AVG(p.amount) AS avg_payment,
            COALESCE(v.composite_score, 0) AS risk_score,
            COALESCE(v.flag_count, 0) AS flag_count
        FROM payments p
        LEFT JOIN vendor_risk_scores v ON p.vendor_name = v.vendor_name
        WHERE p.vendor_name = $1 AND p.is_annual_aggregate = false{date_conditions_p}
        GROUP BY p.vendor_name, v.composite_score, v.flag_count
        """,
        [vendor_name] + date_params,
    )

    if not summary_rows:
        return jsonify({"error": "Vendor not found"}), 404

    summary = summary_rows[0]
    for date_key in ("first_payment", "last_payment"):
        if summary.get(date_key) is not None:
            summary[date_key] = str(summary[date_key])

    # Monthly payment history
    payment_history = _safe_query(
        f"""
        SELECT year, month, SUM(amount) AS total, COUNT(*) AS count
        FROM payments
        WHERE vendor_name = $1 AND is_annual_aggregate = false{date_conditions}
        GROUP BY year, month
        ORDER BY year, month
        """,
        [vendor_name] + date_params,
    )

    # Departments
    departments = _safe_query(
        f"""
        SELECT department_canonical AS department_name, SUM(amount) AS total_paid, COUNT(*) AS payment_count
        FROM payments
        WHERE vendor_name = $1 AND is_annual_aggregate = false{date_conditions}
        GROUP BY department_canonical
        ORDER BY total_paid DESC
        """,
        [vendor_name] + date_params,
    )

    # Contracts
    contracts = _safe_query(
        """
        SELECT DISTINCT
            contract_number, contract_type,
            award_amount, total_paid_per_contract, overspend_ratio
        FROM payment_contract_joined
        WHERE vendor_name = $1 AND contract_number IS NOT NULL
        ORDER BY award_amount DESC
        """,
        [vendor_name],
    )

    # Flags
    flags = _safe_query(
        """
        SELECT flag_type, description, risk_score, amount, voucher_number, department_name
        FROM alerts
        WHERE vendor_name = $1
        ORDER BY risk_score DESC
        """,
        [vendor_name],
    )

    return jsonify({
        "summary": summary,
        "payment_history": payment_history,
        "departments": departments,
        "contracts": contracts,
        "flags": flags,
    })
