from app.core.data_loader import load_collateral_pool, load_deal_terms
from app.core.quality_tests import collateral_quality_metrics, parguard_diversification_index


def test_quality_metrics_are_par_weighted_and_complete():
    loans = load_collateral_pool()
    terms = load_deal_terms()
    metrics = collateral_quality_metrics(loans, terms.ccc_concentration_limit)
    assert metrics["total_par"] > 318_000_000
    assert metrics["was_bps"] > 400
    assert 0 < metrics["ccc_pct"] < terms.ccc_concentration_limit
    assert metrics["watchlist_count"] > 0
    assert metrics["defaulted_count"] == 0
    assert parguard_diversification_index(loans) > 50
