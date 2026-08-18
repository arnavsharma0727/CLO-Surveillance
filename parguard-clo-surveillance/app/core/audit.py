"""Model audit, attribution, and deterministic analyst summary helpers."""
from __future__ import annotations
from typing import Any
import pandas as pd
from .collateral import add_loan_calculations, ccc_excess_adjustment, safe_divide
from .coverage_tests import calculate_ic_tests, calculate_oc_tests
from .quality_tests import collateral_quality_metrics
from .waterfall import run_annual_waterfall

TOLERANCE = 0.01
QUALITY_THRESHOLDS = {"warf": 550.0, "was_bps": 425.0, "warr": 0.60, "wal_years": 6.25, "ccc_pct": 0.075, "parguard_diversification_index": 50.0, "top_obligor_concentration": 0.025, "top_industry_concentration": 0.12}
FORMULAS = {"warf":"Sum(par * rating factor) / total par", "was_bps":"Sum(par * spread bps) / total par", "warr":"Sum(par * recovery rate) / total par", "wal_years":"Sum(par * remaining life) / total par", "ccc_pct":"CCC par / total par", "parguard_diversification_index":"0.50 * effective issuer count + 0.25 * issuer count + 0.25 * effective industry count", "top_obligor_concentration":"Largest obligor par / total par", "top_industry_concentration":"Largest industry par / total par"}

def validation_flag(name: str, difference: float, tolerance: float=TOLERANCE)->dict[str,Any]:
    return {"check": name, "difference": difference, "tolerance": tolerance, "status": "PASS" if abs(difference) <= tolerance else "FAIL"}

def adjusted_collateral_bridge(loans: pd.DataFrame, ccc_limit: float)->list[dict[str,Any]]:
    df=add_loan_calculations(loans); ccc=ccc_excess_adjustment(df, ccc_limit)
    total=float(df.par_balance.sum()); default_loss=float((df.loc[df.default_status,"par_balance"]*(1-df.loc[df.default_status,"recovery_rate"])).sum())
    non_default_haircut=float((df.loc[~df.default_status,"par_balance"]*df.loc[~df.default_status,"collateral_haircut_pct"]).sum())
    return [{"component":"Total collateral par","amount":total},{"component":"Default / recovery losses","amount":-default_loss},{"component":"Scenario collateral haircuts","amount":-non_default_haircut},{"component":"Excess CCC treatment","amount":-ccc["haircut_amount"]},{"component":"Adjusted collateral par","amount":total-default_loss-non_default_haircut-ccc["haircut_amount"]}]

def interest_income_bridge(loans: pd.DataFrame)->list[dict[str,Any]]:
    df=add_loan_calculations(loans); performing=df[~df.default_status]
    return [{"component":"Performing par x coupon rate","amount":float((performing.par_balance*performing.coupon_rate).sum())},{"component":"Defaulted-loan income","amount":0.0},{"component":"Annual portfolio interest income","amount":float(df.annual_interest_income.sum())}]

def attribution_bridges(base_loans: pd.DataFrame, scenario_loans: pd.DataFrame, ccc_limit: float)->dict[str,Any]:
    base=add_loan_calculations(base_loans); scen=add_loan_calculations(scenario_loans)
    b=base.set_index("loan_id"); s=scen.set_index("loan_id")
    defaults=float(((s.par_balance*(1-s.recovery_rate)).where(s.default_status,0)- (b.par_balance*(1-b.recovery_rate)).where(b.default_status,0)).sum())*-1
    haircuts=float(((s.par_balance*s.collateral_haircut_pct).where(~s.default_status,0)- (b.par_balance*b.collateral_haircut_pct).where(~b.default_status,0)).sum())*-1
    ccc_delta=-(ccc_excess_adjustment(scen,ccc_limit)["haircut_amount"]-ccc_excess_adjustment(base,ccc_limit)["haircut_amount"])
    base_adj=collateral_quality_metrics(base,ccc_limit)["total_adjusted_par"]; scen_adj=collateral_quality_metrics(scen,ccc_limit)["total_adjusted_par"]
    other=(scen_adj-base_adj)-(defaults+haircuts+ccc_delta)
    default_income=float((s.loc[s.default_status,"par_balance"]*b.loc[s.default_status,"coupon_rate"]).sum())*-1 if len(s) else 0.0
    rate_spread=float(s.annual_interest_income.sum()-b.annual_interest_income.sum()-default_income)
    return {"oc_attribution":[{"component":"Defaults / recovery losses","amount":defaults},{"component":"CCC excess-treatment effect","amount":ccc_delta},{"component":"Scenario haircuts","amount":haircuts},{"component":"Price / discount-treatment effect","amount":0.0},{"component":"Other configured adjustments","amount":other}],"ic_attribution":[{"component":"Defaulted-loan income loss","amount":default_income},{"component":"Rate / benchmark and spread changes","amount":rate_spread},{"component":"Other configured adjustments","amount":0.0}],"oc_total_change":scen_adj-base_adj,"ic_total_change":float(s.annual_interest_income.sum()-b.annual_interest_income.sum())}

def quality_test_dashboard(loans: pd.DataFrame, ccc_limit: float=0.075, thresholds: dict[str,float]|None=None, base_loans: pd.DataFrame|None=None)->list[dict[str,Any]]:
    th={**QUALITY_THRESHOLDS, **(thresholds or {}), "ccc_pct": ccc_limit}; m=collateral_quality_metrics(loans, ccc_limit); bm=collateral_quality_metrics(base_loans, ccc_limit) if base_loans is not None else m
    rows=[]
    for key, limit in th.items():
        val=m["top_10_obligor_concentration" if key=="top_obligor_concentration" else key]; lower_good=key in {"was_bps","warr","parguard_diversification_index"}
        cushion=(val-limit) if lower_good else (limit-val); status="PASS" if cushion>=0 else ("WATCH" if cushion >= -0.01*max(abs(limit),1) else "FAIL")
        rows.append({"metric":key,"current_value":val,"threshold":limit,"cushion":cushion,"status":status,"base_case_change":val-bm.get("top_10_obligor_concentration" if key=="top_obligor_concentration" else key, val),"formula":FORMULAS[key]})
    return rows

def concentration_tables(loans: pd.DataFrame)->dict[str,pd.DataFrame]:
    df=add_loan_calculations(loans); total=float(df.par_balance.sum())
    return {"industry_rating": pd.pivot_table(df,index="industry",columns="rating",values="par_balance",aggfunc="sum",fill_value=0), "top_obligors": df.groupby("obligor_name",as_index=False).par_balance.sum().assign(exposure_pct=lambda x:x.par_balance/total).sort_values("par_balance",ascending=False).head(10), "watch_default": pd.pivot_table(df,index="watchlist_flag",columns="default_status",values="par_balance",aggfunc="sum",fill_value=0), "price_bucket": df.assign(price_bucket=pd.cut(df.market_price,[0,70,80,90,95,100,200])).groupby("price_bucket",observed=False).par_balance.sum().reset_index(), "life_bucket": df.assign(life_bucket=pd.cut(df.remaining_life_years,[0,3,5,7,30])).groupby("life_bucket",observed=False).par_balance.sum().reset_index()}

def model_audit(loans: pd.DataFrame, liabilities: pd.DataFrame, terms: Any, scenario_run: dict[str,Any]|None=None)->dict[str,Any]:
    ccc=float(terms.ccc_concentration_limit); metrics=collateral_quality_metrics(loans,ccc); wf=run_annual_waterfall(metrics["annual_interest_income"],metrics["total_adjusted_par"],liabilities,float(terms.administrative_expenses))
    flags=[validation_flag("Waterfall interest cash reconciliation", wf["cash_reconciliation"]["difference"]), validation_flag("Adjusted collateral bridge", adjusted_collateral_bridge(loans,ccc)[-1]["amount"]-metrics["total_adjusted_par"]), validation_flag("Interest-income bridge", interest_income_bridge(loans)[-1]["amount"]-metrics["annual_interest_income"])]
    return {"total_collateral_par":metrics["total_par"],"adjusted_collateral_bridge":adjusted_collateral_bridge(loans,ccc),"interest_income_bridge":interest_income_bridge(loans),"oc_checks":[r.model_dump() for r in calculate_oc_tests(metrics["total_adjusted_par"],liabilities)],"ic_checks":[r.model_dump() for r in calculate_ic_tests(metrics["annual_interest_income"],liabilities)],"waterfall_reconciliation":wf["cash_reconciliation"],"scenario_change_reconciliation":scenario_run or {},"validation_flags":flags}

def analyst_morning_brief(loans: pd.DataFrame, liabilities: pd.DataFrame, terms: Any, scenario_name: str="Base Case")->dict[str,Any]:
    metrics=collateral_quality_metrics(loans,terms.ccc_concentration_limit); tests=[r.model_dump() for r in calculate_oc_tests(metrics["total_adjusted_par"],liabilities)+calculate_ic_tests(metrics["annual_interest_income"],liabilities)]
    closest=min(tests,key=lambda x:x["cushion_bps"]); status="Test Breach" if any(t["status"]=="FAIL" for t in tests) else ("Watch" if any(t["status"]=="WATCH" for t in tests) or metrics["ccc_pct"]>terms.ccc_concentration_limit*0.9 else ("Deteriorating" if scenario_name!="Base Case" else "Stable"))
    top=loans.groupby("obligor_name").par_balance.sum().sort_values(ascending=False)
    return {"overall_risk_status":status,"status_explanation":f"{closest['test_type']} {closest['tranche_name']} is the closest coverage test with {closest['cushion_bps']:.0f} bps of cushion.","closest_coverage_test":closest,"largest_adjusted_par_loss_contributor":loans.sort_values("par_balance",ascending=False).iloc[0]["obligor_name"] if len(loans) else "N/A","largest_single_obligor_concentration":safe_divide(float(top.iloc[0]),float(loans.par_balance.sum())) if len(top) else 0,"ccc_exposure_vs_threshold":metrics["ccc_pct"]-terms.ccc_concentration_limit,"next_action_item":"Review the largest watchlist/default contributors and rerun the waterfall under the selected stress."}
