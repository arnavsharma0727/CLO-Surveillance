"""Deterministic export builders for ParGuard."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
import pandas as pd
DISCLAIMER="Synthetic / illustrative output. Not a trustee report, rating, valuation, investment recommendation, legal analysis, or production CLO indenture model."

def metadata(deal_name:str, as_of_date:Any, scenario_name:str)->dict[str,str]:
    return {"deal_name":str(deal_name),"as_of_date":str(as_of_date),"scenario_name":scenario_name,"export_timestamp":datetime.now(timezone.utc).isoformat(),"disclaimer":DISCLAIMER}

def surveillance_memo_markdown(deal_name:str, as_of_date:Any, scenario_name:str, run:dict[str,Any], waterfall:dict[str,Any], brief:dict[str,Any])->str:
    m=metadata(deal_name,as_of_date,scenario_name); metrics=run["scenario_kpi_snapshot"]["metrics"]
    lines=[f"# ParGuard Surveillance Memo — {m['deal_name']}",f"**As of:** {m['as_of_date']}  ",f"**Scenario:** {m['scenario_name']}  ",f"**Export timestamp:** {m['export_timestamp']}  ",f"**Disclaimer:** {m['disclaimer']}","","## Analyst Morning Brief",f"- Overall risk status: {brief['overall_risk_status']}",f"- Explanation: {brief['status_explanation']}",f"- Next action: {brief['next_action_item']}","","## Key Metrics",f"- Adjusted collateral par: ${metrics['total_adjusted_par']:,.0f}",f"- Annual interest income: ${metrics['annual_interest_income']:,.0f}",f"- CCC exposure: {metrics['ccc_pct']:.2%}","","## Coverage Tests"]
    for t in run["scenario_kpi_snapshot"]["oc_tests"]+run["scenario_kpi_snapshot"]["ic_tests"]:
        lines.append(f"- {t['test_type']} {t['tranche_name']}: {t['actual_ratio']:.2f} vs trigger {t['trigger']:.2f} ({t['status']}, {t['cushion_bps']:.0f} bps)")
    lines += ["","## Waterfall",f"- Interest proceeds: ${waterfall['interest_income_before_expenses']:,.0f}",f"- Admin paid: ${waterfall['administrative_expenses_paid']:,.0f}",f"- Debt paydown diversion: ${waterfall['cash_diverted_to_debt_paydown']:,.0f}",f"- Equity distribution after diversion: ${waterfall['equity_cash_flow_after_diversion']:,.0f}"]
    return "\n".join(lines)

def surveillance_memo_html(*args, **kwargs)->str:
    md=surveillance_memo_markdown(*args, **kwargs)
    return "<html><body>"+"".join(f"<p>{line}</p>" for line in md.splitlines())+"</body></html>"

def dataframe_csv(df:pd.DataFrame, deal_name:str, as_of_date:Any, scenario_name:str)->str:
    meta=metadata(deal_name,as_of_date,scenario_name)
    return "# "+json.dumps(meta)+"\n"+df.to_csv(index=False)

def coverage_tests_csv(run:dict[str,Any], deal_name:str, as_of_date:Any)->str:
    rows=run["scenario_kpi_snapshot"]["oc_tests"]+run["scenario_kpi_snapshot"]["ic_tests"]
    return dataframe_csv(pd.DataFrame(rows),deal_name,as_of_date,run["scenario_name"])

def waterfall_csv(waterfall:dict[str,Any], deal_name:str, as_of_date:Any, scenario_name:str)->str:
    rows=[{"line_item":"available_interest","amount":waterfall["interest_income_before_expenses"]},{"line_item":"administrative_expenses_paid","amount":waterfall["administrative_expenses_paid"]},{"line_item":"interest_paid","amount":sum(waterfall["interest_paid"].values())},{"line_item":"principal_diversion","amount":waterfall["cash_diverted_to_debt_paydown"]},{"line_item":"residual_equity_distribution","amount":waterfall["equity_cash_flow_after_diversion"]},{"line_item":"reconciliation_difference","amount":waterfall["cash_reconciliation"]["difference"]}]
    return dataframe_csv(pd.DataFrame(rows),deal_name,as_of_date,scenario_name)

def scenario_comparison_csv(runs:list[dict[str,Any]], deal_name:str, as_of_date:Any)->str:
    rows=[]
    for r in runs:
        met=r["scenario_kpi_snapshot"]["metrics"]; rows.append({"scenario_name":r["scenario_name"],"adjusted_collateral":met["total_adjusted_par"],"annual_interest_income":met["annual_interest_income"],"ccc_pct":met["ccc_pct"],"change_in_adjusted_collateral":r["change_in_adjusted_collateral"]})
    return dataframe_csv(pd.DataFrame(rows),deal_name,as_of_date,"Scenario Comparison")

def scenario_json(run:dict[str,Any], deal_name:str, as_of_date:Any)->str:
    return json.dumps({"metadata":metadata(deal_name,as_of_date,run["scenario_name"]),"scenario":run},default=str,indent=2)
