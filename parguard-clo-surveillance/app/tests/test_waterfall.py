from app.core.data_loader import load_collateral_pool, load_liability_stack, load_deal_terms
from app.core.quality_tests import collateral_quality_metrics
from app.core.scenarios import run_preset_scenario
from app.core.waterfall import run_annual_waterfall


def _base():
    loans, liabilities, terms = load_collateral_pool(), load_liability_stack(), load_deal_terms()
    metrics = collateral_quality_metrics(loans, terms.ccc_concentration_limit)
    return liabilities, terms, metrics


def test_base_case_distributes_positive_residual_to_equity():
    liabilities, terms, metrics = _base()
    out = run_annual_waterfall(metrics["annual_interest_income"], metrics["total_adjusted_par"], liabilities, terms.administrative_expenses)
    assert out["equity_cash_flow_after_diversion"] > 0
    assert out["cash_diverted_to_debt_paydown"] == 0


def test_failed_test_diverts_equity_cash_to_debt_paydown():
    loans, liabilities, terms = load_collateral_pool(), load_liability_stack(), load_deal_terms()
    scenario = run_preset_scenario("severe_default_recovery_shock", loans, liabilities, terms.ccc_concentration_limit)
    metrics = scenario["scenario_kpi_snapshot"]["metrics"]
    out = run_annual_waterfall(metrics["annual_interest_income"], metrics["total_adjusted_par"], liabilities, terms.administrative_expenses)
    assert out["cash_diverted_to_debt_paydown"] > 0
    assert out["equity_cash_flow_after_diversion"] < out["equity_cash_flow_before_diversion"]
    assert out["trigger_that_caused_diversion"] is not None


def test_debt_paydown_cannot_exceed_outstanding_or_residual_cash():
    liabilities, terms, metrics = _base()
    out = run_annual_waterfall(100_000_000, 100_000_000, liabilities, terms.administrative_expenses)
    assert out["cash_diverted_to_debt_paydown"] <= out["equity_cash_flow_before_diversion"]
    for name, paid in out["debt_paydown_by_class"].items():
        assert paid <= out["debt_balance_before"][name]


def test_paydown_does_not_worsen_relevant_oc_ratio():
    liabilities, terms, metrics = _base()
    out = run_annual_waterfall(100_000_000, 100_000_000, liabilities, terms.administrative_expenses)
    trigger = out["trigger_that_caused_diversion"]
    if trigger and trigger["test_type"] == "OC":
        pre = next(t for t in out["pre_diversion_coverage_tests"]["oc_tests"] if t["tranche_name"] == trigger["tranche_name"])
        post = next(t for t in out["post_diversion_coverage_tests"]["oc_tests"] if t["tranche_name"] == trigger["tranche_name"])
        assert post["actual_ratio"] >= pre["actual_ratio"]


def test_admin_and_debt_interest_are_paid_in_order_and_reconcile():
    liabilities, terms, metrics = _base()
    out = run_annual_waterfall(metrics["annual_interest_income"], metrics["total_adjusted_par"], liabilities, terms.administrative_expenses)
    assert out["administrative_expenses_paid"] == terms.administrative_expenses
    assert all(v == 0 for v in out["unpaid_interest"].values())
    assert abs(out["cash_reconciliation"]["difference"]) < 0.01


def test_insufficient_interest_reports_unpaid_interest_and_reconciles():
    liabilities, terms, metrics = _base()
    out = run_annual_waterfall(1_000_000, metrics["total_adjusted_par"], liabilities, terms.administrative_expenses)
    assert out["administrative_expenses_paid"] == 1_000_000
    assert sum(out["unpaid_interest"].values()) > 0
    assert abs(out["cash_reconciliation"]["difference"]) < 0.01
