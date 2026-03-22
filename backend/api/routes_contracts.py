"""Contract routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db

contracts_bp = Blueprint("contracts_bp", __name__, url_prefix="/api/contracts")


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


def _build_date_filter(start_date, end_date, prefix="", start_idx=1):
    """Build date filter conditions and params list.

    Returns (conditions_string, params_list, next_param_idx).
    """
    col = f"{prefix}check_date" if prefix else "check_date"
    conditions = ""
    params = []
    param_idx = start_idx
    if start_date:
        conditions += f" AND {col} >= CAST(${param_idx} AS TIMESTAMP)"
        params.append(start_date)
        param_idx += 1
    if end_date:
        conditions += f" AND {col} <= CAST(${param_idx} AS TIMESTAMP)"
        params.append(end_date)
        param_idx += 1
    return conditions, params, param_idx


def _serialize_row(row):
    """Convert date/datetime objects in a dict to strings."""
    import datetime

    for key, val in row.items():
        if isinstance(val, (datetime.date, datetime.datetime)):
            row[key] = str(val)
    return row


@contracts_bp.route("/summary", methods=["GET"])
def contracts_summary():
    """Contract summary statistics."""
    # Total contracts and award value (latest revision only)
    totals = _safe_query(
        """
        SELECT
            COUNT(*) AS total_contracts,
            COALESCE(SUM(award_amount), 0) AS total_award_value
        FROM (
            SELECT purchase_order_contract_number, award_amount,
                ROW_NUMBER() OVER (
                    PARTITION BY purchase_order_contract_number
                    ORDER BY COALESCE(TRY_CAST(revision_number AS INT), 0) DESC
                ) AS rn
            FROM contracts
        ) sub WHERE rn = 1
        """
    )

    # Total paid from payment_contract_joined
    paid_rows = _safe_query(
        """
        SELECT COALESCE(SUM(amount), 0) AS total_paid
        FROM payment_contract_joined
        WHERE contract_type = 'contract'
          AND is_annual_aggregate = false
        """
    )

    # Overspent contracts (paid > 110% of award)
    overspent_rows = _safe_query(
        """
        SELECT
            COUNT(*) AS overspent_count,
            COALESCE(SUM(total_paid - award_amount), 0) AS overspent_total_excess
        FROM (
            SELECT contract_number, award_amount, SUM(amount) AS total_paid
            FROM payment_contract_joined
            WHERE contract_type = 'contract'
              AND is_annual_aggregate = false
              AND award_amount > 0
            GROUP BY contract_number, award_amount
            HAVING SUM(amount) > award_amount * 1.1
        ) sub
        """
    )

    # Breakdown by contract type
    by_type = _safe_query(
        """
        SELECT
            COALESCE(contract_type, 'Unknown') AS contract_type,
            COUNT(*) AS count,
            COALESCE(SUM(award_amount), 0) AS total_award
        FROM contracts
        GROUP BY 1
        ORDER BY total_award DESC
        """
    )

    # Breakdown by procurement type
    by_procurement = _safe_query(
        """
        SELECT
            COALESCE(procurement_type, 'Unknown') AS procurement_type,
            COUNT(*) AS count,
            COALESCE(SUM(award_amount), 0) AS total_award
        FROM contracts
        GROUP BY 1
        ORDER BY total_award DESC
        """
    )

    return jsonify({
        "total_contracts": totals[0]["total_contracts"] if totals else 0,
        "total_award_value": float(totals[0]["total_award_value"]) if totals else 0,
        "total_paid": float(paid_rows[0]["total_paid"]) if paid_rows else 0,
        "overspent_count": int(overspent_rows[0]["overspent_count"]) if overspent_rows else 0,
        "overspent_total_excess": float(overspent_rows[0]["overspent_total_excess"]) if overspent_rows else 0,
        "by_type": by_type,
        "by_procurement": by_procurement,
    })


@contracts_bp.route("/", methods=["GET"])
def contracts_list():
    """Paginated, filterable contract list with payment data."""
    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    # Filters
    search = request.args.get("search")
    department = request.args.get("department")
    contract_type = request.args.get("contract_type")
    procurement_type = request.args.get("procurement_type")
    min_award = request.args.get("min_award", type=float)
    max_award = request.args.get("max_award", type=float)
    overspend_only = request.args.get("overspend_only", "").lower() == "true"
    sort = request.args.get("sort", "award_amount")
    sort_dir = request.args.get("sort_dir", "desc").upper()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if sort_dir not in ("ASC", "DESC"):
        sort_dir = "DESC"

    # Allowed sort columns to prevent SQL injection
    allowed_sorts = {
        "award_amount", "total_paid", "overspend_ratio", "payment_count",
        "contract_number", "vendor_name", "department", "start_date", "end_date",
        "description",
    }
    if sort not in allowed_sorts:
        sort = "award_amount"

    # Build CTE date filter
    cte_date_conditions = ""
    cte_params = []
    param_idx = 1
    if start_date:
        cte_date_conditions += f" AND check_date >= CAST(${param_idx} AS TIMESTAMP)"
        cte_params.append(start_date)
        param_idx += 1
    if end_date:
        cte_date_conditions += f" AND check_date <= CAST(${param_idx} AS TIMESTAMP)"
        cte_params.append(end_date)
        param_idx += 1

    # Build WHERE conditions for the main query
    where_conditions = ""
    main_params = []

    if search:
        where_conditions += (
            f" AND (c.purchase_order_description ILIKE ${param_idx}"
            f" OR c.vendor_name ILIKE ${param_idx}"
            f" OR c.purchase_order_contract_number ILIKE ${param_idx})"
        )
        main_params.append(f"%{search}%")
        param_idx += 1

    if department:
        where_conditions += f" AND c.department = ${param_idx}"
        main_params.append(department)
        param_idx += 1

    if contract_type:
        where_conditions += f" AND c.contract_type = ${param_idx}"
        main_params.append(contract_type)
        param_idx += 1

    if procurement_type:
        where_conditions += f" AND c.procurement_type = ${param_idx}"
        main_params.append(procurement_type)
        param_idx += 1

    if min_award is not None:
        where_conditions += f" AND c.award_amount >= ${param_idx}"
        main_params.append(min_award)
        param_idx += 1

    if max_award is not None:
        where_conditions += f" AND c.award_amount <= ${param_idx}"
        main_params.append(max_award)
        param_idx += 1

    if overspend_only:
        where_conditions += (
            " AND COALESCE(cp.total_paid, 0) > c.award_amount * 1.1"
            " AND c.award_amount > 0"
        )

    all_params = cte_params + main_params

    # CTE: deduplicate contracts to latest revision + aggregate payments
    ctes = f"""
        WITH latest_contracts AS (
            SELECT purchase_order_contract_number, purchase_order_description,
                   vendor_name, vendor_id, department, award_amount,
                   start_date, end_date, approval_date, contract_type,
                   procurement_type, specification_number,
                   address_1, address_2, city, state, zip,
                   revision_number, contract_pdf
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY purchase_order_contract_number
                        ORDER BY COALESCE(TRY_CAST(revision_number AS INT), 0) DESC
                    ) AS rn
                FROM contracts
            ) sub WHERE rn = 1
        ),
        contract_payments AS (
            SELECT
                contract_number,
                SUM(amount) AS total_paid,
                COUNT(*) AS payment_count
            FROM payment_contract_joined
            WHERE contract_type = 'contract' AND is_annual_aggregate = false{cte_date_conditions}
            GROUP BY contract_number
        )"""

    # Count query
    count_sql = f"""
        {ctes}
        SELECT COUNT(*) AS total
        FROM latest_contracts c
        LEFT JOIN contract_payments cp ON c.purchase_order_contract_number = cp.contract_number
        WHERE 1=1{where_conditions}
    """
    count_rows = _safe_query(count_sql, all_params if all_params else None)
    total = count_rows[0]["total"] if count_rows else 0

    # Pagination params
    limit_param_idx = param_idx
    offset_param_idx = param_idx + 1
    all_params_with_paging = all_params + [per_page, offset]

    # Data query
    data_sql = f"""
        {ctes}
        SELECT
            c.purchase_order_contract_number AS contract_number,
            c.purchase_order_description AS description,
            c.vendor_name,
            c.department,
            CAST(c.award_amount AS DOUBLE) AS award_amount,
            COALESCE(cp.total_paid, 0) AS total_paid,
            CASE WHEN c.award_amount > 0
                 THEN COALESCE(cp.total_paid, 0) / CAST(c.award_amount AS DOUBLE)
                 ELSE NULL END AS overspend_ratio,
            COALESCE(cp.payment_count, 0) AS payment_count,
            c.start_date,
            c.end_date,
            c.contract_type,
            c.procurement_type,
            c.contract_pdf.url AS pdf_url
        FROM latest_contracts c
        LEFT JOIN contract_payments cp ON c.purchase_order_contract_number = cp.contract_number
        WHERE 1=1{where_conditions}
        ORDER BY {sort} {sort_dir} NULLS LAST
        LIMIT ${limit_param_idx} OFFSET ${offset_param_idx}
    """
    rows = _safe_query(data_sql, all_params_with_paging)
    for row in rows:
        _serialize_row(row)

    return jsonify({
        "contracts": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    })


@contracts_bp.route("/repeat-overspenders", methods=["GET"])
def repeat_overspenders():
    """Vendors who repeatedly exceed contract values across multiple contracts."""
    min_contracts = request.args.get("min_contracts", 2, type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    base_sql = """
        WITH contract_totals AS (
            SELECT contract_number, vendor_name, award_amount,
                   SUM(amount) AS total_paid
            FROM payment_contract_joined
            WHERE contract_type = 'contract' AND is_annual_aggregate = false
              AND award_amount > 0
            GROUP BY contract_number, vendor_name, award_amount
            HAVING SUM(amount) > award_amount * 1.1
        ),
        vendor_summary AS (
            SELECT vendor_name,
                   COUNT(*) AS overspent_contracts,
                   SUM(total_paid - award_amount) AS total_excess,
                   SUM(award_amount) AS total_awarded,
                   SUM(total_paid) AS total_paid,
                   ROUND(AVG(total_paid / award_amount), 2) AS avg_ratio
            FROM contract_totals
            GROUP BY vendor_name
            HAVING COUNT(*) >= $1
        )
    """

    count_rows = _safe_query(
        f"{base_sql} SELECT COUNT(*) AS total FROM vendor_summary",
        [min_contracts],
    )
    total = count_rows[0]["total"] if count_rows else 0

    vendors = _safe_query(
        f"""{base_sql}
        SELECT * FROM vendor_summary
        ORDER BY total_excess DESC
        LIMIT $2 OFFSET $3""",
        [min_contracts, per_page, offset],
    )

    # Total excess across all repeat overspenders
    totals = _safe_query(
        f"""{base_sql}
        SELECT SUM(total_excess) AS grand_excess,
               SUM(overspent_contracts) AS grand_contracts
        FROM vendor_summary""",
        [min_contracts],
    )

    return jsonify({
        "vendors": vendors,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "grand_total_excess": float(totals[0]["grand_excess"] or 0) if totals else 0,
        "grand_total_contracts": int(totals[0]["grand_contracts"] or 0) if totals else 0,
    })


@contracts_bp.route("/repeat-overspenders/<vendor_name>", methods=["GET"])
def overspender_detail(vendor_name):
    """Detail for a specific repeat overspender — all their overspent contracts."""
    contracts = _safe_query(
        """
        SELECT contract_number, award_amount, SUM(amount) AS total_paid,
               ROUND(SUM(amount) / award_amount, 2) AS ratio,
               MIN(check_date) AS first_payment, MAX(check_date) AS last_payment,
               COUNT(*) AS payment_count
        FROM payment_contract_joined
        WHERE vendor_name = $1 AND contract_type = 'contract'
          AND is_annual_aggregate = false AND award_amount > 0
        GROUP BY contract_number, award_amount
        HAVING SUM(amount) > award_amount * 1.1
        ORDER BY (SUM(amount) - award_amount) DESC
        """,
        [vendor_name],
    )
    for row in contracts:
        _serialize_row(row)

    # Also get their non-overspent contracts for context
    normal = _safe_query(
        """
        SELECT contract_number, award_amount, SUM(amount) AS total_paid,
               ROUND(SUM(amount) / NULLIF(award_amount, 0), 2) AS ratio,
               COUNT(*) AS payment_count
        FROM payment_contract_joined
        WHERE vendor_name = $1 AND contract_type = 'contract'
          AND is_annual_aggregate = false AND award_amount > 0
        GROUP BY contract_number, award_amount
        HAVING SUM(amount) <= award_amount * 1.1
        ORDER BY total_paid DESC
        """,
        [vendor_name],
    )

    return jsonify({
        "vendor_name": vendor_name,
        "overspent_contracts": contracts,
        "normal_contracts": normal,
        "total_overspent": len(contracts),
        "total_normal": len(normal),
        "total_excess": sum(
            (c.get("total_paid", 0) - c.get("award_amount", 0))
            for c in contracts
        ),
    })


@contracts_bp.route("/<contract_number>", methods=["GET"])
def contract_detail(contract_number):
    """Full detail for a single contract including payments and monthly spending."""
    # Contract info with payment totals
    contract_rows = _safe_query(
        """
        WITH contract_payments AS (
            SELECT
                contract_number,
                SUM(amount) AS total_paid,
                COUNT(*) AS payment_count
            FROM payment_contract_joined
            WHERE contract_type = 'contract' AND is_annual_aggregate = false
            GROUP BY contract_number
        )
        SELECT
            c.purchase_order_contract_number AS contract_number,
            c.purchase_order_description AS description,
            c.revision_number,
            c.specification_number,
            c.contract_type,
            c.approval_date,
            c.department,
            c.vendor_name,
            c.vendor_id,
            c.address_1,
            c.address_2,
            c.city,
            c.state,
            c.zip,
            CAST(c.award_amount AS DOUBLE) AS award_amount,
            c.start_date,
            c.end_date,
            c.procurement_type,
            c.contract_pdf.url AS pdf_url,
            COALESCE(cp.total_paid, 0) AS total_paid,
            COALESCE(cp.payment_count, 0) AS payment_count,
            CASE WHEN c.award_amount > 0
                 THEN COALESCE(cp.total_paid, 0) / CAST(c.award_amount AS DOUBLE)
                 ELSE NULL END AS overspend_ratio
        FROM (
            SELECT purchase_order_contract_number, purchase_order_description,
                   vendor_name, vendor_id, department, award_amount,
                   start_date, end_date, approval_date, contract_type,
                   procurement_type, specification_number, revision_number,
                   address_1, address_2, city, state, zip, contract_pdf
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY purchase_order_contract_number
                        ORDER BY COALESCE(TRY_CAST(revision_number AS INT), 0) DESC
                    ) AS rn
                FROM contracts
            ) sub WHERE rn = 1
        ) c
        LEFT JOIN contract_payments cp ON c.purchase_order_contract_number = cp.contract_number
        WHERE c.purchase_order_contract_number = $1
        """,
        [contract_number],
    )

    if not contract_rows:
        return jsonify({"error": "Contract not found"}), 404

    contract = _serialize_row(contract_rows[0])

    # Also include revision history for context
    revisions = _safe_query(
        """
        SELECT revision_number, CAST(award_amount AS DOUBLE) AS award_amount,
               start_date, end_date
        FROM contracts
        WHERE purchase_order_contract_number = $1
        ORDER BY COALESCE(TRY_CAST(revision_number AS INT), 0)
        """,
        [contract_number],
    )
    for rev in revisions:
        _serialize_row(rev)

    # Individual payments for this contract
    payments = _safe_query(
        """
        SELECT
            voucher_number,
            amount,
            check_date,
            department_canonical AS department,
            vendor_name,
            year,
            month
        FROM payment_contract_joined
        WHERE contract_number = $1
          AND contract_type = 'contract'
          AND is_annual_aggregate = false
        ORDER BY check_date DESC
        """,
        [contract_number],
    )
    for row in payments:
        _serialize_row(row)

    # Monthly aggregated spending
    monthly_spending = _safe_query(
        """
        SELECT
            DATE_TRUNC('month', check_date) AS month,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count
        FROM payment_contract_joined
        WHERE contract_number = $1
          AND contract_type = 'contract'
          AND is_annual_aggregate = false
        GROUP BY 1
        ORDER BY 1
        """,
        [contract_number],
    )
    for row in monthly_spending:
        _serialize_row(row)

    return jsonify({
        "contract": contract,
        "payments": payments,
        "monthly_spending": monthly_spending,
        "revisions": revisions,
    })
