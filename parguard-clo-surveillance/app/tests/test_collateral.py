from app.core.collateral import add_loan_calculations, ccc_excess_adjustment, total_adjusted_par
from app.core.data_loader import load_collateral_pool, load_deal_terms


def test_market_value_and_adjusted_par_do_not_exceed_total_par_normal_conditions():
    loans = load_collateral_pool()
    terms = load_deal_terms()
    calculated = add_loan_calculations(loans)
    assert (calculated["market_value"] == calculated["par_balance"] * calculated["market_price"] / 100).all()
    assert total_adjusted_par(loans, terms.ccc_concentration_limit) <= loans["par_balance"].sum()


def test_base_case_ccc_bucket_is_meaningful_but_non_breaching():
    loans = load_collateral_pool()
    terms = load_deal_terms()
    ccc = ccc_excess_adjustment(loans, terms.ccc_concentration_limit)
    assert ccc["ccc_par"] > 0
    assert ccc["excess_par"] == 0
