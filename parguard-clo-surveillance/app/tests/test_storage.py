from app.core.data_loader import load_collateral_pool, load_liability_stack, load_deal_terms
from app.core.scenarios import run_preset_scenario
from app.core.storage import compare_scenario_runs, delete_scenario_run, get_scenario_run, list_scenario_runs, save_scenario_run


def test_scenario_runs_can_be_saved_listed_loaded_compared_and_deleted(tmp_path):
    db = tmp_path / "runs.sqlite3"
    loans, liabilities, terms = load_collateral_pool(), load_liability_stack(), load_deal_terms()
    base = run_preset_scenario("base_case", loans, liabilities, terms.ccc_concentration_limit)
    ccc = run_preset_scenario("ccc_migration_shock", loans, liabilities, terms.ccc_concentration_limit)
    base_id = save_scenario_run(base, {"deal_name": terms.deal_name}, db_path=db)
    ccc_id = save_scenario_run(ccc, {"deal_name": terms.deal_name}, db_path=db)
    assert len(list_scenario_runs(db)) == 2
    loaded = get_scenario_run(ccc_id, db)
    assert loaded["scenario_name"] == "CCC Migration Shock"
    assert loaded["loan_level_changes"]
    comparison = compare_scenario_runs(base_id, ccc_id, db)
    assert comparison["run_a"]["run_id"] == base_id
    assert comparison["run_b"]["run_id"] == ccc_id
    assert delete_scenario_run(base_id, db) is True
    assert get_scenario_run(base_id, db) is None
