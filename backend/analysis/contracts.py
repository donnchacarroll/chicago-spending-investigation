"""Contract analysis for Chicago spending payments.

Detects contract overspending and high-value payments without contracts.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from backend.config import CONTRACT_OVERSPEND_THRESHOLD, NO_CONTRACT_HIGH_VALUE


def analyze_contracts(con) -> pd.DataFrame:
    """Analyze contract-related spending anomalies.

    Detects two types of flags:
    1. CONTRACT_OVERSPEND: contracts where total payments exceed the award
       amount by more than CONTRACT_OVERSPEND_THRESHOLD (10%).
    2. NO_CONTRACT_HIGH_VALUE: direct voucher payments above
       NO_CONTRACT_HIGH_VALUE without a contract.

    Args:
        con: A DuckDB connection with the payments and
             payment_contract_joined tables loaded.

    Returns:
        DataFrame of flagged items with columns:
        contract_number, vendor_name, department_name, award_amount,
        total_paid, overspend_ratio, amount, flag_type, description,
        risk_score.
    """
    # 1. Contract overspend detection
    overspend_query = f"""
    SELECT DISTINCT
        contract_number,
        vendor_name,
        department_canonical AS department_name,
        award_amount,
        total_paid_per_contract AS total_paid,
        ROUND((total_paid_per_contract - award_amount) / award_amount, 4) AS overspend_ratio,
        NULL AS amount
    FROM payment_contract_joined
    WHERE award_amount > 0
      AND total_paid_per_contract > award_amount * (1 + {CONTRACT_OVERSPEND_THRESHOLD})
    ORDER BY (total_paid_per_contract - award_amount) DESC
    """

    # 2. No-contract high-value payments
    no_contract_query = f"""
    SELECT
        NULL AS contract_number,
        vendor_name,
        department_canonical AS department_name,
        NULL AS award_amount,
        NULL AS total_paid,
        NULL AS overspend_ratio,
        amount
    FROM payments
    WHERE contract_type = 'direct_voucher'
      AND amount > {NO_CONTRACT_HIGH_VALUE}
      AND amount IS NOT NULL
    ORDER BY amount DESC
    """

    result_cols = [
        "contract_number", "vendor_name", "department_name", "award_amount",
        "total_paid", "overspend_ratio", "amount", "flag_type", "description",
        "risk_score",
    ]

    frames = []

    # Overspend results
    try:
        overspend_df = con.execute(overspend_query).fetchdf()
        if not overspend_df.empty:
            overspend_df["flag_type"] = "CONTRACT_OVERSPEND"

            # Risk score: scale overspend ratio. 10% over -> low, 100%+ over -> max
            overspend_df["risk_score"] = (
                overspend_df["overspend_ratio"].clip(0, 1.0) * 100
            ).round(1)

            overspend_df["description"] = overspend_df.apply(
                lambda r: (
                    f"Contract {r['contract_number']}: "
                    f"${r['total_paid']:,.2f} paid vs "
                    f"${r['award_amount']:,.2f} awarded "
                    f"({r['overspend_ratio'] * 100:.1f}% over) "
                    f"for {r['vendor_name']}"
                ),
                axis=1,
            )
            frames.append(overspend_df)
    except Exception:
        # payment_contract_joined table may not exist yet
        pass

    # No-contract results
    try:
        no_contract_df = con.execute(no_contract_query).fetchdf()
        if not no_contract_df.empty:
            no_contract_df["flag_type"] = "NO_CONTRACT_HIGH_VALUE"

            # Risk score: scale by amount. $25k -> 30, $500k+ -> 100
            no_contract_df["risk_score"] = (
                30 + (no_contract_df["amount"] - NO_CONTRACT_HIGH_VALUE)
                / (500_000 - NO_CONTRACT_HIGH_VALUE) * 70
            ).clip(30, 100).round(1)

            no_contract_df["description"] = no_contract_df.apply(
                lambda r: (
                    f"${r['amount']:,.2f} direct voucher to {r['vendor_name']} "
                    f"({r['department_name']}) with no contract"
                ),
                axis=1,
            )
            frames.append(no_contract_df)
    except Exception:
        # payments table may not have the expected columns
        pass

    if not frames:
        return pd.DataFrame(columns=result_cols)

    result = pd.concat(frames, ignore_index=True)
    return result[result_cols]
