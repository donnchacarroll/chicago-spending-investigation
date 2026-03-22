"""Alert routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db
from backend.analysis.purpose_inference import infer_purpose

alerts_bp = Blueprint("alerts_bp", __name__, url_prefix="/api/alerts")


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


@alerts_bp.route("/", methods=["GET"])
def list_alerts():
    """Return paginated, filterable alerts sorted by risk score descending."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)
    offset = (page - 1) * per_page

    # TODO: start_date/end_date are accepted but not used for filtering alerts,
    # because many alert types (e.g. HIGH_CONCENTRATION, SPLIT_PAYMENT) don't have
    # voucher_numbers and can't be reliably joined to payments.check_date.
    _start_date = request.args.get("start_date")  # noqa: F841
    _end_date = request.args.get("end_date")  # noqa: F841

    conditions = []
    params = []

    flag_type = request.args.get("flag_type")
    if flag_type:
        conditions.append("flag_type = $" + str(len(params) + 1))
        params.append(flag_type)

    min_risk_score = request.args.get("min_risk_score", type=float)
    if min_risk_score is not None:
        conditions.append("risk_score >= $" + str(len(params) + 1))
        params.append(min_risk_score)

    department = request.args.get("department")
    if department:
        conditions.append("department_name = $" + str(len(params) + 1))
        params.append(department)

    vendor = request.args.get("vendor")
    if vendor:
        conditions.append("vendor_name = $" + str(len(params) + 1))
        params.append(vendor)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Count
    count_sql = f"SELECT COUNT(*) AS total FROM alerts {where_clause}"
    count_rows = _safe_query(count_sql, params if params else None)
    total = count_rows[0]["total"] if count_rows else 0

    # Data
    data_sql = f"""
        SELECT
            flag_type, description, risk_score, vendor_name,
            department_name, amount, voucher_number
        FROM alerts
        {where_clause}
        ORDER BY risk_score DESC
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
    """
    params.extend([per_page, offset])
    data = _safe_query(data_sql, params)

    return jsonify({
        "alerts": data,
        "total": int(total),
        "page": page,
        "per_page": per_page,
        "total_pages": (int(total) + per_page - 1) // per_page if per_page > 0 else 0,
    })


@alerts_bp.route("/detail/<path:voucher_number>", methods=["GET"])
def alert_detail(voucher_number):
    """Return detailed context for a specific alert/payment.

    For OUTLIER_AMOUNT alerts: returns group stats and comparison payments
    from the same vendor/department to explain why this payment is an outlier.
    """
    # Get the alert info
    alert_rows = _safe_query(
        """
        SELECT flag_type, description, risk_score, vendor_name,
               department_name, amount, voucher_number
        FROM alerts
        WHERE voucher_number = $1
        ORDER BY risk_score DESC
        """,
        [voucher_number],
    )

    if not alert_rows:
        return jsonify({"error": "Alert not found"}), 404

    # Get the payment itself
    payment_rows = _safe_query(
        """
        SELECT voucher_number, vendor_name, department_canonical AS department_name,
               amount, check_date, contract_number, contract_type
        FROM payments
        WHERE voucher_number = $1
        """,
        [voucher_number],
    )
    payment = payment_rows[0] if payment_rows else {}
    if payment.get("check_date"):
        payment["check_date"] = str(payment["check_date"])

    vendor = payment.get("vendor_name") or (alert_rows[0].get("vendor_name") if alert_rows else None)
    dept = payment.get("department_name") or (alert_rows[0].get("department_name") if alert_rows else None)

    # Group stats: how does this payment compare to others from same vendor/dept?
    group_stats = {}
    comparison_payments = []
    if vendor:
        stats_query = """
        SELECT
            COUNT(*) AS payment_count,
            ROUND(AVG(amount), 2) AS mean_amount,
            ROUND(STDDEV_SAMP(amount), 2) AS std_amount,
            ROUND(MIN(amount), 2) AS min_amount,
            ROUND(MAX(amount), 2) AS max_amount,
            ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount), 2) AS median_amount,
            ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY amount), 2) AS p25_amount,
            ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY amount), 2) AS p75_amount
        FROM payments
        WHERE vendor_name = $1
          AND is_annual_aggregate = false
          AND amount IS NOT NULL
        """
        params = [vendor]
        if dept:
            stats_query += " AND department_canonical = $2"
            params.append(dept)

        stats_rows = _safe_query(stats_query, params)
        if stats_rows:
            group_stats = stats_rows[0]

        # Get recent comparison payments from same vendor/dept (to show what "normal" looks like)
        comp_query = """
        SELECT voucher_number, amount, check_date, contract_number
        FROM payments
        WHERE vendor_name = $1
          AND is_annual_aggregate = false
          AND amount IS NOT NULL
        """
        comp_params = [vendor]
        if dept:
            comp_query += " AND department_canonical = $2"
            comp_params.append(dept)
        comp_query += " ORDER BY check_date DESC LIMIT 20"

        comparison_payments = _safe_query(comp_query, comp_params)
        for cp in comparison_payments:
            if cp.get("check_date"):
                cp["check_date"] = str(cp["check_date"])

    # Build a human-readable explanation
    explanation = _build_explanation(alert_rows, payment, group_stats)

    # Infer purpose
    purpose = infer_purpose(
        vendor_name=payment.get("vendor_name", ""),
        amount=payment.get("amount", 0),
        contract_type=payment.get("contract_type", ""),
    )

    return jsonify({
        "alerts": alert_rows,
        "payment": payment,
        "group_stats": group_stats,
        "comparison_payments": comparison_payments,
        "explanation": explanation,
        "inferred_purpose": purpose,
    })


def _build_explanation(alerts, payment, group_stats):
    """Build a plain-English explanation of why this payment was flagged."""
    sections = []
    amount = payment.get("amount", 0)
    vendor = payment.get("vendor_name", "this vendor")

    for alert in alerts:
        flag = alert.get("flag_type", "")

        if flag == "OUTLIER_AMOUNT" and group_stats:
            mean = group_stats.get("mean_amount", 0)
            median = group_stats.get("median_amount", 0)
            count = group_stats.get("payment_count", 0)
            p25 = group_stats.get("p25_amount", 0)
            p75 = group_stats.get("p75_amount", 0)
            min_amt = group_stats.get("min_amount", 0)
            max_amt = group_stats.get("max_amount", 0)

            ratio = amount / mean if mean > 0 else 0
            sections.append({
                "title": "Why this is an outlier",
                "text": (
                    f"This ${amount:,.2f} payment is {ratio:.1f}x the average payment "
                    f"(${mean:,.2f}) to {vendor}. "
                    f"Out of {count} payments to this vendor, the typical range is "
                    f"${p25:,.2f} to ${p75:,.2f} (25th–75th percentile), "
                    f"with a median of ${median:,.2f}. "
                    f"The overall range is ${min_amt:,.2f} to ${max_amt:,.2f}."
                ),
            })
            if ratio > 10:
                sections.append({
                    "title": "Severity",
                    "text": (
                        f"This payment is more than 10x the average, which is highly unusual. "
                        f"This could indicate a data entry error, a one-time large purchase, "
                        f"or a payment that warrants further investigation."
                    ),
                })
            elif ratio > 3:
                sections.append({
                    "title": "Severity",
                    "text": (
                        f"This payment is {ratio:.1f}x the average. While large payments "
                        f"can be legitimate (e.g. annual contracts, bulk purchases), "
                        f"the size relative to the norm warrants a closer look."
                    ),
                })

        elif flag == "DUPLICATE_PAYMENT":
            sections.append({
                "title": "Possible duplicate",
                "text": alert.get("description", ""),
            })

        elif flag == "NO_CONTRACT_HIGH_VALUE":
            sections.append({
                "title": "No contract on file",
                "text": (
                    f"This ${amount:,.2f} payment was made as a direct voucher "
                    f"without an associated contract. Payments above $25,000 "
                    f"without a contract may indicate procurement policy violations "
                    f"or missing documentation."
                ),
            })

        elif flag == "SPLIT_PAYMENT":
            sections.append({
                "title": "Potential payment splitting",
                "text": alert.get("description", ""),
            })

        else:
            sections.append({
                "title": flag.replace("_", " ").title(),
                "text": alert.get("description", ""),
            })

    return sections


@alerts_bp.route("/summary", methods=["GET"])
def alerts_summary():
    """Return alert counts grouped by flag type plus totals."""
    # TODO: start_date/end_date accepted but not used for alert filtering (see list_alerts)
    _start_date = request.args.get("start_date")  # noqa: F841
    _end_date = request.args.get("end_date")  # noqa: F841

    by_type = _safe_query(
        """
        SELECT flag_type, COUNT(*) AS count, AVG(risk_score) AS avg_risk_score
        FROM alerts
        GROUP BY flag_type
        ORDER BY count DESC
        """
    )

    total_rows = _safe_query("SELECT COUNT(*) AS total FROM alerts")
    total_count = total_rows[0]["total"] if total_rows else 0

    critical_rows = _safe_query(
        "SELECT COUNT(*) AS critical FROM alerts WHERE risk_score > 75"
    )
    critical_count = critical_rows[0]["critical"] if critical_rows else 0

    return jsonify({
        "by_flag_type": by_type,
        "total_count": int(total_count),
        "critical_count": int(critical_count),
    })
