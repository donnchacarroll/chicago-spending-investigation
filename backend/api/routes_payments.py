"""Payment routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db
from backend.analysis.purpose_inference import infer_purpose

payments_bp = Blueprint("payments_bp", __name__, url_prefix="/api/payments")


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


@payments_bp.route("/", methods=["GET"])
def list_payments():
    """Return paginated, filterable list of payments with risk scores."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap
    offset = (page - 1) * per_page

    # Build WHERE clauses
    conditions = ["p.is_annual_aggregate = false"]
    params = []

    department = request.args.get("department")
    if department:
        conditions.append("p.department_canonical = $" + str(len(params) + 1))
        params.append(department)

    vendor = request.args.get("vendor")
    if vendor:
        conditions.append("p.vendor_name ILIKE $" + str(len(params) + 1))
        params.append(f"%{vendor}%")

    min_amount = request.args.get("min_amount", type=float)
    if min_amount is not None:
        conditions.append("p.amount >= $" + str(len(params) + 1))
        params.append(min_amount)

    max_amount = request.args.get("max_amount", type=float)
    if max_amount is not None:
        conditions.append("p.amount <= $" + str(len(params) + 1))
        params.append(max_amount)

    start_date = request.args.get("start_date")
    if start_date:
        conditions.append("p.check_date >= CAST($" + str(len(params) + 1) + " AS TIMESTAMP)")
        params.append(start_date)

    end_date = request.args.get("end_date")
    if end_date:
        conditions.append("p.check_date <= CAST($" + str(len(params) + 1) + " AS TIMESTAMP)")
        params.append(end_date)

    min_risk_score = request.args.get("min_risk_score", type=float)
    if min_risk_score is not None:
        conditions.append("COALESCE(r.composite_score, 0) >= $" + str(len(params) + 1))
        params.append(min_risk_score)

    flag_type = request.args.get("flag_type")
    if flag_type:
        conditions.append(
            "p.voucher_number IN (SELECT voucher_number FROM alerts WHERE flag_type = $"
            + str(len(params) + 1) + ")"
        )
        params.append(flag_type)

    where_clause = " AND ".join(conditions)

    # Count query
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM payments p
        LEFT JOIN payment_risk_scores r ON p.voucher_number = r.voucher_number
        WHERE {where_clause}
    """
    count_rows = _safe_query(count_sql, params)
    total = count_rows[0]["total"] if count_rows else 0

    # Data query
    data_sql = f"""
        SELECT
            p.voucher_number,
            p.amount,
            p.check_date,
            p.department_canonical AS department_name,
            p.vendor_name,
            p.contract_number,
            p.contract_type,
            p.year,
            p.month,
            COALESCE(r.composite_score, 0) AS risk_score
        FROM payments p
        LEFT JOIN payment_risk_scores r ON p.voucher_number = r.voucher_number
        WHERE {where_clause}
        ORDER BY p.check_date DESC
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
    """
    params.extend([per_page, offset])
    data = _safe_query(data_sql, params)

    # Serialize dates
    for row in data:
        if row.get("check_date") is not None:
            row["check_date"] = str(row["check_date"])

    return jsonify({
        "payments": data,
        "total": int(total),
        "page": page,
        "per_page": per_page,
        "total_pages": (int(total) + per_page - 1) // per_page if per_page > 0 else 0,
    })


@payments_bp.route("/<voucher_number>", methods=["GET"])
def payment_detail(voucher_number):
    """Return single payment detail with all associated flags."""
    # Payment info from the enriched table (has contract details)
    payment_rows = _safe_query(
        """
        SELECT
            p.voucher_number, p.amount, p.check_date, p.department_canonical AS department_name,
            p.vendor_name, p.contract_number, p.contract_type,
            p.year, p.month, p.quarter,
            p.spending_category,
            p.dv_subcategory,
            COALESCE(r.composite_score, 0) AS risk_score
        FROM payment_contract_joined p
        LEFT JOIN payment_risk_scores r ON p.voucher_number = r.voucher_number
        WHERE p.voucher_number = $1
        LIMIT 1
        """,
        [voucher_number],
    )

    if not payment_rows:
        return jsonify({"error": "Payment not found"}), 404

    payment = payment_rows[0]
    if payment.get("check_date") is not None:
        payment["check_date"] = str(payment["check_date"])

    # Contract details if this payment has a contract
    contract = None
    if payment.get("contract_number") and payment["contract_type"] == "contract":
        contract_rows = _safe_query(
            """
            SELECT
                purchase_order_contract_number AS contract_number,
                purchase_order_description AS description,
                contract_type AS contract_type_desc,
                procurement_type,
                award_amount,
                start_date,
                end_date,
                approval_date,
                specification_number,
                vendor_name AS contract_vendor,
                vendor_id,
                address_1, city, state, zip,
                contract_pdf.url AS pdf_url
            FROM contracts
            WHERE purchase_order_contract_number = $1
            LIMIT 1
            """,
            [str(payment["contract_number"])],
        )
        if contract_rows:
            contract = contract_rows[0]
            for key in ("start_date", "end_date", "approval_date"):
                if contract.get(key) is not None:
                    contract[key] = str(contract[key])

            # How much has been paid against this contract total?
            totals = _safe_query(
                """
                SELECT SUM(amount) AS total_paid, COUNT(*) AS payment_count
                FROM payment_contract_joined
                WHERE contract_number = $1
                  AND contract_type = 'contract'
                  AND is_annual_aggregate = false
                """,
                [str(payment["contract_number"])],
            )
            if totals:
                contract["total_paid_on_contract"] = float(totals[0].get("total_paid") or 0)
                contract["contract_payment_count"] = int(totals[0].get("payment_count") or 0)

    # Other payments to same vendor (for context)
    vendor_context = _safe_query(
        """
        SELECT COUNT(*) AS total_payments,
               SUM(amount) AS total_paid,
               AVG(amount) AS avg_payment
        FROM payment_contract_joined
        WHERE vendor_name = $1
          AND is_annual_aggregate = false
        """,
        [payment["vendor_name"]],
    )

    # Associated flags
    flags = _safe_query(
        """
        SELECT flag_type, description, risk_score, vendor_name,
               department_name, amount
        FROM alerts
        WHERE voucher_number = $1
        ORDER BY risk_score DESC
        """,
        [voucher_number],
    )

    payment["flags"] = flags
    payment["contract"] = contract
    payment["vendor_context"] = vendor_context[0] if vendor_context else {}

    # Infer likely purpose
    payment["inferred_purpose"] = infer_purpose(
        vendor_name=payment.get("vendor_name", ""),
        amount=payment.get("amount", 0),
        contract_type=payment.get("contract_type", ""),
        dv_subcategory=payment.get("dv_subcategory", ""),
        spending_category=payment.get("spending_category", ""),
    )

    return jsonify(payment)
