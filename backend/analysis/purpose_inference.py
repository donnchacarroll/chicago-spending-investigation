"""Infer likely payment purpose from vendor name, amount, and context.

This module provides SPECULATIVE purpose classifications based on pattern
matching. These inferences are NOT definitive — they are educated guesses
to help investigators prioritize where to look.
"""

import re

# Pattern rules: (purpose, confidence, patterns, amount_hint)
# confidence: "high" = strong signal, "medium" = reasonable guess, "low" = weak signal
VENDOR_RULES = [
    # Legal
    ("Legal Settlement / Lawsuit Payment",
     [r"\bLAW\b", r"\bATTORNEY", r"\bLEGAL\b", r"\bLOEVY\b", r"\bLITIGAT"],
     "high",
     "Payments to law firms are typically for legal representation or lawsuit settlements. "
     "Chicago pays hundreds of millions annually in police misconduct and other settlements."),

    ("Court / Legal Proceeding",
     [r"\bCLERK.*COURT\b", r"\bJUDGE\b", r"\bU\.?S\.?\s*DISTRICT"],
     "high",
     "Payments to courts are typically for settlement disbursements, filing fees, or judgments."),

    # Financial
    ("Pension Fund Contribution",
     [r"\bPENSION\b", r"\bANNUIT", r"\bRETIREMENT\b", r"\bBENEFIT FUND\b"],
     "high",
     "Mandatory employer contributions to municipal pension funds. "
     "Chicago has significant pension obligations across police, fire, and municipal employee funds."),

    ("Debt Service / Bond Payment",
     [r"\bBANK\b", r"\bTRUST\b", r"\bAMALGAMATED\b", r"\bZIONS\b", r"\bWELLS FARGO\b"],
     "medium",
     "Payments to banks likely relate to debt service on municipal bonds, "
     "interest payments, or financial transactions. Could also be banking fees."),

    ("Deferred Compensation / Payroll",
     [r"\bNATIONWIDE RETIREMENT\b", r"\bDEFERRED COMP\b", r"\bPATROLMEN.*FCU\b",
      r"\bFIREMAN.*ASSN\b", r"\bCREDIT UNION\b"],
     "high",
     "Employee deferred compensation plans or payroll-related transfers to union credit unions."),

    # Government
    ("Intergovernmental Transfer",
     [r"^COOK COUNTY", r"^STATE OF", r"\bTREASURER\b", r"\bCOLLECTOR\b",
      r"^CITY OF\b", r"\bMETROPOLITAN WATER\b"],
     "high",
     "Transfers between government entities — tax remittances, shared service payments, "
     "or intergovernmental agreements."),

    ("Transit Authority Payment",
     [r"\bTRANSIT\b", r"\bCTA\b", r"\bMETRA\b", r"\bPACE\b"],
     "high",
     "Payments to transit agencies, likely for city contributions to public transportation operations."),

    # Insurance
    ("Insurance Premium / Claims",
     [r"\bINSURANCE\b", r"\bCLAIMS\b", r"\bSEDGWICK\b", r"\bRISK MGMT\b",
      r"\bBLUE CROSS\b", r"\bBLUE SHIELD\b"],
     "high",
     "Insurance premiums, self-insurance claims payments, or third-party claims administration."),

    # Utilities
    ("Utility Payment",
     [r"\bEDISON\b", r"\bCOMED\b", r"\bPEOPLES GAS\b", r"\bNICOR\b",
      r"\bCOMMONWEALTH.*EDISON\b", r"\bELECTRIC\b"],
     "high",
     "Payments for electricity, gas, or other utility services for city facilities."),

    # Property
    ("Real Estate / Title",
     [r"\bTITLE\b(?!.*INSURANCE)", r"\bREALTY\b", r"\bREAL ESTATE\b",
      r"\bPROPERTY\b.*\bMGMT\b", r"\bLEASE\b"],
     "medium",
     "May relate to property transactions, title services, lease payments, or real estate closings."),

    # Services
    ("Medical / Healthcare",
     [r"\bHOSPITAL\b", r"\bMEDICAL CENTER\b", r"\bHEALTH CENTER\b",
      r"\bCLINIC\b", r"\bPHYSICIAN\b"],
     "medium",
     "Payments to healthcare providers, possibly for employee health programs, "
     "inmate medical care, or public health services."),

    ("Consulting / Professional Services",
     [r"\bCONSULTING\b", r"\bCONSULTANT\b", r"\bADVISOR\b"],
     "medium",
     "Professional consulting services. Without a contract, it's unclear "
     "what scope of work was performed."),

    ("Towing / Vehicle Services",
     [r"\bTOWING\b", r"\bTOW\b.*\bSERVICE\b", r"\bAUTO POUND\b"],
     "high",
     "Towing services, likely from the city's towing program or impound operations."),

    ("Parking / Traffic",
     [r"\bPARKING\b", r"\bMETER\b"],
     "medium",
     "Parking-related payments — could be meter revenue sharing, "
     "parking enforcement, or the Chicago Parking Meters LLC concession."),

    ("Construction / Building",
     [r"\bCONSTRUCTION\b", r"\bPAVING\b", r"\bCEMENT\b",
      r"\bPLUMBING\b", r"\bROOFING\b", r"\bDEMOLITION\b"],
     "medium",
     "Construction or building-related work. The absence of a contract "
     "for construction payments is unusual and may warrant review."),

    ("Technology / Telecom",
     [r"\bVERIZON\b", r"\bAT&T\b", r"\bCOMCAST\b", r"\bT-MOBILE\b",
      r"\bMICROSOFT\b", r"\bORACLE\b", r"\bCISCO\b"],
     "high",
     "Telecommunications or technology service payments."),
]

# Amount-based heuristics for individual payments
AMOUNT_HINTS = [
    (0, 100, "Likely a permit fee refund, overpayment reimbursement, or small claim."),
    (100, 500, "Possibly a deposit refund, citation overpayment, or minor reimbursement."),
    (500, 5000, "Could be a damage claim, tax refund, or small settlement payment."),
    (5000, 25000, "May be a property damage claim, small legal settlement, or employee payout."),
    (25000, 100000, "Significant payment — possibly a legal settlement, property claim, or severance."),
    (100000, float("inf"), "Large payment to an individual — likely a substantial legal settlement or judgment."),
]


def infer_purpose(vendor_name: str, amount: float, contract_type: str = "",
                  dv_subcategory: str = "", spending_category: str = "") -> dict:
    """Infer the likely purpose of a payment.

    Returns a dict with:
        - purpose: str — the inferred purpose
        - confidence: str — "high", "medium", "low"
        - reasoning: str — explanation of why this was inferred
        - disclaimer: str — standard caveat
        - amount_context: str — what the amount range suggests (for individuals)
    """
    result = {
        "purpose": None,
        "confidence": "low",
        "reasoning": "",
        "disclaimer": (
            "This is a speculative classification based on the vendor name and "
            "payment characteristics. It is not a definitive determination of "
            "what this payment was for. Actual purpose may differ."
        ),
        "amount_context": None,
    }

    # If we already have contract info, use that
    if spending_category and spending_category not in ("Uncategorized / Direct Voucher", "Other/Administrative"):
        result["purpose"] = spending_category
        result["confidence"] = "high"
        result["reasoning"] = f"Classified from contract type: {spending_category}"
        return result

    # If we have a DV subcategory, use that as a starting point
    if dv_subcategory and dv_subcategory != "Other Direct Voucher":
        result["purpose"] = dv_subcategory
        result["confidence"] = "medium"
        result["reasoning"] = f"Classified from vendor name pattern: {dv_subcategory}"

    # Try vendor name pattern matching for more specific purpose
    upper_name = vendor_name.upper() if vendor_name else ""
    for purpose, patterns, confidence, explanation in VENDOR_RULES:
        for pattern in patterns:
            if re.search(pattern, upper_name):
                result["purpose"] = purpose
                result["confidence"] = confidence
                result["reasoning"] = explanation
                break
        if result["purpose"] and result["confidence"] != "low":
            break

    # Amount-based hints for individual payments
    # Detect individuals: has comma (LAST, FIRST), or short name with spaces + no corp keywords
    is_individual = dv_subcategory == "Individual Payments"
    if not is_individual and vendor_name:
        has_corp = any(kw in upper_name for kw in [
            "LLC", "INC", "CORP", "LTD", "CO.", "COMPANY", "SERVICES",
            "GROUP", "FUND", "BANK", "ASSOC", "OFFICE", "DEPT",
        ])
        if not has_corp and ("," in vendor_name or (
            len(vendor_name.split()) <= 4 and re.match(r"^[A-Z][a-z]|^[A-Z]+ [A-Z]", vendor_name)
        )):
            is_individual = True
    if is_individual:
        for low, high, hint in AMOUNT_HINTS:
            if low <= amount < high:
                result["amount_context"] = hint
                break
        if not result["purpose"]:
            if amount < 500:
                result["purpose"] = "Probable Refund / Reimbursement"
                result["confidence"] = "medium"
                result["reasoning"] = (
                    "Small payment to an individual — most commonly a permit refund, "
                    "overpayment reimbursement, or minor claim settlement."
                )
            elif amount < 25000:
                result["purpose"] = "Possible Claim / Settlement"
                result["confidence"] = "low"
                result["reasoning"] = (
                    "Payment to an individual in this range could be a damage claim, "
                    "tax refund, small settlement, or employee-related payout."
                )
            else:
                result["purpose"] = "Probable Legal Settlement"
                result["confidence"] = "medium"
                result["reasoning"] = (
                    "Large payment to an individual is frequently a legal settlement or "
                    "court judgment. Chicago pays significant sums annually in settlements."
                )

    # Fallback
    if not result["purpose"]:
        result["purpose"] = "Unknown — Requires Investigation"
        result["confidence"] = "low"
        result["reasoning"] = (
            "No contract on file and vendor name doesn't match known patterns. "
            "This payment's purpose cannot be determined from available data alone."
        )

    return result
