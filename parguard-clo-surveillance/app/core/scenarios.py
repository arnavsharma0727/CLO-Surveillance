"""Deterministic scenario engine for ParGuard CLO Surveillance.

All scenarios are illustrative educational stresses. They are not trustee-report
logic, rating-agency methodology, investment advice, or legal interpretation.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .collateral import add_loan_calculations
from .constants import CCC_RATINGS, DEFAULT_CCC_LIMIT_PCT, RATING_ORDER
from .coverage_tests import calculate_ic_tests, calculate_oc_tests
from .quality_tests import collateral_quality_metrics


RATING_FACTOR_MAP = {"BB": 100, "BB-": 150, "B+": 250, "B": 350, "B-": 500, "CCC+": 900, "CCC": 1200, "CCC-": 1800, "CC": 3000, "C": 5000, "D": 10000}


class CustomScenarioParameters(BaseModel):
    """Validated custom scenario controls exposed to the UI in later phases."""

    model_config = ConfigDict(extra="forbid")

    loans_to_default: list[str] = Field(default_factory=list)
    loan_rating_migrations: dict[str, str] = Field(default_factory=dict)
    loan_price_shocks: dict[str, float] = Field(default_factory=dict, description="Price-point changes, e.g. -10.")
    industry_price_shocks: dict[str, float] = Field(default_factory=dict)
    industry_rating_downgrades: dict[str, int] = Field(default_factory=dict, description="Positive notch count.")
    recovery_rate_overrides: dict[str, float] = Field(default_factory=dict)
    haircut_overrides: dict[str, float] = Field(default_factory=dict)
    benchmark_rate_change: float = 0.0
    portfolio_spread_adjustment_bps: float = 0.0
    ccc_limit_override: float | None = Field(default=None, ge=0, le=1)
    ccc_excess_haircut_policy_override: str | None = None
    administrative_expense_override: float | None = Field(default=None, ge=0)
    note_paydown_assumptions: dict[str, float] = Field(default_factory=dict)

    @field_validator("loan_rating_migrations")
    @classmethod
    def ratings_are_supported(cls, value: dict[str, str]) -> dict[str, str]:
        invalid = sorted(set(value.values()) - set(RATING_ORDER))
        if invalid:
            raise ValueError(f"invalid target ratings: {invalid}")
        return value

    @field_validator("industry_rating_downgrades")
    @classmethod
    def downgrade_counts_are_positive(cls, value: dict[str, int]) -> dict[str, int]:
        if any(count < 0 for count in value.values()):
            raise ValueError("industry rating downgrade counts must be non-negative")
        return value

    @field_validator("recovery_rate_overrides")
    @classmethod
    def recoveries_are_percentages(cls, value: dict[str, float]) -> dict[str, float]:
        if any(rate < 0 or rate > 1 for rate in value.values()):
            raise ValueError("recovery rates must be between 0% and 100%")
        return value

    @field_validator("haircut_overrides")
    @classmethod
    def haircuts_are_percentages(cls, value: dict[str, float]) -> dict[str, float]:
        if any(rate < 0 or rate > 1 for rate in value.values()):
            raise ValueError("haircuts must be between 0% and 100%")
        return value

    @field_validator("note_paydown_assumptions")
    @classmethod
    def paydowns_are_non_negative(cls, value: dict[str, float]) -> dict[str, float]:
        if any(amount < 0 for amount in value.values()):
            raise ValueError("note paydowns must be non-negative")
        return value

    @model_validator(mode="after")
    def defaulted_loans_are_not_given_performing_rating(self) -> "CustomScenarioParameters":
        overlap = set(self.loans_to_default) & {loan_id for loan_id, rating in self.loan_rating_migrations.items() if rating != "D"}
        if overlap:
            raise ValueError(f"a defaulted loan cannot also be migrated to a performing rating: {sorted(overlap)}")
        return self


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _downgrade(rating: str, notches: int = 1) -> str:
    idx = RATING_ORDER.index(rating) if rating in RATING_ORDER else RATING_ORDER.index("B")
    return RATING_ORDER[min(idx + notches, len(RATING_ORDER) - 1)]


def _set_rating(df: pd.DataFrame, idx: Any, rating: str) -> None:
    df.at[idx, "rating"] = rating
    df.at[idx, "rating_factor"] = RATING_FACTOR_MAP[rating]
    df.at[idx, "ccc_flag"] = rating in CCC_RATINGS
    if rating == "D":
        df.at[idx, "default_status"] = True
        df.at[idx, "annual_interest_income"] = 0.0


def _recalc_income(df: pd.DataFrame) -> None:
    performing = ~df["default_status"]
    df.loc[performing, "coupon_rate"] = (df.loc[performing, "benchmark_rate"] + df.loc[performing, "spread_bps"] / 10_000).clip(lower=0)
    df.loc[performing, "annual_interest_income"] = df.loc[performing, "par_balance"] * df.loc[performing, "coupon_rate"]
    df.loc[~performing, "annual_interest_income"] = 0.0


def _changes(base: pd.DataFrame, scenario: pd.DataFrame) -> list[dict[str, Any]]:
    fields = ["rating", "rating_factor", "market_price", "recovery_rate", "default_status", "ccc_flag", "watchlist_flag", "collateral_haircut_pct", "annual_interest_income"]
    out = []
    keyed = base.set_index("loan_id")
    scen = scenario.set_index("loan_id")
    for loan_id in scen.index:
        before_after = {}
        for field in fields:
            b, a = keyed.at[loan_id, field], scen.at[loan_id, field]
            if b != a:
                before_after[field] = {"before": b, "after": a}
        if before_after:
            row = scen.loc[loan_id]
            out.append({"loan_id": loan_id, "obligor_name": row["obligor_name"], "industry": row["industry"], "changes": before_after})
    return out


def _snapshot(loans: pd.DataFrame, liabilities: pd.DataFrame, ccc_limit: float) -> dict[str, Any]:
    metrics = collateral_quality_metrics(loans, ccc_limit)
    oc = calculate_oc_tests(metrics["total_adjusted_par"], liabilities)
    ic = calculate_ic_tests(metrics["annual_interest_income"], liabilities)
    return {"metrics": metrics, "oc_tests": [r.model_dump() for r in oc], "ic_tests": [r.model_dump() for r in ic]}


def _run(scenario_id: str, name: str, base_loans: pd.DataFrame, liabilities: pd.DataFrame, parameters: dict[str, Any], assumptions: list[str], mutator, ccc_limit: float = DEFAULT_CCC_LIMIT_PCT) -> dict[str, Any]:
    base = deepcopy(base_loans)
    scenario = deepcopy(base_loans)
    base_snapshot = _snapshot(base, liabilities, ccc_limit)
    mutator(scenario)
    _recalc_income(scenario)
    scenario = add_loan_calculations(scenario)
    scenario_snapshot = _snapshot(scenario, liabilities, ccc_limit)
    ratio_changes = {}
    for test_type in ("oc_tests", "ic_tests"):
        for b, s in zip(base_snapshot[test_type], scenario_snapshot[test_type]):
            ratio_changes[f"{s['test_type']} {s['tranche_name']}"] = s["actual_ratio"] - b["actual_ratio"]
    tests_changed = [s for test_type in ("oc_tests", "ic_tests") for b, s in zip(base_snapshot[test_type], scenario_snapshot[test_type]) if b["status"] == "PASS" and s["status"] in {"WATCH", "FAIL"}]
    return {"scenario_id": scenario_id, "scenario_name": name, "timestamp": _timestamp(), "parameters": parameters, "impacted_loans": _changes(base, scenario), "base_case_kpi_snapshot": base_snapshot, "scenario_kpi_snapshot": scenario_snapshot, "change_in_adjusted_collateral": scenario_snapshot["metrics"]["total_adjusted_par"] - base_snapshot["metrics"]["total_adjusted_par"], "change_in_portfolio_interest_income": scenario_snapshot["metrics"]["annual_interest_income"] - base_snapshot["metrics"]["annual_interest_income"], "change_in_oc_ic_ratios": ratio_changes, "tests_changed_from_pass": tests_changed, "assumptions_limitations": assumptions, "scenario_loans": scenario.to_dict("records")}


def run_preset_scenario(scenario_id: str, base_loans: pd.DataFrame, liabilities: pd.DataFrame, ccc_limit: float = DEFAULT_CCC_LIMIT_PCT, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    params = parameters or {}
    if scenario_id == "base_case":
        return _run("base_case", "Base Case", base_loans, liabilities, params, ["No stress applied; calculations reflect synthetic illustrative inputs."], lambda df: None, ccc_limit)
    if scenario_id == "moderate_credit_deterioration":
        def m(df):
            pick = df[(df["rating"].isin(["B", "B-"])) | (df["watchlist_flag"])].sort_values(["watchlist_flag", "market_price", "par_balance"], ascending=[False, True, False]).head(12)
            for n, idx in enumerate(pick.index):
                _set_rating(df, idx, _downgrade(df.at[idx, "rating"], 2 if n % 3 == 0 else 1)); df.at[idx, "market_price"] = max(df.at[idx, "market_price"] - (10 if n % 2 == 0 else 5), 0); df.at[idx, "collateral_haircut_pct"] = min(float(df.at[idx, "collateral_haircut_pct"]) + 0.08, 1); df.at[idx, "watchlist_flag"] = True
        return _run(scenario_id, "Moderate Credit Deterioration", base_loans, liabilities, params, ["Stresses weaker B-rated and existing watchlist names using deterministic ranking."], m, ccc_limit)
    if scenario_id == "healthcare_sector_shock":
        def m(df):
            for n, idx in enumerate(df[df["industry"] == "Healthcare"].index):
                _set_rating(df, idx, _downgrade(df.at[idx, "rating"], 2)); df.at[idx, "market_price"] = max(df.at[idx, "market_price"] - (25 if n % 2 == 0 else 15), 0); df.at[idx, "collateral_haircut_pct"] = min(float(df.at[idx, "collateral_haircut_pct"]) + 0.15, 1); df.at[idx, "recovery_rate"] = max(float(df.at[idx, "recovery_rate"]) - 0.15, 0); df.at[idx, "watchlist_flag"] = True
        return _run(scenario_id, "Healthcare Sector Shock", base_loans, liabilities, params, ["Hypothetical sector-specific stress applied only to healthcare loans."], m, ccc_limit)
    if scenario_id == "ccc_migration_shock":
        def m(df):
            current = float(df.loc[df["ccc_flag"], "par_balance"].sum()); target = float(df["par_balance"].sum()) * (params.get("target_ccc_pct", 0.12)); candidates = df[df["rating"].isin(["B", "B-", "CCC+"])].sort_values(["rating", "market_price"])
            for idx, row in candidates.iterrows():
                if current > target: break
                _set_rating(df, idx, "CCC"); df.at[idx, "market_price"] = max(df.at[idx, "market_price"] - 12, 0); df.at[idx, "collateral_haircut_pct"] = min(float(df.at[idx, "collateral_haircut_pct"]) + 0.10, 1); current += float(row["par_balance"])
        return _run(scenario_id, "CCC Migration Shock", base_loans, liabilities, params, ["Migrates deterministic weaker B/CCC+ subset until CCC par exceeds the limit and excess-CCC treatment applies."], m, ccc_limit)
    if scenario_id == "severe_default_recovery_shock":
        def m(df):
            pick = df[(df["rating"].isin(["B-", "CCC+", "CCC"])) | (df["watchlist_flag"])].sort_values(["par_balance", "market_price"], ascending=[False, True]).head(5)
            rec = [0.35, 0.40, 0.45, 0.50, 0.35]
            for n, idx in enumerate(pick.index):
                _set_rating(df, idx, "D"); df.at[idx, "recovery_rate"] = rec[n]; df.at[idx, "market_price"] = rec[n] * 100; df.at[idx, "collateral_haircut_pct"] = 1.0; df.at[idx, "watchlist_flag"] = True
            weak = df[(~df.index.isin(pick.index)) & (df["rating"].isin(["B-", "CCC+", "CCC"]))].sort_values("market_price").head(35)
            for idx in weak.index: df.at[idx, "market_price"] = max(df.at[idx, "market_price"] - 25, 0); df.at[idx, "collateral_haircut_pct"] = min(float(df.at[idx, "collateral_haircut_pct"]) + 0.35, 1)
        return _run(scenario_id, "Severe Default and Recovery Shock", base_loans, liabilities, params, ["Defaults five large/weak loans with disclosed 35%-50% recoveries and applies elevated haircuts to additional weak loans; no defaulted-loan interest accrues."], m, ccc_limit)
    if scenario_id == "rate_spread_compression_shock":
        def m(df):
            df["benchmark_rate"] = (df["benchmark_rate"] + params.get("benchmark_rate_change", -0.025)).clip(lower=0); df["spread_bps"] = (df["spread_bps"] + params.get("portfolio_spread_adjustment_bps", -250)).clip(lower=0)
        return _run(scenario_id, "Rate / Spread Compression Shock", base_loans, liabilities, params, ["Reduces benchmark and/or spread to pressure IC while preserving par."], m, ccc_limit)
    raise ValueError(f"unknown scenario_id: {scenario_id}")


def run_custom_scenario(base_loans: pd.DataFrame, liabilities: pd.DataFrame, parameters: CustomScenarioParameters | dict[str, Any], ccc_limit: float = DEFAULT_CCC_LIMIT_PCT) -> dict[str, Any]:
    p = parameters if isinstance(parameters, CustomScenarioParameters) else CustomScenarioParameters(**parameters)
    def m(df):
        known = set(df["loan_id"])
        referenced = set(p.loans_to_default) | set(p.loan_rating_migrations) | set(p.loan_price_shocks) | set(p.recovery_rate_overrides) | set(p.haircut_overrides)
        missing = sorted(referenced - known)
        if missing: raise ValueError(f"unknown loan_ids: {missing}")
        for industry in set(p.industry_price_shocks) | set(p.industry_rating_downgrades):
            if industry not in set(df["industry"]): raise ValueError(f"unknown industry: {industry}")
        for idx, row in df.iterrows():
            lid = row["loan_id"]
            if lid in p.loans_to_default: _set_rating(df, idx, "D")
            elif lid in p.loan_rating_migrations: _set_rating(df, idx, p.loan_rating_migrations[lid])
            if row["industry"] in p.industry_rating_downgrades and lid not in p.loans_to_default: _set_rating(df, idx, _downgrade(df.at[idx, "rating"], p.industry_rating_downgrades[row["industry"]]))
            shock = p.loan_price_shocks.get(lid, 0) + p.industry_price_shocks.get(row["industry"], 0)
            df.at[idx, "market_price"] = max(float(df.at[idx, "market_price"]) + shock, 0)
            if lid in p.recovery_rate_overrides: df.at[idx, "recovery_rate"] = p.recovery_rate_overrides[lid]
            if lid in p.haircut_overrides: df.at[idx, "collateral_haircut_pct"] = p.haircut_overrides[lid]
        df["benchmark_rate"] = (df["benchmark_rate"] + p.benchmark_rate_change).clip(lower=0); df["spread_bps"] = (df["spread_bps"] + p.portfolio_spread_adjustment_bps).clip(lower=0)
    return _run("custom", "Custom Scenario", base_loans, liabilities, p.model_dump(), ["User-configured deterministic scenario with validated inputs."], m, p.ccc_limit_override if p.ccc_limit_override is not None else ccc_limit)
