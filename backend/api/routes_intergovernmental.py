"""Intergovernmental payment routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db

intergovernmental_bp = Blueprint(
    "intergovernmental_bp", __name__, url_prefix="/api/intergovernmental"
)


def _safe_query(sql, params=None):
    """Execute a query and return results as list of dicts, or empty on error."""
    try:
        con = get_db()
        if params:
            result = con.execute(sql, params)
        else:
            result = con.execute(sql)
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception:
        return []


@intergovernmental_bp.route("/", methods=["GET"])
def intergovernmental_summary():
    """Summary of intergovernmental payment flows."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    params = []
    date_conditions = ""
    if start_date:
        date_conditions += " AND p.check_date >= CAST($" + str(len(params) + 1) + " AS TIMESTAMP)"
        params.append(start_date)
    if end_date:
        date_conditions += " AND p.check_date <= CAST($" + str(len(params) + 1) + " AS TIMESTAMP)"
        params.append(end_date)

    where = f"WHERE p.is_intergovernmental = true AND p.is_annual_aggregate = false{date_conditions}"

    # Totals
    totals = _safe_query(
        f"SELECT COALESCE(SUM(p.amount), 0) AS total_spending, COUNT(*) AS payment_count "
        f"FROM payment_contract_joined p {where}",
        params or None,
    )
    total_spending = float(totals[0]["total_spending"]) if totals else 0.0
    payment_count = int(totals[0]["payment_count"]) if totals else 0

    # Top recipients
    top_recipients = _safe_query(
        f"""
        SELECT p.vendor_name, SUM(p.amount) AS total_paid, COUNT(*) AS payment_count
        FROM payment_contract_joined p
        {where}
        GROUP BY p.vendor_name
        ORDER BY total_paid DESC
        LIMIT 20
        """,
        params or None,
    )

    # Spending by year
    spending_by_year = _safe_query(
        f"""
        SELECT p.year, SUM(p.amount) AS total_spending, COUNT(*) AS payment_count
        FROM payment_contract_joined p
        {where}
        GROUP BY p.year
        ORDER BY p.year
        """,
        params or None,
    )

    # Spending by department
    spending_by_department = _safe_query(
        f"""
        SELECT p.department_canonical AS department_name,
               SUM(p.amount) AS total_spending, COUNT(*) AS payment_count
        FROM payment_contract_joined p
        {where}
        GROUP BY p.department_canonical
        ORDER BY total_spending DESC
        """,
        params or None,
    )

    return jsonify({
        "total_spending": total_spending,
        "payment_count": payment_count,
        "top_recipients": top_recipients,
        "spending_by_year": spending_by_year,
        "spending_by_department": spending_by_department,
    })


@intergovernmental_bp.route("/<path:vendor_name>", methods=["GET"])
def intergovernmental_detail(vendor_name):
    """Detail for a specific intergovernmental entity."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    params = [vendor_name]
    date_conditions = ""
    if start_date:
        date_conditions += " AND p.check_date >= CAST($" + str(len(params) + 1) + " AS TIMESTAMP)"
        params.append(start_date)
    if end_date:
        date_conditions += " AND p.check_date <= CAST($" + str(len(params) + 1) + " AS TIMESTAMP)"
        params.append(end_date)

    where = f"WHERE p.vendor_name = $1 AND p.is_intergovernmental = true AND p.is_annual_aggregate = false{date_conditions}"

    # Summary
    summary = _safe_query(
        f"""
        SELECT SUM(p.amount) AS total_paid, COUNT(*) AS payment_count,
               MIN(p.check_date) AS first_payment, MAX(p.check_date) AS last_payment
        FROM payment_contract_joined p
        {where}
        """,
        params,
    )
    if not summary or summary[0]["total_paid"] is None:
        return jsonify({"error": "Not found"}), 404

    row = summary[0]

    # Payment history by year
    payment_history = _safe_query(
        f"""
        SELECT p.year, p.month, SUM(p.amount) AS total, COUNT(*) AS count
        FROM payment_contract_joined p
        {where}
        GROUP BY p.year, p.month
        ORDER BY p.year, p.month
        """,
        params,
    )

    # Departments
    departments = _safe_query(
        f"""
        SELECT p.department_canonical AS department_name,
               SUM(p.amount) AS total_paid, COUNT(*) AS payment_count
        FROM payment_contract_joined p
        {where}
        GROUP BY p.department_canonical
        ORDER BY total_paid DESC
        """,
        params,
    )

    return jsonify({
        "vendor_name": vendor_name,
        "total_paid": float(row["total_paid"]),
        "payment_count": int(row["payment_count"]),
        "first_payment": str(row["first_payment"]) if row["first_payment"] else None,
        "last_payment": str(row["last_payment"]) if row["last_payment"] else None,
        "payment_history": payment_history,
        "departments": departments,
    })
