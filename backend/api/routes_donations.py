"""Political donation routes for the Chicago spending investigation API."""

from flask import Blueprint, jsonify, request
from backend.api.db import get_db

donations_bp = Blueprint("donations_bp", __name__, url_prefix="/api/donations")


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


def _table_exists(table_name):
    """Check if a table exists in the database."""
    try:
        con = get_db()
        result = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = $1",
            [table_name],
        ).fetchone()
        return result[0] > 0
    except Exception:
        return False


@donations_bp.route("/summary", methods=["GET"])
def donations_summary():
    """Overview of political donation data."""
    if not _table_exists("donations"):
        return jsonify({
            "total_donations": 0,
            "total_amount": 0,
            "vendors_with_donations": 0,
            "top_donor_vendors": [],
            "top_recipients": [],
            "message": "Donations table not available. Run build_db to fetch donation data.",
        })

    source = request.args.get("source")  # "fec", "isbe", or None for all
    source_condition = ""
    source_params = []
    if source:
        source_condition = " WHERE source = $1"
        source_params = [source]

    # Total stats
    totals = _safe_query(f"""
        SELECT
            COUNT(*) AS total_donations,
            COALESCE(SUM(amount), 0) AS total_amount,
            COUNT(DISTINCT matched_vendor) AS vendors_with_donations
        FROM donations
        {source_condition}
    """, source_params or None)
    stats = totals[0] if totals else {
        "total_donations": 0, "total_amount": 0, "vendors_with_donations": 0
    }

    # Source breakdown
    source_breakdown = _safe_query("""
        SELECT COALESCE(source, 'fec') AS source,
               COUNT(*) AS count,
               COALESCE(SUM(amount), 0) AS total
        FROM donations
        GROUP BY COALESCE(source, 'fec')
    """)

    # Top donor vendors (by donation total), joined with contract values
    source_where = f"WHERE d.source = $1" if source else ""
    top_donor_vendors = _safe_query(f"""
        SELECT
            d.matched_vendor AS vendor_name,
            SUM(d.amount) AS total_donated,
            COUNT(*) AS donation_count,
            COALESCE(c.total_contracts, 0) AS total_contracts
        FROM donations d
        LEFT JOIN (
            SELECT vendor_name, SUM(amount) AS total_contracts
            FROM payment_contract_joined
            WHERE is_annual_aggregate = false AND amount > 0
            GROUP BY vendor_name
        ) c ON d.matched_vendor = c.vendor_name
        {source_where}
        GROUP BY d.matched_vendor, c.total_contracts
        ORDER BY total_donated DESC
        LIMIT 20
    """, source_params or None)

    # Top recipient committees
    source_and = f"AND source = ${len(source_params) + 1}" if source else ""
    top_recipients = _safe_query(f"""
        SELECT
            recipient_committee AS committee,
            SUM(amount) AS total_received,
            COUNT(DISTINCT donor_name) AS donor_count
        FROM donations
        WHERE recipient_committee IS NOT NULL AND recipient_committee != ''
        {source_and}
        GROUP BY recipient_committee
        ORDER BY total_received DESC
        LIMIT 20
    """, source_params or None)

    return jsonify({
        "total_donations": stats.get("total_donations", 0),
        "total_amount": stats.get("total_amount", 0),
        "vendors_with_donations": stats.get("vendors_with_donations", 0),
        "top_donor_vendors": top_donor_vendors,
        "top_recipients": top_recipients,
        "source_breakdown": source_breakdown,
    })


@donations_bp.route("/vendor/<path:vendor_name>", methods=["GET"])
def vendor_donations(vendor_name):
    """Donation detail for a specific vendor."""
    if not _table_exists("donations"):
        return jsonify({
            "vendor_name": vendor_name,
            "contract_value": 0,
            "donations": [],
            "total_donated": 0,
            "donation_count": 0,
            "recipients": [],
            "donation_to_contract_ratio": 0,
            "employees_who_donated": [],
            "message": "Donations table not available.",
        })

    # Get contract value for this vendor
    contract_rows = _safe_query("""
        SELECT COALESCE(SUM(amount), 0) AS contract_value
        FROM payment_contract_joined
        WHERE vendor_name = $1 AND is_annual_aggregate = false AND amount > 0
    """, [vendor_name])
    contract_value = contract_rows[0]["contract_value"] if contract_rows else 0

    # Check cached donations table
    donations = _safe_query("""
        SELECT donor_name, donor_employer, donor_city, donor_state,
               amount, date, recipient_committee, recipient_id,
               election_cycle, match_type, COALESCE(source, 'fec') AS source
        FROM donations
        WHERE matched_vendor = $1
        ORDER BY amount DESC
    """, [vendor_name])

    # If no cached results, optionally do a live FEC search
    if not donations and request.args.get("live_search", "false").lower() == "true":
        try:
            import re
            from backend.external.fetch_donations import search_fec_donations
            clean = re.sub(
                r'\b(LLC|INC|CORP|LTD|CO\.|COMPANY|L\.P\.|LP|NFP)\b\.?',
                '', vendor_name, flags=re.IGNORECASE
            ).strip().rstrip(',').rstrip('.')
            clean = re.sub(r'\s+', ' ', clean).strip()
            if len(clean) >= 3:
                name_results = search_fec_donations(clean, search_type="name", max_pages=2)
                for r in name_results:
                    r["match_type"] = "company_name"
                emp_results = search_fec_donations(clean, search_type="employer", max_pages=1)
                for r in emp_results:
                    r["match_type"] = "employer"
                donations = name_results + emp_results
        except Exception:
            pass

    total_donated = sum(d.get("amount", 0) for d in donations)
    donation_count = len(donations)

    # Aggregate by recipient committee
    recipient_map = {}
    for d in donations:
        comm = d.get("recipient_committee", "Unknown")
        if comm not in recipient_map:
            recipient_map[comm] = {"committee": comm, "total": 0, "count": 0}
        recipient_map[comm]["total"] += d.get("amount", 0)
        recipient_map[comm]["count"] += 1
    recipients = sorted(recipient_map.values(), key=lambda x: x["total"], reverse=True)

    # Employees who donated (match_type == "employer")
    employee_map = {}
    for d in donations:
        if d.get("match_type") == "employer":
            name = d.get("donor_name", "Unknown")
            if name not in employee_map:
                employee_map[name] = {"name": name, "total": 0, "count": 0}
            employee_map[name]["total"] += d.get("amount", 0)
            employee_map[name]["count"] += 1
    employees = sorted(employee_map.values(), key=lambda x: x["total"], reverse=True)

    # Donation-to-contract ratio
    ratio = (total_donated / contract_value) if contract_value > 0 else 0

    return jsonify({
        "vendor_name": vendor_name,
        "contract_value": contract_value,
        "donations": donations,
        "total_donated": total_donated,
        "donation_count": donation_count,
        "recipients": recipients,
        "donation_to_contract_ratio": ratio,
        "employees_who_donated": employees,
    })


@donations_bp.route("/red-flags", methods=["GET"])
def donation_red_flags():
    """Flag suspicious donation-to-contract patterns."""
    if not _table_exists("donations"):
        return jsonify({"flags": [], "message": "Donations table not available."})

    flags = []

    # Get all vendors with donations and their contract info
    vendor_donation_stats = _safe_query("""
        SELECT
            d.matched_vendor AS vendor_name,
            SUM(d.amount) AS donation_total,
            COUNT(*) AS donation_count
        FROM donations d
        GROUP BY d.matched_vendor
        HAVING SUM(d.amount) > 0
    """)

    for vd in vendor_donation_stats:
        vendor_name = vd["vendor_name"]
        donation_total = vd["donation_total"]

        # Get contract total for this vendor
        contract_rows = _safe_query("""
            SELECT COALESCE(SUM(amount), 0) AS contract_total
            FROM payment_contract_joined
            WHERE vendor_name = $1 AND is_annual_aggregate = false AND amount > 0
        """, [vendor_name])
        contract_total = contract_rows[0]["contract_total"] if contract_rows else 0

        if contract_total <= 0:
            continue

        ratio = donation_total / contract_total

        # Flag: large_donor_sole_source
        sole_source_rows = _safe_query("""
            SELECT COUNT(*) AS sole_source_count
            FROM payment_contract_joined
            WHERE vendor_name = $1
              AND contract_type_desc ILIKE '%sole source%'
              AND is_annual_aggregate = false
        """, [vendor_name])
        sole_source_count = sole_source_rows[0]["sole_source_count"] if sole_source_rows else 0

        if sole_source_count > 0 and donation_total > 1000:
            risk_score = min(100, int(50 + (donation_total / 1000) + (sole_source_count * 5)))
            flags.append({
                "vendor_name": vendor_name,
                "flag_type": "large_donor_sole_source",
                "description": (
                    f"{vendor_name} donated ${donation_total:,.0f} to political campaigns "
                    f"and has {sole_source_count} sole source contract payments "
                    f"totaling ${contract_total:,.0f}."
                ),
                "donation_total": donation_total,
                "contract_total": contract_total,
                "risk_score": risk_score,
            })

        # Flag: high_donation_ratio (> 1%)
        if ratio > 0.01:
            risk_score = min(100, int(60 + (ratio * 1000)))
            flags.append({
                "vendor_name": vendor_name,
                "flag_type": "high_donation_ratio",
                "description": (
                    f"{vendor_name} has a donation-to-contract ratio of {ratio:.2%}. "
                    f"Donated ${donation_total:,.0f} against ${contract_total:,.0f} in contracts."
                ),
                "donation_total": donation_total,
                "contract_total": contract_total,
                "risk_score": risk_score,
            })

        # Placeholder: donation_timing (for future implementation)
        # Would check if donations occurred near contract award dates

    # Sort by risk score descending
    flags.sort(key=lambda x: x["risk_score"], reverse=True)

    return jsonify({"flags": flags})
