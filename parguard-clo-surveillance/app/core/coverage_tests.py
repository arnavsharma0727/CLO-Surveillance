"""Simplified OC and IC coverage tests."""

from __future__ import annotations

import pandas as pd

from .collateral import safe_divide
from .constants import DEFAULT_PASS_CUSHION_PCT, DEFAULT_WATCH_LOWER_BOUND_PCT, IC_FORMULA, OC_FORMULA
from .models import CoverageTestResult


def test_status(cushion: float, pass_threshold: float = DEFAULT_PASS_CUSHION_PCT, watch_lower: float = DEFAULT_WATCH_LOWER_BOUND_PCT) -> str:
    if cushion >= pass_threshold:
        return "PASS"
    if cushion <= 0.0:
        return "FAIL"
    if cushion > watch_lower:
        return "WATCH"
    return "FAIL"


def calculate_oc_tests(adjusted_collateral_par: float, liabilities: pd.DataFrame) -> list[CoverageTestResult]:
    debt = liabilities[~liabilities["is_equity"]].sort_values("seniority_rank")
    results: list[CoverageTestResult] = []
    for _, tranche in debt.iterrows():
        denom = float(debt.loc[debt["seniority_rank"] <= tranche["seniority_rank"], "outstanding_par"].sum())
        actual = safe_divide(adjusted_collateral_par, denom)
        trigger = float(tranche["oc_trigger"])
        cushion = actual - trigger
        results.append(CoverageTestResult(tranche_name=tranche["tranche_name"], test_type="OC", actual_ratio=actual, trigger=trigger, cushion=cushion, cushion_bps=cushion * 10_000, status=test_status(cushion), numerator=adjusted_collateral_par, denominator=denom, formula=OC_FORMULA))
    return results


def calculate_ic_tests(annual_portfolio_interest_income: float, liabilities: pd.DataFrame) -> list[CoverageTestResult]:
    debt = liabilities[~liabilities["is_equity"]].sort_values("seniority_rank")
    debt = debt.assign(annual_interest_due=debt["outstanding_par"] * debt["annual_coupon_rate"])
    results: list[CoverageTestResult] = []
    for _, tranche in debt.iterrows():
        denom = float(debt.loc[debt["seniority_rank"] <= tranche["seniority_rank"], "annual_interest_due"].sum())
        actual = safe_divide(annual_portfolio_interest_income, denom)
        trigger = float(tranche["ic_trigger"])
        cushion = actual - trigger
        results.append(CoverageTestResult(tranche_name=tranche["tranche_name"], test_type="IC", actual_ratio=actual, trigger=trigger, cushion=cushion, cushion_bps=cushion * 10_000, status=test_status(cushion), numerator=annual_portfolio_interest_income, denominator=denom, formula=IC_FORMULA))
    return results
