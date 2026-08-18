import pytest

from app.core.data_loader import load_collateral_pool, load_liability_stack, load_deal_terms
from app.core.scenarios import CustomScenarioParameters, run_custom_scenario, run_preset_scenario


def _inputs():
    return load_collateral_pool(), load_liability_stack(), load_deal_terms()


def test_ccc_migration_reduces_adjusted_collateral_and_worsens_oc():
    loans, liabilities, terms = _inputs()
    result = run_preset_scenario("ccc_migration_shock", loans, liabilities, terms.ccc_concentration_limit)
    assert result["change_in_adjusted_collateral"] < 0
    oc_changes = [v for k, v in result["change_in_oc_ic_ratios"].items() if k.startswith("OC")]
    assert min(oc_changes) < 0
    assert result["scenario_kpi_snapshot"]["metrics"]["ccc_pct"] > terms.ccc_concentration_limit
    assert len(result["impacted_loans"]) > 0


def test_severe_default_causes_coverage_breach():
    loans, liabilities, terms = _inputs()
    result = run_preset_scenario("severe_default_recovery_shock", loans, liabilities, terms.ccc_concentration_limit)
    statuses = [t["status"] for t in result["scenario_kpi_snapshot"]["oc_tests"] + result["scenario_kpi_snapshot"]["ic_tests"]]
    assert "FAIL" in statuses
    defaulted = [loan for loan in result["scenario_loans"] if loan["default_status"]]
    assert 3 <= len(defaulted) <= 5
    assert all(loan["annual_interest_income"] == 0 for loan in defaulted)


def test_healthcare_shock_only_changes_healthcare_loans():
    loans, liabilities, terms = _inputs()
    result = run_preset_scenario("healthcare_sector_shock", loans, liabilities, terms.ccc_concentration_limit)
    assert result["impacted_loans"]
    assert {loan["industry"] for loan in result["impacted_loans"]} == {"Healthcare"}


def test_custom_scenario_validates_bad_recovery_and_rating():
    with pytest.raises(ValueError):
        CustomScenarioParameters(recovery_rate_overrides={"PG26-001": 1.2})
    with pytest.raises(ValueError):
        CustomScenarioParameters(loan_rating_migrations={"PG26-001": "AAA"})


def test_custom_scenario_applies_loan_and_industry_controls():
    loans, liabilities, terms = _inputs()
    result = run_custom_scenario(loans, liabilities, {"loans_to_default": ["PG26-001"], "industry_price_shocks": {"Technology": -5}, "ccc_limit_override": 0.05}, terms.ccc_concentration_limit)
    assert any(ch["loan_id"] == "PG26-001" for ch in result["impacted_loans"])
    assert result["scenario_id"] == "custom"
