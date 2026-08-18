from app.core.coverage_tests import calculate_ic_tests, calculate_oc_tests
from app.core.data_loader import load_collateral_pool, load_deal_terms, load_liability_stack
from app.core.quality_tests import collateral_quality_metrics


def test_base_case_passes_all_oc_and_ic_tests():
    loans = load_collateral_pool()
    liabilities = load_liability_stack()
    terms = load_deal_terms()
    metrics = collateral_quality_metrics(loans, terms.ccc_concentration_limit)
    results = calculate_oc_tests(metrics["total_adjusted_par"], liabilities) + calculate_ic_tests(metrics["annual_interest_income"], liabilities)
    assert all(result.status == "PASS" for result in results)


def test_every_test_result_is_traceable():
    loans = load_collateral_pool()
    liabilities = load_liability_stack()
    terms = load_deal_terms()
    metrics = collateral_quality_metrics(loans, terms.ccc_concentration_limit)
    results = calculate_oc_tests(metrics["total_adjusted_par"], liabilities) + calculate_ic_tests(metrics["annual_interest_income"], liabilities)
    for result in results:
        assert result.numerator > 0
        assert result.denominator > 0
        assert result.trigger > 0
        assert "/" in result.formula
        assert result.cushion_bps == result.cushion * 10_000
