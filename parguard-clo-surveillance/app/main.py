from __future__ import annotations
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from app.core.audit import analyst_morning_brief, attribution_bridges, concentration_tables, model_audit, quality_test_dashboard
from app.core.data_loader import load_collateral_pool, load_deal_terms, load_liability_stack
from app.core.exports import coverage_tests_csv, dataframe_csv, scenario_comparison_csv, scenario_json, surveillance_memo_html, surveillance_memo_markdown, waterfall_csv
from app.core.importer import DISCLAIMER as IMPORT_DISCLAIMER, collateral_template, deal_terms_template, error_report_csv, extract_pdf_text, liability_template, parse_deal_terms_json, validate_collateral_csv, validate_liability_csv
from app.core.scenarios import run_preset_scenario
from app.core.waterfall import run_annual_waterfall

st.set_page_config(page_title="ParGuard CLO Surveillance", layout="wide")
fmt_m=lambda x:f"${x/1_000_000:,.1f}m"; fmt_p=lambda x:f"{x:.2%}"; fmt_bps=lambda x:f"{x:,.0f} bps"
SCENARIOS={"Base Case":"base_case","CCC Migration Shock":"ccc_migration_shock","Healthcare Sector Shock":"healthcare_sector_shock","Severe Default and Recovery Shock":"severe_default_recovery_shock","Rate / Spread Compression Shock":"rate_spread_compression_shock"}
if "loans" not in st.session_state:
    st.session_state.loans=load_collateral_pool(); st.session_state.liabilities=load_liability_stack(); st.session_state.terms=load_deal_terms(); st.session_state.deal_source="Sample deal"; st.session_state.scenario="Base Case"
terms=st.session_state.terms; liabilities=st.session_state.liabilities
with st.sidebar:
    st.title("ParGuard")
    st.caption("CLO surveillance — simplified / illustrative")
    st.write(f"**Active deal:** {terms.deal_name}"); st.write(f"**Deal source:** {st.session_state.deal_source}"); st.write(f"**As-of date:** {terms.as_of_date}")
    st.session_state.scenario=st.selectbox("Selected scenario", list(SCENARIOS), index=list(SCENARIOS).index(st.session_state.scenario))
    if st.button("Reset to sample deal"):
        st.session_state.clear(); st.rerun()
with st.spinner("Running deterministic scenario..."):
    run=run_preset_scenario(SCENARIOS[st.session_state.scenario], st.session_state.loans, liabilities, terms.ccc_concentration_limit)
loans=pd.DataFrame(run["scenario_loans"]); metrics=run["scenario_kpi_snapshot"]["metrics"]; waterfall=run_annual_waterfall(metrics["annual_interest_income"],metrics["total_adjusted_par"],liabilities,terms.administrative_expenses); brief=analyst_morning_brief(loans,liabilities,terms,run["scenario_name"])
st.sidebar.metric("Coverage status", brief["overall_risk_status"]); st.sidebar.caption("Disclaimer: synthetic educational model; not investment/legal advice.")
page=st.sidebar.radio("Navigate",["Deal Overview","Collateral Surveillance","Coverage Tests","Cash Flow Waterfall","Scenario Comparison","Model Audit & Reconciliation","Report Ingestion","Surveillance Memo & Exports","Model Limitations"])
st.title("ParGuard CLO Surveillance")
if page=="Deal Overview":
    st.header("Analyst Morning Brief")
    c=st.columns(4); c[0].metric("Risk status",brief["overall_risk_status"]); c[1].metric("Adjusted collateral",fmt_m(metrics["total_adjusted_par"])); c[2].metric("CCC vs threshold",fmt_bps(brief["ccc_exposure_vs_threshold"]*10000)); c[3].metric("Equity after diversion",fmt_m(waterfall["equity_cash_flow_after_diversion"]))
    st.write(brief["status_explanation"]); st.write("**Next action:** "+brief["next_action_item"])
    with st.expander("Show calculation"):
        st.json(brief); st.caption("All values derive from scenario metrics, coverage tests, and the selected liability stack.")
    st.subheader("Capital stack"); st.dataframe(liabilities,use_container_width=True)
    st.subheader("Collateral by industry"); st.plotly_chart(px.bar(loans.groupby("industry",as_index=False).par_balance.sum(),x="industry",y="par_balance"),use_container_width=True)
elif page=="Collateral Surveillance":
    st.header("Collateral Quality Tests")
    q=pd.DataFrame(quality_test_dashboard(loans,terms.ccc_concentration_limit,base_loans=st.session_state.loans)); st.dataframe(q,use_container_width=True)
    tabs=concentration_tables(loans); st.subheader("Industry x rating exposure heatmap"); st.plotly_chart(px.imshow(tabs["industry_rating"],aspect="auto"),use_container_width=True)
    st.subheader("Top obligor concentration"); st.dataframe(tabs["top_obligors"],use_container_width=True)
    st.subheader("Watchlist / default heatmap"); st.plotly_chart(px.imshow(tabs["watch_default"],aspect="auto"),use_container_width=True)
    st.subheader("Exposure buckets"); st.dataframe(tabs["price_bucket"],use_container_width=True); st.dataframe(tabs["life_bucket"],use_container_width=True)
elif page=="Coverage Tests":
    st.header("OC / IC Tests")
    df=pd.DataFrame(run["scenario_kpi_snapshot"]["oc_tests"]+run["scenario_kpi_snapshot"]["ic_tests"]); st.dataframe(df,use_container_width=True)
    with st.expander("Show calculation formulas"): st.write(df[["tranche_name","test_type","numerator","denominator","trigger","actual_ratio","cushion_bps","status","formula"]])
elif page=="Cash Flow Waterfall":
    st.header("Cash Flow Waterfall")
    st.json(waterfall); st.subheader("Cash reconciliation"); st.dataframe(pd.DataFrame([waterfall["cash_reconciliation"]]),use_container_width=True)
elif page=="Scenario Comparison":
    st.header("Scenario Comparison")
    runs=[run_preset_scenario(v,st.session_state.loans,liabilities,terms.ccc_concentration_limit) for v in SCENARIOS.values()]
    comp=pd.DataFrame([{ "scenario":r["scenario_name"], **r["scenario_kpi_snapshot"]["metrics"]} for r in runs]); st.dataframe(comp,use_container_width=True); st.plotly_chart(px.bar(comp,x="scenario",y="total_adjusted_par"),use_container_width=True)
    st.subheader("Deterioration attribution"); attr=attribution_bridges(st.session_state.loans,loans,terms.ccc_concentration_limit); st.dataframe(pd.DataFrame(attr["oc_attribution"]),use_container_width=True); st.dataframe(pd.DataFrame(attr["ic_attribution"]),use_container_width=True)
elif page=="Model Audit & Reconciliation":
    st.header("Model Audit & Reconciliation"); audit=model_audit(loans,liabilities,terms,run); st.json(audit); st.dataframe(pd.DataFrame(audit["validation_flags"]),use_container_width=True)
elif page=="Report Ingestion":
    st.header("Report Ingestion"); st.warning(IMPORT_DISCLAIMER)
    st.download_button("Download collateral CSV template",collateral_template().to_csv(index=False),"collateral_template.csv"); st.download_button("Download liability CSV template",liability_template().to_csv(index=False),"liability_template.csv"); st.download_button("Download deal terms JSON template",json.dumps(deal_terms_template(),indent=2),"deal_terms_template.json")
    cfile=st.file_uploader("Collateral portfolio CSV",type="csv"); lfile=st.file_uploader("Liability stack CSV",type="csv"); jfile=st.file_uploader("Optional deal-terms JSON",type="json")
    if cfile and lfile:
        with st.spinner("Validating import..."):
            cv=validate_collateral_csv(pd.read_csv(cfile)); lv=validate_liability_csv(pd.read_csv(lfile))
        if not cv["valid"] or not lv["valid"]:
            errs=cv["errors"]+lv["errors"]; st.error("Import validation failed"); st.dataframe(pd.DataFrame(errs)); st.download_button("Download error report",error_report_csv(errs),"import_errors.csv")
        else:
            st.success("Validation passed. Preview before loading."); st.dataframe(cv["data"].head(25)); choice=st.radio("Import action",["Load as a temporary session deal","Save as a named local deal","Cancel import"])
            if st.button("Confirm import") and choice!="Cancel import":
                st.session_state.loans=cv["data"]; st.session_state.liabilities=lv["data"]; st.session_state.terms=parse_deal_terms_json(jfile.read().decode() if jfile else "{}"); st.session_state.deal_source="Imported temporary deal" if choice.startswith("Load") else "Saved local deal"; st.rerun()
    pdf=st.file_uploader("Optional text-based PDF sample",type="pdf")
    if pdf:
        ext=extract_pdf_text(pdf); st.write(ext.get("error") or "Unverified candidate values:"); st.json(ext.get("candidates",{})); st.text_area("Raw extracted text",ext.get("text",""),height=250)
elif page=="Surveillance Memo & Exports":
    st.header("Surveillance Memo & Exports"); md=surveillance_memo_markdown(terms.deal_name,terms.as_of_date,run["scenario_name"],run,waterfall,brief); st.markdown(md)
    st.download_button("Memo Markdown",md,"surveillance_memo.md"); st.download_button("Memo HTML",surveillance_memo_html(terms.deal_name,terms.as_of_date,run["scenario_name"],run,waterfall,brief),"surveillance_memo.html"); st.download_button("Collateral CSV",dataframe_csv(loans,terms.deal_name,terms.as_of_date,run["scenario_name"]),"collateral.csv"); st.download_button("Coverage CSV",coverage_tests_csv(run,terms.deal_name,terms.as_of_date),"coverage_tests.csv"); st.download_button("Waterfall CSV",waterfall_csv(waterfall,terms.deal_name,terms.as_of_date,run["scenario_name"]),"waterfall.csv"); st.download_button("Scenario Comparison CSV",scenario_comparison_csv([run],terms.deal_name,terms.as_of_date),"scenario_comparison.csv"); st.download_button("Scenario JSON",scenario_json(run,terms.deal_name,terms.as_of_date),"scenario.json")
else:
    st.header("Model Limitations"); st.info("This synthetic illustrative model does not replace trustee reports, indentures, ratings, valuation, investment recommendations, or legal analysis. Actual CLO transaction terms differ materially.")
