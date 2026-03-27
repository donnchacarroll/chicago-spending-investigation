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


@departments_bp.route("/true-cost", methods=["GET"])
def department_true_cost():
    """Return department true cost analysis with attribution detail and methodology."""
    year = request.args.get("year")
    year_condition = ""
    year_params = []
    if year:
        year_condition = " WHERE year = $1"
        year_params = [int(year)]

    # When filtering by year, aggregate per department; when all years, sum across years
    departments = _safe_query(f"""
        SELECT department_name,
               SUM(employee_count) AS employee_count,
               SUM(total_salary) AS total_salary,
               SUM(confirmed_payments) AS confirmed_payments,
               MAX(confirmed_contracts) AS confirmed_contracts,
               SUM(attributed_total) AS attributed_total,
               SUM(estimated_total) AS estimated_total,
               SUM(total_true_cost) AS total_true_cost
        FROM department_true_cost
        {year_condition}
        GROUP BY department_name
        ORDER BY total_true_cost DESC
    """, year_params or None)

    # For single-year queries, employee_count/total_salary are already correct.
    # For all-years, we show the latest year's headcount for display.
    if not year:
        latest_salary = _safe_query("""
            SELECT department_name, employee_count, total_salary
            FROM department_true_cost
            WHERE year = (SELECT MAX(year) FROM department_true_cost WHERE total_salary > 0)
        """)
        salary_lookup = {r["department_name"]: r for r in latest_salary}
        for dept in departments:
            latest = salary_lookup.get(dept["department_name"])
            if latest:
                dept["employee_count"] = latest["employee_count"]
                dept["total_salary"] = latest["total_salary"]

    # Attach cost detail per department
    detail_year_cond = ""
    if year:
        detail_year_cond = " WHERE year = $1"
    detail = _safe_query(f"""
        SELECT department_name, tier, source_vendor, SUM(amount) AS amount,
               reason
        FROM department_cost_detail
        {detail_year_cond}
        GROUP BY department_name, tier, source_vendor, reason
        ORDER BY department_name, tier, amount DESC
    """, year_params or None)

    detail_by_dept = {}
    for row in detail:
        dept = row["department_name"]
        if dept not in detail_by_dept:
            detail_by_dept[dept] = []
        detail_by_dept[dept].append({
            "tier": row["tier"],
            "source_vendor": row["source_vendor"],
            "amount": row["amount"],
            "reason": row["reason"],
        })

    for dept in departments:
        dept["detail"] = detail_by_dept.get(dept["department_name"], [])

    # Totals
    totals = _safe_query(f"""
        SELECT SUM(employee_count) AS total_employees,
               SUM(total_salary) AS total_salary,
               SUM(confirmed_payments) AS total_confirmed_payments,
               SUM(attributed_total) AS total_attributed,
               SUM(estimated_total) AS total_estimated,
               SUM(total_true_cost) AS grand_total_true_cost
        FROM department_true_cost
        {year_condition}
    """, year_params or None)

    # Available years
    available_years = _safe_query(
        "SELECT DISTINCT year FROM department_true_cost ORDER BY year"
    )

    methodology = (
        "Department true cost is computed annually in three tiers: "
        "(1) Confirmed: payments explicitly tagged with a department in city records. "
        "(2) Attributed: payments to vendors with a known single-department relationship "
        "(e.g., pension funds mapped to Police or Fire), where 90%+ of contract value "
        "goes to one department. "
        "(3) Estimated: shared costs (city-wide pension funds, insurance, banking) "
        "allocated proportionally by department headcount. "
        "Salary data comes from Chicago Budget Ordinance datasets (budgeted positions). "
        "2026 uses the current employee salary snapshot. "
        "Contract awards are shown for reference but not year-filtered. "
        "All payment data is scoped to 2023 and later."
    )

    return jsonify({
        "departments": departments,
        "totals": totals[0] if totals else {},
        "methodology": methodology,
        "available_years": [r["year"] for r in available_years],
        "selected_year": int(year) if year else None,
    })


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
