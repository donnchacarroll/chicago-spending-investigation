"""Vendor network analysis routes for the Chicago spending investigation API.

Provides shell-company detection signals: address clustering, vendor aliases,
and risk assessment for vendor networks sharing addresses or identifiers.
"""

import datetime
from urllib.parse import unquote

from flask import Blueprint, jsonify, request
from backend.api.db import get_db

network_bp = Blueprint("network_bp", __name__, url_prefix="/api/network")


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


def _serialize_row(row):
    """Convert date/datetime objects and lists in a dict to JSON-safe types."""
    for key, val in row.items():
        if isinstance(val, (datetime.date, datetime.datetime)):
            row[key] = str(val)
        elif isinstance(val, list):
            row[key] = [str(v) if isinstance(v, (datetime.date, datetime.datetime)) else v for v in val]
    return row


def _compute_risk_flags(vendors, departments, cluster_total_awards):
    """Compute risk flags for an address cluster."""
    flags = []

    # Check for JV / joint venture entities
    jv_count = 0
    for v in vendors:
        name_upper = v.upper() if isinstance(v, str) else ""
        if "JV" in name_upper or "JOINT VENTURE" in name_upper or "/" in v:
            jv_count += 1
    if jv_count >= 2:
        flags.append("Multiple JV entities at same address")

    # Single department client
    if len(departments) == 1:
        flags.append("Single department client")

    return flags


def _compute_cluster_risk_flags_with_data(vendors_data, departments):
    """Compute risk flags using full vendor award data for a cluster."""
    flags = []

    # JV entities
    jv_count = 0
    for v in vendors_data:
        name_upper = v.get("vendor_name", "").upper()
        if "JV" in name_upper or "JOINT VENTURE" in name_upper or "/" in v.get("vendor_name", ""):
            jv_count += 1
    if jv_count >= 2:
        flags.append("Multiple JV entities at same address")

    # Single department client
    if len(departments) == 1:
        flags.append("Single department client")

    # High award concentration
    total_awards = sum(v.get("total_awards", 0) or 0 for v in vendors_data)
    if total_awards > 0:
        for v in vendors_data:
            vendor_awards = v.get("total_awards", 0) or 0
            if vendor_awards / total_awards > 0.70:
                flags.append("High award concentration")
                break

    # Sole source contracts
    for v in vendors_data:
        if v.get("has_sole_source"):
            flags.append("Sole source contracts")
            break

    return flags


# ---------------------------------------------------------------------------
# GET /api/network/address-clusters
# ---------------------------------------------------------------------------
@network_bp.route("/address-clusters", methods=["GET"])
def address_clusters():
    """Find vendors sharing the same address -- key shell-company detection signal."""
    min_vendors = request.args.get("min_vendors", 2, type=int)
    sort = request.args.get("sort", "vendor_count")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    allowed_sorts = {"vendor_count": "vendor_count DESC", "total_awards": "total_awards DESC"}
    order_clause = allowed_sorts.get(sort, "vendor_count DESC")

    # Count total clusters
    count_sql = """
        WITH vendor_addresses AS (
            SELECT DISTINCT
                vendor_name,
                TRIM(REGEXP_REPLACE(address_1, '\\s*EFT\\s*$', '')) AS address_clean,
                city,
                COALESCE(zip, '') AS zip,
                vendor_id
            FROM contracts
            WHERE address_1 IS NOT NULL
              AND address_1 != ''
              AND LENGTH(TRIM(address_1)) > 5
        ),
        address_groups AS (
            SELECT
                address_clean,
                city,
                zip,
                COUNT(DISTINCT vendor_name) AS vendor_count
            FROM vendor_addresses
            GROUP BY address_clean, city, zip
            HAVING COUNT(DISTINCT vendor_name) >= $1
        )
        SELECT COUNT(*) AS total FROM address_groups
    """
    count_rows = _safe_query(count_sql, [min_vendors])
    total_clusters = count_rows[0]["total"] if count_rows else 0

    # Main cluster query with award totals
    data_sql = f"""
        WITH vendor_addresses AS (
            SELECT DISTINCT
                vendor_name,
                TRIM(REGEXP_REPLACE(address_1, '\\s*EFT\\s*$', '')) AS address_clean,
                city,
                COALESCE(zip, '') AS zip,
                vendor_id,
                department,
                award_amount,
                procurement_type
            FROM contracts
            WHERE address_1 IS NOT NULL
              AND address_1 != ''
              AND LENGTH(TRIM(address_1)) > 5
        ),
        address_groups AS (
            SELECT
                address_clean,
                city,
                zip,
                COUNT(DISTINCT vendor_name) AS vendor_count,
                LIST(DISTINCT vendor_name ORDER BY vendor_name) AS vendors,
                LIST(DISTINCT vendor_id ORDER BY vendor_id) AS vendor_ids,
                COALESCE(SUM(award_amount), 0) AS total_awards,
                LIST(DISTINCT department ORDER BY department) AS departments,
                BOOL_OR(UPPER(procurement_type) LIKE '%SOLE%SOURCE%') AS has_sole_source
            FROM vendor_addresses
            GROUP BY address_clean, city, zip
            HAVING COUNT(DISTINCT vendor_name) >= $1
        )
        SELECT * FROM address_groups
        ORDER BY {order_clause}
        LIMIT $2 OFFSET $3
    """
    clusters_raw = _safe_query(data_sql, [min_vendors, per_page, offset])

    # Enrich clusters with payment totals and risk flags
    clusters = []
    for row in clusters_raw:
        vendors_list = row.get("vendors", [])
        departments_list = row.get("departments", [])
        departments_list = [d for d in departments_list if d]

        risk_flags = _compute_risk_flags(vendors_list, departments_list, row.get("total_awards", 0))

        # Check sole source from the query
        if row.get("has_sole_source"):
            risk_flags.append("Sole source contracts")

        # Check high award concentration: get per-vendor awards for this cluster
        # We use the vendor list to query per-vendor totals
        # For performance, approximate from the aggregate query
        if len(vendors_list) > 0 and row.get("total_awards", 0) > 0:
            # Query per-vendor awards for this address
            vendor_awards_sql = """
                SELECT
                    vendor_name,
                    COALESCE(SUM(award_amount), 0) AS vendor_total
                FROM contracts
                WHERE TRIM(REGEXP_REPLACE(address_1, '\\s*EFT\\s*$', '')) = $1
                  AND city = $2
                  AND COALESCE(zip, '') = $3
                GROUP BY vendor_name
                ORDER BY vendor_total DESC
                LIMIT 1
            """
            top_vendor = _safe_query(vendor_awards_sql, [
                row["address_clean"], row.get("city", ""), row.get("zip", "")
            ])
            if top_vendor and row["total_awards"] > 0:
                top_pct = (top_vendor[0]["vendor_total"] or 0) / row["total_awards"]
                if top_pct > 0.70:
                    risk_flags.append("High award concentration")

        # Get total paid for cluster vendors
        if vendors_list:
            placeholders = ", ".join([f"${i+1}" for i in range(len(vendors_list))])
            paid_sql = f"""
                SELECT COALESCE(SUM(amount), 0) AS total_paid
                FROM payment_contract_joined
                WHERE vendor_name IN ({placeholders})
                  AND is_annual_aggregate = false
            """
            paid_rows = _safe_query(paid_sql, vendors_list)
            total_paid = float(paid_rows[0]["total_paid"]) if paid_rows else 0
        else:
            total_paid = 0

        clusters.append({
            "address": row.get("address_clean", ""),
            "city": row.get("city", ""),
            "zip": row.get("zip", ""),
            "vendor_count": row.get("vendor_count", 0),
            "vendors": vendors_list,
            "total_awards": float(row.get("total_awards", 0)),
            "total_paid": total_paid,
            "departments": departments_list,
            "risk_flags": risk_flags,
        })

    # Summary stats
    summary_sql = """
        WITH vendor_addresses AS (
            SELECT DISTINCT
                vendor_name,
                TRIM(REGEXP_REPLACE(address_1, '\\s*EFT\\s*$', '')) AS address_clean,
                city,
                COALESCE(zip, '') AS zip,
                award_amount
            FROM contracts
            WHERE address_1 IS NOT NULL
              AND address_1 != ''
              AND LENGTH(TRIM(address_1)) > 5
        ),
        address_groups AS (
            SELECT
                address_clean, city, zip,
                COUNT(DISTINCT vendor_name) AS vendor_count,
                COALESCE(SUM(award_amount), 0) AS total_awards
            FROM vendor_addresses
            GROUP BY address_clean, city, zip
            HAVING COUNT(DISTINCT vendor_name) >= $1
        )
        SELECT
            COUNT(*) AS total_clusters,
            COALESCE(SUM(vendor_count), 0) AS total_vendors_in_clusters,
            COALESCE(SUM(total_awards), 0) AS total_awards_in_clusters
        FROM address_groups
    """
    summary_rows = _safe_query(summary_sql, [min_vendors])
    summary = summary_rows[0] if summary_rows else {}

    return jsonify({
        "clusters": clusters,
        "total_clusters": int(summary.get("total_clusters", total_clusters)),
        "total_vendors_in_clusters": int(summary.get("total_vendors_in_clusters", 0)),
        "total_awards_in_clusters": float(summary.get("total_awards_in_clusters", 0)),
        "page": page,
        "per_page": per_page,
        "total_pages": (total_clusters + per_page - 1) // per_page if per_page > 0 else 0,
    })


# ---------------------------------------------------------------------------
# GET /api/network/vendor-aliases
# ---------------------------------------------------------------------------
@network_bp.route("/vendor-aliases", methods=["GET"])
def vendor_aliases():
    """Find vendors sharing the same vendor_id but with different names."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    count_sql = """
        SELECT COUNT(*) AS total FROM (
            SELECT vendor_id
            FROM contracts
            WHERE vendor_id IS NOT NULL AND vendor_id != ''
            GROUP BY vendor_id
            HAVING COUNT(DISTINCT vendor_name) >= 2
        ) sub
    """
    count_rows = _safe_query(count_sql)
    total_groups = count_rows[0]["total"] if count_rows else 0

    data_sql = """
        WITH alias_groups AS (
            SELECT
                vendor_id,
                LIST(DISTINCT vendor_name ORDER BY vendor_name) AS names,
                COALESCE(SUM(award_amount), 0) AS total_awards,
                COUNT(*) AS contract_count,
                LIST(DISTINCT department ORDER BY department) AS departments
            FROM contracts
            WHERE vendor_id IS NOT NULL AND vendor_id != ''
            GROUP BY vendor_id
            HAVING COUNT(DISTINCT vendor_name) >= 2
        )
        SELECT * FROM alias_groups
        ORDER BY total_awards DESC
        LIMIT $1 OFFSET $2
    """
    rows = _safe_query(data_sql, [per_page, offset])

    aliases = []
    for row in rows:
        names = row.get("names", [])
        # Get total paid across all alias names
        if names:
            placeholders = ", ".join([f"${i+1}" for i in range(len(names))])
            paid_sql = f"""
                SELECT COALESCE(SUM(amount), 0) AS total_paid
                FROM payment_contract_joined
                WHERE vendor_name IN ({placeholders})
                  AND is_annual_aggregate = false
            """
            paid_rows = _safe_query(paid_sql, names)
            total_paid = float(paid_rows[0]["total_paid"]) if paid_rows else 0
        else:
            total_paid = 0

        departments = [d for d in row.get("departments", []) if d]

        aliases.append({
            "vendor_id": row.get("vendor_id", ""),
            "names": names,
            "total_awards": float(row.get("total_awards", 0)),
            "total_paid": total_paid,
            "contract_count": row.get("contract_count", 0),
            "departments": departments,
        })

    return jsonify({
        "aliases": aliases,
        "total_alias_groups": total_groups,
        "page": page,
        "per_page": per_page,
        "total_pages": (total_groups + per_page - 1) // per_page if per_page > 0 else 0,
    })


# ---------------------------------------------------------------------------
# GET /api/network/cluster/<address>
# ---------------------------------------------------------------------------
@network_bp.route("/cluster/<path:address>", methods=["GET"])
def cluster_detail(address):
    """Drill into a specific address cluster with full vendor and contract detail."""
    address = unquote(address).strip()

    # Parse address -- expect format "ADDRESS, CITY ZIP" or just the address_1 value
    # Try to match on address_1 alone first
    vendors_sql = """
        SELECT DISTINCT
            vendor_name,
            vendor_id,
            TRIM(REGEXP_REPLACE(address_1, '\\s*EFT\\s*$', '')) AS address_clean,
            city,
            COALESCE(zip, '') AS zip
        FROM contracts
        WHERE TRIM(REGEXP_REPLACE(address_1, '\\s*EFT\\s*$', '')) = $1
          AND address_1 IS NOT NULL
    """
    vendors_at_address = _safe_query(vendors_sql, [address])

    if not vendors_at_address:
        return jsonify({"error": "No vendors found at this address"}), 404

    # Determine city/zip from first match
    cluster_city = vendors_at_address[0].get("city", "")
    cluster_zip = vendors_at_address[0].get("zip", "")
    full_address = f"{address}, {cluster_city} {cluster_zip}".strip().rstrip(",")

    # Get unique vendor names
    vendor_names = list({v["vendor_name"] for v in vendors_at_address})

    # Build detailed vendor info
    vendors_detail = []
    all_departments = set()
    all_vendor_awards = []
    sole_source_count = 0

    for vname in sorted(vendor_names):
        # Get contracts for this vendor at this address
        contracts_sql = """
            SELECT
                purchase_order_contract_number AS contract_number,
                purchase_order_description AS description,
                CAST(award_amount AS DOUBLE) AS award_amount,
                department,
                procurement_type,
                contract_type,
                contract_pdf.url AS pdf_url
            FROM contracts
            WHERE vendor_name = $1
              AND TRIM(REGEXP_REPLACE(address_1, '\\s*EFT\\s*$', '')) = $2
            ORDER BY award_amount DESC
        """
        contracts = _safe_query(contracts_sql, [vname, address])
        for c in contracts:
            _serialize_row(c)
            if c.get("department"):
                all_departments.add(c["department"])
            if c.get("procurement_type") and "SOLE" in c["procurement_type"].upper() and "SOURCE" in c["procurement_type"].upper():
                sole_source_count += 1

        vendor_total_awards = sum(c.get("award_amount", 0) or 0 for c in contracts)
        all_vendor_awards.append({"vendor_name": vname, "total_awards": vendor_total_awards})

        # Get vendor_id
        vid = None
        for v in vendors_at_address:
            if v["vendor_name"] == vname:
                vid = v.get("vendor_id")
                break

        # Get total paid
        paid_sql = """
            SELECT COALESCE(SUM(amount), 0) AS total_paid
            FROM payment_contract_joined
            WHERE vendor_name = $1
              AND is_annual_aggregate = false
        """
        paid_rows = _safe_query(paid_sql, [vname])
        total_paid = float(paid_rows[0]["total_paid"]) if paid_rows else 0

        # Get departments from payments
        dept_sql = """
            SELECT DISTINCT department_canonical AS department
            FROM payment_contract_joined
            WHERE vendor_name = $1
              AND is_annual_aggregate = false
              AND department_canonical IS NOT NULL
        """
        vendor_depts = _safe_query(dept_sql, [vname])
        vendor_dept_list = [d["department"] for d in vendor_depts]

        vendors_detail.append({
            "vendor_name": vname,
            "vendor_id": vid,
            "contracts": contracts,
            "total_awards": vendor_total_awards,
            "total_paid": total_paid,
            "departments": vendor_dept_list,
        })

    # Shared departments (departments that have contracts with 2+ vendors in cluster)
    dept_vendor_count = {}
    for vd in vendors_detail:
        for d in vd["departments"]:
            dept_vendor_count[d] = dept_vendor_count.get(d, 0) + 1
    shared_departments = [d for d, count in dept_vendor_count.items() if count >= 2]

    # Risk assessment
    total_awards = sum(va["total_awards"] for va in all_vendor_awards)
    jv_count = sum(
        1 for va in all_vendor_awards
        if "JV" in va["vendor_name"].upper()
        or "JOINT VENTURE" in va["vendor_name"].upper()
        or "/" in va["vendor_name"]
    )

    largest_vendor_pct = 0
    if total_awards > 0:
        largest_vendor_pct = round(
            max(va["total_awards"] for va in all_vendor_awards) / total_awards * 100, 1
        )

    single_department_pct = 0
    if all_departments and total_awards > 0:
        # Calculate what % of awards go to the most common department
        dept_awards = {}
        for vd in vendors_detail:
            for c in vd["contracts"]:
                dept = c.get("department", "Unknown")
                dept_awards[dept] = dept_awards.get(dept, 0) + (c.get("award_amount", 0) or 0)
        if dept_awards:
            max_dept_awards = max(dept_awards.values())
            single_department_pct = round(max_dept_awards / total_awards * 100, 1)

    return jsonify({
        "address": full_address,
        "vendors": vendors_detail,
        "shared_departments": shared_departments,
        "risk_assessment": {
            "jv_entities": jv_count,
            "sole_source_contracts": sole_source_count,
            "single_department_pct": single_department_pct,
            "largest_vendor_pct": largest_vendor_pct,
        },
    })


# ---------------------------------------------------------------------------
# GET /api/network/summary
# ---------------------------------------------------------------------------
@network_bp.route("/summary", methods=["GET"])
def network_summary():
    """Overview stats for the network analysis page."""

    # Address cluster stats
    cluster_stats_sql = """
        WITH vendor_addresses AS (
            SELECT DISTINCT
                vendor_name,
                TRIM(REGEXP_REPLACE(address_1, '\\s*EFT\\s*$', '')) AS address_clean,
                city,
                COALESCE(zip, '') AS zip,
                award_amount
            FROM contracts
            WHERE address_1 IS NOT NULL
              AND address_1 != ''
              AND LENGTH(TRIM(address_1)) > 5
        ),
        address_groups AS (
            SELECT
                address_clean, city, zip,
                COUNT(DISTINCT vendor_name) AS vendor_count,
                COALESCE(SUM(award_amount), 0) AS total_awards
            FROM vendor_addresses
            GROUP BY address_clean, city, zip
            HAVING COUNT(DISTINCT vendor_name) >= 2
        )
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN vendor_count >= 3 THEN 1 ELSE 0 END), 0) AS with_3plus,
            COALESCE(SUM(total_awards), 0) AS total_awards
        FROM address_groups
    """
    cluster_rows = _safe_query(cluster_stats_sql)
    cluster_stats = cluster_rows[0] if cluster_rows else {"total": 0, "with_3plus": 0, "total_awards": 0}

    # Vendor alias stats
    alias_stats_sql = """
        WITH alias_groups AS (
            SELECT
                vendor_id,
                COALESCE(SUM(award_amount), 0) AS total_awards
            FROM contracts
            WHERE vendor_id IS NOT NULL AND vendor_id != ''
            GROUP BY vendor_id
            HAVING COUNT(DISTINCT vendor_name) >= 2
        )
        SELECT
            COUNT(*) AS total_groups,
            COALESCE(SUM(total_awards), 0) AS total_awards
        FROM alias_groups
    """
    alias_rows = _safe_query(alias_stats_sql)
    alias_stats = alias_rows[0] if alias_rows else {"total_groups": 0, "total_awards": 0}

    # Sole source stats
    sole_source_sql = """
        SELECT
            COUNT(DISTINCT vendor_name) AS total_vendors,
            COALESCE(SUM(award_amount), 0) AS total_awards
        FROM contracts
        WHERE UPPER(procurement_type) LIKE '%SOLE%SOURCE%'
    """
    sole_rows = _safe_query(sole_source_sql)
    sole_stats = sole_rows[0] if sole_rows else {"total_vendors": 0, "total_awards": 0}

    # Repeat sole source winners (vendors with 2+ sole source contracts)
    repeat_sql = """
        SELECT COUNT(*) AS repeat_winners FROM (
            SELECT vendor_name
            FROM contracts
            WHERE UPPER(procurement_type) LIKE '%SOLE%SOURCE%'
            GROUP BY vendor_name
            HAVING COUNT(*) >= 2
        ) sub
    """
    repeat_rows = _safe_query(repeat_sql)
    repeat_winners = repeat_rows[0]["repeat_winners"] if repeat_rows else 0

    # Top 5 risk clusters (by vendor count, then awards)
    top_risk_sql = """
        WITH vendor_addresses AS (
            SELECT DISTINCT
                vendor_name,
                TRIM(REGEXP_REPLACE(address_1, '\\s*EFT\\s*$', '')) AS address_clean,
                city,
                COALESCE(zip, '') AS zip,
                award_amount,
                department,
                procurement_type
            FROM contracts
            WHERE address_1 IS NOT NULL
              AND address_1 != ''
              AND LENGTH(TRIM(address_1)) > 5
        ),
        address_groups AS (
            SELECT
                address_clean,
                city,
                zip,
                COUNT(DISTINCT vendor_name) AS vendor_count,
                LIST(DISTINCT vendor_name ORDER BY vendor_name) AS vendors,
                COALESCE(SUM(award_amount), 0) AS total_awards,
                LIST(DISTINCT department ORDER BY department) AS departments,
                BOOL_OR(UPPER(procurement_type) LIKE '%SOLE%SOURCE%') AS has_sole_source
            FROM vendor_addresses
            GROUP BY address_clean, city, zip
            HAVING COUNT(DISTINCT vendor_name) >= 2
        )
        SELECT * FROM address_groups
        ORDER BY vendor_count DESC, total_awards DESC
        LIMIT 5
    """
    top_clusters_raw = _safe_query(top_risk_sql)
    top_risk_clusters = []
    for row in top_clusters_raw:
        vendors_list = row.get("vendors", [])
        departments_list = [d for d in row.get("departments", []) if d]
        risk_flags = _compute_risk_flags(vendors_list, departments_list, row.get("total_awards", 0))
        if row.get("has_sole_source"):
            risk_flags.append("Sole source contracts")

        top_risk_clusters.append({
            "address": row.get("address_clean", ""),
            "city": row.get("city", ""),
            "zip": row.get("zip", ""),
            "vendor_count": row.get("vendor_count", 0),
            "vendors": vendors_list,
            "total_awards": float(row.get("total_awards", 0)),
            "departments": departments_list,
            "risk_flags": risk_flags,
        })

    return jsonify({
        "address_clusters": {
            "total": int(cluster_stats.get("total", 0)),
            "with_3plus": int(cluster_stats.get("with_3plus", 0)),
            "total_awards": float(cluster_stats.get("total_awards", 0)),
        },
        "vendor_aliases": {
            "total_groups": int(alias_stats.get("total_groups", 0)),
            "total_awards": float(alias_stats.get("total_awards", 0)),
        },
        "sole_source_stats": {
            "total_vendors": int(sole_stats.get("total_vendors", 0)),
            "total_awards": float(sole_stats.get("total_awards", 0)),
            "repeat_winners": int(repeat_winners),
        },
        "top_risk_clusters": top_risk_clusters,
    })
