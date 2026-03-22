"""Spending category analysis for Chicago payments."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


CATEGORY_MAP = {
    'DELEGATE AGENCY': 'Social Services & Grants',
    'Delegate Agency': 'Social Services & Grants',
    'DPS DELEGATE AGENCY': 'Social Services & Grants',
    'CONSTRUCTION-LARGE $3MILLIONorABOVE': 'Construction',
    'CONSTRUCTION-GENERAL': 'Construction',
    'CONSTRUCTION-AVIATION': 'Construction',
    'CONSTRUCTION': 'Construction',
    'Construction': 'Construction',
    'CONSTRUCTION SERVICES': 'Construction',
    'CONSTRUCTION-LARGE $5MILLIONorABOVE': 'Construction',
    'DEMOLITION': 'Construction',
    'DEMOLITION-SMALL ORDERS': 'Construction',
    'Demolition': 'Construction',
    'ROOFING': 'Construction',
    'JOC': 'Construction',
    'ARCH/ENGINEERING': 'Architecture & Engineering',
    'ARCH/ENGINEERING-AVIATION': 'Architecture & Engineering',
    'COMMODITIES': 'Commodities & Supplies',
    'COMMODITIES-SMALL ORDERS': 'Commodities & Supplies',
    'COMMODITIES-AVIATION': 'Commodities & Supplies',
    'VEHICLES/HEAVY EQUIPMENT (CAPITAL)': 'Commodities & Supplies',
    'HARDWARE': 'Technology',
    'SOFTWARE': 'Technology',
    'PRO SERV-SOFTWARE/HARDWARE': 'Technology',
    'TELECOMMUNICATIONS': 'Technology',
    'PRO SERV CONSULTING $250,000orABOVE': 'Professional Services',
    'PRO SERV CONSULTING UNDER $250,000': 'Professional Services',
    'PRO SERV-AVIATION': 'Professional Services',
    'PRO SERV-SMALL ORDERS': 'Professional Services',
    'PRO SERV': 'Professional Services',
    'PRO SERV-BUSINESS CONSULTING': 'Professional Services',
    'Professional Services': 'Professional Services',
    'WORK SERVICES / FACILITIES MAINT.': 'Facilities & Maintenance',
    'WORK SERVICES-SMALL ORDERS': 'Facilities & Maintenance',
    'WORK SERV-AVIATION': 'Facilities & Maintenance',
    'HIRED TRUCK': 'Facilities & Maintenance',
    'PROPERTY LEASE': 'Property & Leasing',
    'COMPTROLLER-OTHER': 'Other/Administrative',
    'UTILITIES-ELECTRICITY': 'Utilities',
    'REVENUE': 'Revenue',
    'CONVERTED': 'Other/Administrative',
    'Modification': 'Contract Modification',
    'Time Extension': 'Contract Modification',
    'Term Agreement': 'Contract Modification',
    'One Shot': 'Other/Administrative',
    'ONE SHOT': 'Other/Administrative',
    'EXHIBIT-A': 'Other/Administrative',
    'EXHIBIT-B': 'Other/Administrative',
    'RELEASE REQUISITION': 'Other/Administrative',
    'Add Line Item': 'Contract Modification',
    'Emergency': 'Emergency',
    'Service Contract': 'Professional Services',
    'CM': 'Construction',
    'Other': 'Other/Administrative',
}


# Subcategorize direct voucher vendors by name patterns
DV_VENDOR_RULES = [
    ("Pensions & Retirement", [
        "%PENSION%", "%ANNUIT%", "%RETIREMENT%", "%BENEFIT FUND%",
    ]),
    ("Debt Service & Banking", [
        "%BANK%", "%AMALGAMATED%", "%ZIONS%", "%TRUST CO%",
    ]),
    ("Government Transfers", [
        "COOK COUNTY%", "STATE OF%", "%TRANSIT%", "DEPARTMENT OF%",
        "%TREASURER%", "%COLLECTOR%", "CITY OF%",
    ]),
    ("Legal Settlements & Fees", [
        "%LAW%", "%ATTORNEY%", "%LEGAL%", "%LOEVY%",
    ]),
    ("Insurance & Risk", [
        "%INSURANCE%", "%CLAIMS%", "%SEDGWICK%", "%RISK%",
    ]),
    ("Utilities", [
        "%COMED%", "%COMMONWEALTH EDISON%", "%PEOPLES GAS%",
        "%NICOR%", "%WATER%RECLAMATION%",
    ]),
    ("Payroll & Benefits", [
        "%PATROLMEN%", "%FIREMANS ASSN%", "%NATIONWIDE RETIREMENT%",
        "%DEFERRED COMP%", "%UNION%", "%CREDIT UNION%",
    ]),
]


def classify_dv_vendor(vendor_name: str) -> str:
    """Classify a direct voucher vendor into a subcategory."""
    upper = vendor_name.upper()
    for category, patterns in DV_VENDOR_RULES:
        for pat in patterns:
            pat_clean = pat.replace("%", "")
            if pat.startswith("%") and pat.endswith("%"):
                if pat_clean in upper:
                    return category
            elif pat.startswith("%"):
                if upper.endswith(pat_clean):
                    return category
            elif pat.endswith("%"):
                if upper.startswith(pat_clean):
                    return category
            else:
                if upper == pat_clean:
                    return category
    # Check if it looks like a person's name (LAST, FIRST pattern)
    if ", " in vendor_name and not any(
        kw in upper for kw in ["LLC", "INC", "CORP", "LTD", "CO.", "COMPANY", "SERVICES", "GROUP"]
    ):
        return "Individual Payments"
    return "Other Direct Voucher"


def analyze_categories(con) -> dict:
    """Analyze spending by category, procurement type, and contract type.

    Args:
        con: A DuckDB connection with the payment_contract_joined table.

    Returns:
        dict with keys: by_category, by_procurement, by_contract_type,
        no_contract_spending.
    """
    # By spending_category (pre-computed in build_db)
    by_category_rows = con.execute("""
        SELECT
            COALESCE(spending_category, 'Uncategorized / Direct Voucher') AS category,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count,
            COUNT(DISTINCT vendor_name) AS vendor_count,
            AVG(amount) AS avg_payment
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false
        GROUP BY category
        ORDER BY total_spending DESC
    """).fetchall()

    by_category = [
        {
            "category": row[0],
            "total_spending": float(row[1]) if row[1] else 0,
            "payment_count": int(row[2]),
            "vendor_count": int(row[3]),
            "avg_payment": float(row[4]) if row[4] else 0,
        }
        for row in by_category_rows
    ]

    # By procurement type
    by_procurement_rows = con.execute("""
        SELECT
            COALESCE(procurement_type, 'Unknown') AS procurement_type,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count,
            COUNT(DISTINCT vendor_name) AS vendor_count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false
        GROUP BY procurement_type
        ORDER BY total_spending DESC
    """).fetchall()

    by_procurement = [
        {
            "procurement_type": row[0],
            "total_spending": float(row[1]) if row[1] else 0,
            "payment_count": int(row[2]),
            "vendor_count": int(row[3]),
        }
        for row in by_procurement_rows
    ]

    # By contract type (top 30)
    by_contract_type_rows = con.execute("""
        SELECT
            COALESCE(contract_type_desc, 'N/A') AS contract_type,
            COALESCE(spending_category, 'Uncategorized / Direct Voucher') AS category,
            SUM(amount) AS total_spending,
            COUNT(*) AS payment_count
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false
        GROUP BY contract_type, category
        ORDER BY total_spending DESC
        LIMIT 30
    """).fetchall()

    by_contract_type = [
        {
            "contract_type": row[0],
            "category": row[1],
            "total_spending": float(row[2]) if row[2] else 0,
            "payment_count": int(row[3]),
        }
        for row in by_contract_type_rows
    ]

    # No-contract spending (direct vouchers)
    no_contract_rows = con.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM payment_contract_joined
        WHERE is_annual_aggregate = false
          AND contract_type = 'direct_voucher'
    """).fetchone()

    no_contract_spending = float(no_contract_rows[0]) if no_contract_rows else 0

    return {
        "by_category": by_category,
        "by_procurement": by_procurement,
        "by_contract_type": by_contract_type,
        "no_contract_spending": no_contract_spending,
    }
