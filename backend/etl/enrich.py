"""Enrich payments with contract data."""

import pandas as pd


def enrich_payments(payments_df, contracts_df):
    """
    Join payments with contracts and compute overspend metrics.

    Joins on payments contract_number (numeric contracts only) to contracts
    purchase_order_contract_number. Adds contract columns and computes
    total_paid_per_contract and overspend_ratio.

    Args:
        payments_df: Cleaned payments DataFrame (from ingest.py).
        contracts_df: Contracts DataFrame (from fetch_contracts.py).

    Returns:
        pd.DataFrame: Enriched payments with contract info and overspend metrics.
    """
    print("Enriching payments with contract data ...")

    # Work on a copy
    payments = payments_df.copy()
    contracts = contracts_df.copy()

    # Filter to only payments that have a numeric contract
    has_contract = payments["contract_type"] == "contract"
    print(f"  Payments with contract type 'contract': {has_contract.sum():,}")

    # Normalize the join keys to string for matching
    payments["_join_key"] = payments["contract_number"].astype(str).str.strip()
    # Only keep the join key for contract-type rows; null out others
    payments.loc[~has_contract, "_join_key"] = None

    # Prepare contracts join key
    if "purchase_order_contract_number" in contracts.columns:
        contracts["_join_key"] = (
            contracts["purchase_order_contract_number"]
            .astype(str)
            .str.strip()
        )
    else:
        print("  WARNING: 'purchase_order_contract_number' not found in contracts. Skipping join.")
        payments.drop(columns=["_join_key"], inplace=True)
        return payments

    # Select contract columns to bring over
    contract_cols = ["_join_key"]
    for col in ["award_amount", "start_date", "end_date", "procurement_type",
                 "purchase_order_description", "contract_type", "revision_number"]:
        if col in contracts.columns:
            contract_cols.append(col)

    # Rename for clarity after join
    contracts_for_join = contracts[contract_cols].copy()
    rename_map = {}
    if "start_date" in contracts_for_join.columns:
        rename_map["start_date"] = "contract_start"
    if "end_date" in contracts_for_join.columns:
        rename_map["end_date"] = "contract_end"
    if "contract_type" in contracts_for_join.columns:
        rename_map["contract_type"] = "contract_type_desc"
    contracts_for_join = contracts_for_join.rename(columns=rename_map)

    # Deduplicate contracts: keep the latest revision (highest revision_number) per contract
    # This gives us the most current award amount and dates
    if "revision_number" in contracts.columns:
        contracts_for_join["_rev_num"] = pd.to_numeric(
            contracts_for_join.get("revision_number", 0), errors="coerce"
        ).fillna(0)
        contracts_for_join = (
            contracts_for_join
            .sort_values("_rev_num", ascending=False)
            .drop_duplicates(subset=["_join_key"], keep="first")
            .drop(columns=["_rev_num"])
        )
    else:
        contracts_for_join = contracts_for_join.drop_duplicates(subset=["_join_key"], keep="first")
    # Drop revision_number — not needed in final output
    if "revision_number" in contracts_for_join.columns:
        contracts_for_join = contracts_for_join.drop(columns=["revision_number"])

    # Left join
    enriched = payments.merge(
        contracts_for_join,
        on="_join_key",
        how="left",
        suffixes=("", "_contract"),
    )

    # Compute total_paid_per_contract
    contract_totals = (
        enriched[enriched["contract_type"] == "contract"]
        .groupby("_join_key")["amount"]
        .sum()
        .reset_index()
        .rename(columns={"AMOUNT": "total_paid_per_contract"})
    )

    enriched = enriched.merge(contract_totals, on="_join_key", how="left")

    # Compute overspend_ratio = total_paid / award_amount
    if "award_amount" in enriched.columns:
        enriched["overspend_ratio"] = enriched.apply(
            lambda row: (
                row["total_paid_per_contract"] / row["award_amount"]
                if pd.notna(row.get("award_amount"))
                and row.get("award_amount", 0) > 0
                and pd.notna(row.get("total_paid_per_contract"))
                else None
            ),
            axis=1,
        )
    else:
        enriched["overspend_ratio"] = None

    # Clean up temp column
    enriched.drop(columns=["_join_key"], inplace=True)

    print(f"  Enriched DataFrame: {len(enriched):,} rows, {len(enriched.columns)} columns")
    return enriched
