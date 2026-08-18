"""Collateral-quality metrics for ParGuard CLO Surveillance."""

from __future__ import annotations

import pandas as pd

from .collateral import add_loan_calculations, safe_divide, total_adjusted_par


def parguard_diversification_index(loans: pd.DataFrame) -> float:
    """Illustrative diversification index combining issuer and industry breadth.

    Formula: 0.50 * effective issuer count by HHI + 0.25 * issuer count +
    0.25 * effective industry count by HHI. This is proprietary to ParGuard's
    educational sample and is not a rating-agency diversity score.
    """
    total_par = float(loans["par_balance"].sum())
    if total_par == 0:
        return 0.0
    issuer_weights = loans.groupby("obligor_name")["par_balance"].sum() / total_par
    industry_weights = loans.groupby("industry")["par_balance"].sum() / total_par
    effective_issuers = safe_divide(1.0, float((issuer_weights**2).sum()))
    effective_industries = safe_divide(1.0, float((industry_weights**2).sum()))
    issuer_count = float(loans["obligor_name"].nunique())
    return 0.50 * effective_issuers + 0.25 * issuer_count + 0.25 * effective_industries


def collateral_quality_metrics(loans: pd.DataFrame, ccc_limit_pct: float = 0.075) -> dict[str, float]:
    df = add_loan_calculations(loans)
    total_par = float(df["par_balance"].sum())
    defaulted = df[df["default_status"]]
    industry_par = df.groupby("industry")["par_balance"].sum()
    obligor_par = df.groupby("obligor_name")["par_balance"].sum().sort_values(ascending=False)
    return {
        "total_par": total_par,
        "total_market_value": float(df["market_value"].sum()),
        "total_adjusted_par": total_adjusted_par(df, ccc_limit_pct),
        "was_bps": safe_divide(float((df["par_balance"] * df["spread_bps"]).sum()), total_par),
        "wal_years": safe_divide(float((df["par_balance"] * df["remaining_life_years"]).sum()), total_par),
        "warf": safe_divide(float((df["par_balance"] * df["rating_factor"]).sum()), total_par),
        "warr": safe_divide(float((df["par_balance"] * df["recovery_rate"]).sum()), total_par),
        "ccc_pct": safe_divide(float(df.loc[df["ccc_flag"], "par_balance"].sum()), total_par),
        "top_10_obligor_concentration": safe_divide(float(obligor_par.head(10).sum()), total_par),
        "top_industry_concentration": safe_divide(float(industry_par.max()), total_par),
        "watchlist_count": float(df["watchlist_flag"].sum()),
        "defaulted_count": float(defaulted.shape[0]),
        "defaulted_par": float(defaulted["par_balance"].sum()),
        "parguard_diversification_index": parguard_diversification_index(df),
        "annual_interest_income": float(df["annual_interest_income"].sum()),
    }
