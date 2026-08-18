"""Transparent simplified annual cash-flow waterfall for ParGuard CLO Surveillance."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from .coverage_tests import calculate_ic_tests, calculate_oc_tests

WATERFALL_LIMITATIONS = [
    "Annual simplified cash-flow waterfall.",
    "Not a legal interpretation of a CLO indenture.",
    "Does not model every indenture feature, reinvestment criterion, trading restriction, tax item, manager fee, hedge, or payment-date convention.",
    "Models test-driven diversion conceptually and transparently.",
]


def _dump(results):
    return [r.model_dump() for r in results]


def run_annual_waterfall(annual_portfolio_interest_income: float, adjusted_collateral_par: float, liabilities: pd.DataFrame, administrative_expenses: float = 1_500_000.0, principal_proceeds: float = 0.0) -> dict[str, Any]:
    """Run a deterministic annual waterfall and reconcile all interest cash."""
    if annual_portfolio_interest_income < 0 or adjusted_collateral_par < 0 or administrative_expenses < 0 or principal_proceeds < 0:
        raise ValueError("waterfall monetary inputs must be non-negative")
    debt = liabilities[~liabilities["is_equity"]].sort_values("seniority_rank").copy()
    before = debt[["tranche_name", "outstanding_par"]].set_index("tranche_name")["outstanding_par"].to_dict()
    cash = float(annual_portfolio_interest_income)
    admin_paid = min(cash, float(administrative_expenses)); cash -= admin_paid
    interest_paid, unpaid_interest = {}, {}
    for _, t in debt.iterrows():
        due = float(t["outstanding_par"] * t["annual_coupon_rate"])
        paid = min(cash, due); cash -= paid
        interest_paid[t["tranche_name"]] = paid; unpaid_interest[t["tranche_name"]] = due - paid
    equity_before = cash
    pre_oc = calculate_oc_tests(adjusted_collateral_par, debt)
    pre_ic = calculate_ic_tests(annual_portfolio_interest_income, debt)
    failed = [r for r in pre_oc + pre_ic if r.status == "FAIL"]
    diversion = 0.0; trigger = None; paydown_by_class = {name: 0.0 for name in before}; explanation = "All coverage tests pass; residual interest is distributed to equity in the simplified model."
    if failed and cash > 0:
        failed.sort(key=lambda r: (next(int(x["seniority_rank"]) for _, x in debt.iterrows() if x["tranche_name"] == r.tranche_name), 0 if r.test_type == "OC" else 1))
        trigger = failed[0].model_dump(); target = trigger["tranche_name"]
        outstanding = float(debt.loc[debt["tranche_name"] == target, "outstanding_par"].iloc[0])
        diversion = min(cash, outstanding); cash -= diversion; paydown_by_class[target] = diversion
        debt.loc[debt["tranche_name"] == target, "outstanding_par"] = outstanding - diversion
        explanation = f"{trigger['test_type']} breach for {target} caused ${diversion:,.0f} of residual interest to be diverted from equity to debt paydown."
    post_oc = calculate_oc_tests(adjusted_collateral_par, debt)
    post_ic = calculate_ic_tests(annual_portfolio_interest_income, debt)
    after = debt[["tranche_name", "outstanding_par"]].set_index("tranche_name")["outstanding_par"].to_dict()
    allocated = admin_paid + sum(interest_paid.values()) + diversion + cash
    return {"interest_income_before_expenses": annual_portfolio_interest_income, "principal_proceeds": principal_proceeds, "administrative_expenses_due": administrative_expenses, "administrative_expenses_paid": admin_paid, "interest_paid": interest_paid, "unpaid_interest": unpaid_interest, "cash_diverted_to_debt_paydown": diversion, "debt_paydown_by_class": paydown_by_class, "debt_balance_before": before, "debt_balance_after": after, "equity_cash_flow_before_diversion": equity_before, "equity_cash_flow_after_diversion": cash, "pre_diversion_coverage_tests": {"oc_tests": _dump(pre_oc), "ic_tests": _dump(pre_ic)}, "post_diversion_coverage_tests": {"oc_tests": _dump(post_oc), "ic_tests": _dump(post_ic)}, "trigger_that_caused_diversion": trigger, "cash_reconciliation": {"available_interest": annual_portfolio_interest_income, "allocated_interest": allocated, "difference": annual_portfolio_interest_income - allocated}, "assumptions_limitations": deepcopy(WATERFALL_LIMITATIONS), "explanation": explanation}
