"""Educational CSV and PDF-text ingestion utilities for ParGuard."""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd
from pydantic import ValidationError
from .constants import RATING_ORDER
from .models import DealTerms, LiabilityTranche, Loan

DISCLAIMER="ParGuard’s import workflow is an illustrative educational parser. Actual CLO trustee reports and indentures vary materially by transaction. Imported information must be reviewed and validated by a qualified user. This application does not provide a legal interpretation of transaction documents."
REQUIRED_COLLATERAL_COLUMNS=["loan_id","obligor_name","industry","rating","par_balance","market_price","spread_bps","remaining_life_years","recovery_rate","default_status","ccc_flag","watchlist_flag"]
OPTIONAL_COLLATERAL_COLUMNS=["seniority","country","maturity_date","coupon_rate","benchmark_rate","collateral_haircut_pct"]
REQUIRED_LIABILITY_COLUMNS=["tranche_name","seniority_rank","outstanding_balance","annual_coupon_rate","oc_trigger","ic_trigger"]

def collateral_template()->pd.DataFrame:
    return pd.DataFrame([{c:"" for c in REQUIRED_COLLATERAL_COLUMNS+OPTIONAL_COLLATERAL_COLUMNS}])
def liability_template()->pd.DataFrame:
    return pd.DataFrame([{c:"" for c in REQUIRED_LIABILITY_COLUMNS}])
def deal_terms_template()->dict[str,Any]:
    return {"deal_name":"Imported Educational Deal","as_of_date":"2026-08-18","reinvestment_status":"Illustrative / user import","ccc_concentration_limit":0.075,"ccc_excess_haircut_description":"Educational excess-CCC treatment.","defaulted_interest_zero":True,"administrative_expenses":1500000.0,"disclaimer":"Synthetic / illustrative user import; validate before use."}

def _bool(x):
    if isinstance(x,bool): return x
    return str(x).strip().lower() in {"true","1","yes","y"}

def validate_collateral_csv(df: pd.DataFrame)->dict[str,Any]:
    errors=[]; missing=[c for c in REQUIRED_COLLATERAL_COLUMNS if c not in df.columns]
    if missing: errors += [{"row":None,"field":c,"error":"missing required column"} for c in missing]
    if errors: return {"valid":False,"errors":errors,"data":pd.DataFrame()}
    out=df.copy()
    defaults={"seniority":"First Lien","country":"United States","maturity_date":"2031-12-31","benchmark_rate":0.0425,"collateral_haircut_pct":0.0}
    for k,v in defaults.items():
        if k not in out.columns: out[k]=v
    for b in ["default_status","ccc_flag","watchlist_flag"]: out[b]=out[b].map(_bool)
    if "coupon_rate" not in out.columns or out["coupon_rate"].isna().any(): out["coupon_rate"]=(pd.to_numeric(out["benchmark_rate"],errors="coerce")+pd.to_numeric(out["spread_bps"],errors="coerce")/10000)
    out["annual_interest_income"]=pd.to_numeric(out["par_balance"],errors="coerce")*pd.to_numeric(out["coupon_rate"],errors="coerce"); out.loc[out["default_status"],"annual_interest_income"]=0.0
    if out["loan_id"].duplicated().any():
        for i in out.index[out["loan_id"].duplicated(keep=False)]: errors.append({"row":int(i)+2,"field":"loan_id","error":"duplicate loan_id"})
    for i,r in out.iterrows():
        if r["rating"] not in RATING_ORDER: errors.append({"row":int(i)+2,"field":"rating","error":"unsupported rating"})
        if pd.isna(r["loan_id"]) or str(r["loan_id"]).strip()=="": errors.append({"row":int(i)+2,"field":"loan_id","error":"required value is blank"})
        for f in ["par_balance","market_price","spread_bps","remaining_life_years","recovery_rate","coupon_rate","benchmark_rate","collateral_haircut_pct"]:
            val=pd.to_numeric(r[f],errors="coerce")
            if pd.isna(val): errors.append({"row":int(i)+2,"field":f,"error":"not numeric"})
            elif val<0: errors.append({"row":int(i)+2,"field":f,"error":"negative value"})
        if not (0 <= float(r["recovery_rate"]) <= 1): errors.append({"row":int(i)+2,"field":"recovery_rate","error":"must be between 0 and 1"})
        if str(r["seniority"]) not in {"First Lien","Second Lien"}: errors.append({"row":int(i)+2,"field":"seniority","error":"must be First Lien or Second Lien"})
    if errors: return {"valid":False,"errors":errors,"data":out}
    out["rating_factor"]=out["rating"].map({"BB":100,"BB-":150,"B+":250,"B":350,"B-":500,"CCC+":900,"CCC":1200,"CCC-":1800,"CC":3000,"C":5000,"D":10000})
    return {"valid":True,"errors":[],"data":pd.DataFrame([Loan(**rec).model_dump() for rec in out.to_dict("records")])}

def validate_liability_csv(df: pd.DataFrame)->dict[str,Any]:
    errors=[]; missing=[c for c in REQUIRED_LIABILITY_COLUMNS if c not in df.columns]
    if missing: return {"valid":False,"errors":[{"row":None,"field":c,"error":"missing required column"} for c in missing],"data":pd.DataFrame()}
    out=df.rename(columns={"outstanding_balance":"outstanding_par"}).copy(); out["is_equity"]=False
    for i,r in out.iterrows():
        for f in ["seniority_rank","outstanding_par","annual_coupon_rate","oc_trigger","ic_trigger"]:
            val=pd.to_numeric(r[f],errors="coerce")
            if pd.isna(val): errors.append({"row":int(i)+2,"field":f,"error":"not numeric"})
            elif val<0: errors.append({"row":int(i)+2,"field":f,"error":"negative value"})
    if errors: return {"valid":False,"errors":errors,"data":out}
    return {"valid":True,"errors":[],"data":pd.DataFrame([LiabilityTranche(**rec).model_dump() for rec in out.to_dict("records")])}

def error_report_csv(errors:list[dict[str,Any]])->str:
    return pd.DataFrame(errors).to_csv(index=False)

def parse_deal_terms_json(text:str)->DealTerms:
    data={**deal_terms_template(), **json.loads(text or "{}")}; return DealTerms(**data)

def extract_pdf_text(file_obj)->dict[str,Any]:
    try:
        from pypdf import PdfReader
        reader=PdfReader(file_obj); text="\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        return {"ok":False,"error":f"Text-based PDF extraction failed: {exc}. Use CSV templates instead.","text":"","candidates":{},"audit_log":[]}
    candidates={}
    pats={"deal_name":r"Deal Name[:\s]+([^\n]+)","as_of_date":r"As[- ]of Date[:\s]+([0-9/-]+)","oc_ratio":r"OC Ratio[:\s]+([0-9.]+%?)","ic_ratio":r"IC Ratio[:\s]+([0-9.]+x?)","total_collateral_principal_amount":r"Total Collateral Principal Amount[:\s$]+([0-9,.]+)"}
    for k,p in pats.items():
        m=re.search(p,text,re.I); 
        if m: candidates[k]=m.group(1).strip()
    return {"ok":True,"error":"","text":text,"candidates":candidates,"audit_log":[{"timestamp":datetime.now(timezone.utc).isoformat(),"message":"Unverified candidate values extracted from text-based PDF only."}]}
