"""Deterministic collateral calculations for the simplified ParGuard CLO model."""

from __future__ import annotations

import pandas as pd

from .constants import DEFAULT_CCC_LIMIT_PCT


def safe_divide(numerator: float, denominator: float) -> float:
    """Return zero for zero denominators; otherwise return numerator / denominator."""
    return 0.0 if denominator == 0 else numerator / denominator


def add_loan_calculations(loans: pd.DataFrame) -> pd.DataFrame:
    """Add market value, loan-level adjusted par, and validated interest income.

    Defaulted loans receive recovery-based adjusted par and zero interest income.
    Non-defaulted loans receive par less explicit collateral haircut.
    """
    df = loans.copy()
    df["market_value"] = df["par_balance"] * df["market_price"] / 100.0
    non_default_adjusted = df["par_balance"] * (1.0 - df["collateral_haircut_pct"])
    default_adjusted = df["par_balance"] * df["recovery_rate"]
    df["loan_adjusted_par"] = non_default_adjusted.where(~df["default_status"], default_adjusted)
    df.loc[df["default_status"], "annual_interest_income"] = 0.0
    return df


def ccc_excess_adjustment(
    loans: pd.DataFrame,
    ccc_limit_pct: float = DEFAULT_CCC_LIMIT_PCT,
) -> dict[str, float]:
    """Calculate the educational excess-CCC haircut adjustment.

    Excess CCC par above the configured limit is valued at the lower of market
    value or 50% of par, applied proportionally across CCC names. The adjustment
    equals par value of the excess less the simplified value assigned to it.
    This is an educational simplification, not indenture-specific treatment.
    """
    df = add_loan_calculations(loans)
    total_par = float(df["par_balance"].sum())
    ccc_df = df[df["ccc_flag"]]
    ccc_par = float(ccc_df["par_balance"].sum())
    limit_par = total_par * ccc_limit_pct
    excess_par = max(ccc_par - limit_par, 0.0)
    if excess_par == 0 or ccc_par == 0:
        return {"total_par": total_par, "ccc_par": ccc_par, "limit_par": limit_par, "excess_par": 0.0, "excess_value": 0.0, "haircut_amount": 0.0}

    market_value = float(ccc_df["market_value"].sum())
    simplified_value = min(market_value, 0.5 * ccc_par)
    excess_value = excess_par * safe_divide(simplified_value, ccc_par)
    haircut_amount = excess_par - excess_value
    return {"total_par": total_par, "ccc_par": ccc_par, "limit_par": limit_par, "excess_par": excess_par, "excess_value": excess_value, "haircut_amount": haircut_amount}


def total_adjusted_par(loans: pd.DataFrame, ccc_limit_pct: float = DEFAULT_CCC_LIMIT_PCT) -> float:
    """Total adjusted par after loan-level and excess-CCC educational haircuts."""
    df = add_loan_calculations(loans)
    gross_adjusted = float(df["loan_adjusted_par"].sum())
    return gross_adjusted - ccc_excess_adjustment(df, ccc_limit_pct)["haircut_amount"]
