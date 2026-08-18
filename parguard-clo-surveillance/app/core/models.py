"""Pydantic schemas for collateral, liabilities, deal terms, and test outputs."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Loan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loan_id: str
    obligor_name: str
    industry: str
    country: str
    seniority: Literal["First Lien", "Second Lien"]
    rating: str
    rating_factor: float = Field(ge=0)
    par_balance: float = Field(ge=0)
    market_price: float = Field(ge=0)
    spread_bps: float
    benchmark_rate: float = Field(ge=0)
    coupon_rate: float = Field(ge=0)
    maturity_date: date
    remaining_life_years: float = Field(ge=0)
    recovery_rate: float = Field(ge=0, le=1)
    default_status: bool
    ccc_flag: bool
    watchlist_flag: bool
    collateral_haircut_pct: float = Field(ge=0, le=1)
    annual_interest_income: float = Field(ge=0)

    @model_validator(mode="after")
    def defaulted_loans_do_not_accrue_interest(self) -> "Loan":
        if self.default_status and self.annual_interest_income != 0:
            raise ValueError("defaulted loans must have zero annual_interest_income in the base configuration")
        return self


class LiabilityTranche(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tranche_name: str
    seniority_rank: int = Field(ge=1)
    outstanding_par: float = Field(ge=0)
    annual_coupon_rate: float = Field(ge=0)
    oc_trigger: float | None = Field(default=None, ge=0)
    ic_trigger: float | None = Field(default=None, ge=0)
    is_equity: bool = False

    @model_validator(mode="after")
    def debt_has_triggers(self) -> "LiabilityTranche":
        if not self.is_equity and (self.oc_trigger is None or self.ic_trigger is None):
            raise ValueError("debt tranches require OC and IC triggers")
        return self


class DealTerms(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deal_name: str
    as_of_date: date
    reinvestment_status: str
    ccc_concentration_limit: float = Field(default=0.075, ge=0, le=1)
    ccc_excess_haircut_description: str
    defaulted_interest_zero: bool = True
    administrative_expenses: float = Field(default=1_500_000.0, ge=0)
    disclaimer: str


class CoverageTestResult(BaseModel):
    tranche_name: str
    test_type: Literal["OC", "IC"]
    actual_ratio: float
    trigger: float
    cushion: float
    cushion_bps: float
    status: Literal["PASS", "WATCH", "FAIL"]
    numerator: float
    denominator: float
    formula: str
