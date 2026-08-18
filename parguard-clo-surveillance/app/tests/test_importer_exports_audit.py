import json
import pandas as pd
from app.core.audit import attribution_bridges, model_audit, quality_test_dashboard
from app.core.data_loader import load_collateral_pool, load_deal_terms, load_liability_stack
from app.core.exports import coverage_tests_csv, scenario_json, surveillance_memo_markdown, waterfall_csv, scenario_comparison_csv
from app.core.importer import validate_collateral_csv, validate_liability_csv, error_report_csv
from app.core.scenarios import run_preset_scenario
from app.core.waterfall import run_annual_waterfall


def test_csv_import_valid_case():
    loans=load_collateral_pool().head(2).drop(columns=["rating_factor","annual_interest_income"])
    liab=load_liability_stack().head(1).rename(columns={"outstanding_par":"outstanding_balance"}).drop(columns=["is_equity"])
    assert validate_collateral_csv(loans)["valid"] is True
    assert validate_liability_csv(liab)["valid"] is True


def test_csv_import_invalid_schema_duplicate_rating_recovery():
    loans=load_collateral_pool().head(2).drop(columns=["rating_factor","annual_interest_income"])
    bad=loans.drop(columns=["loan_id"])
    assert validate_collateral_csv(bad)["valid"] is False
    loans.loc[1,"loan_id"]=loans.loc[0,"loan_id"]; loans.loc[0,"rating"]="AAA"; loans.loc[0,"recovery_rate"]=1.5
    res=validate_collateral_csv(loans)
    assert res["valid"] is False
    assert "duplicate loan_id" in error_report_csv(res["errors"])


def test_quality_dashboard_and_audit_flags():
    loans, liabilities, terms=load_collateral_pool(), load_liability_stack(), load_deal_terms()
    assert quality_test_dashboard(loans, terms.ccc_concentration_limit)
    audit=model_audit(loans, liabilities, terms)
    assert all(f["status"]=="PASS" for f in audit["validation_flags"])


def test_attribution_bridge_reconciliation():
    loans, liabilities, terms=load_collateral_pool(), load_liability_stack(), load_deal_terms()
    scen=run_preset_scenario("severe_default_recovery_shock", loans, liabilities, terms.ccc_concentration_limit)
    attr=attribution_bridges(loans, pd.DataFrame(scen["scenario_loans"]), terms.ccc_concentration_limit)
    assert abs(sum(x["amount"] for x in attr["oc_attribution"])-attr["oc_total_change"]) < 0.01
    assert abs(sum(x["amount"] for x in attr["ic_attribution"])-attr["ic_total_change"]) < 0.01


def test_export_generation_contains_metadata():
    loans, liabilities, terms=load_collateral_pool(), load_liability_stack(), load_deal_terms()
    run=run_preset_scenario("base_case", loans, liabilities, terms.ccc_concentration_limit)
    metrics=run["scenario_kpi_snapshot"]["metrics"]
    wf=run_annual_waterfall(metrics["annual_interest_income"], metrics["total_adjusted_par"], liabilities, terms.administrative_expenses)
    brief={"overall_risk_status":"Stable","status_explanation":"Base case passes.","next_action_item":"Monitor watchlist."}
    assert "disclaimer" in coverage_tests_csv(run, terms.deal_name, terms.as_of_date)
    assert "reconciliation_difference" in waterfall_csv(wf, terms.deal_name, terms.as_of_date, run["scenario_name"])
    assert "Scenario Comparison" in scenario_comparison_csv([run], terms.deal_name, terms.as_of_date)
    assert "ParGuard Surveillance Memo" in surveillance_memo_markdown(terms.deal_name, terms.as_of_date, run["scenario_name"], run, wf, brief)
    assert json.loads(scenario_json(run, terms.deal_name, terms.as_of_date))["metadata"]["deal_name"] == terms.deal_name


def test_null_empty_state_handling():
    empty=pd.DataFrame(columns=load_collateral_pool().columns)
    liab=load_liability_stack().head(1)
    terms=load_deal_terms()
    dashboard=quality_test_dashboard(empty, terms.ccc_concentration_limit)
    assert dashboard
    wf=run_annual_waterfall(0,0,liab,0)
    assert wf["cash_reconciliation"]["difference"] == 0
