# Data Dictionary

## Collateral CSV

| Field | Type | Required | Units / allowed values |
|---|---:|:---:|---|
| loan_id | string | Yes | Unique loan identifier |
| obligor_name | string | Yes | Borrower / issuer name |
| industry | string | Yes | Industry sector |
| rating | string | Yes | BB, BB-, B+, B, B-, CCC+, CCC, CCC-, CC, C, D |
| par_balance | number | Yes | Dollars; non-negative |
| market_price | number | Yes | Price points; non-negative |
| spread_bps | number | Yes | Basis points; non-negative |
| remaining_life_years | number | Yes | Years; non-negative |
| recovery_rate | number | Yes | Decimal 0–1 |
| default_status | boolean | Yes | true/false |
| ccc_flag | boolean | Yes | true/false |
| watchlist_flag | boolean | Yes | true/false |
| seniority | string | Optional | First Lien or Second Lien |
| country | string | Optional | Country name |
| maturity_date | date | Optional | ISO date preferred |
| coupon_rate | number | Optional | Decimal annual rate |
| benchmark_rate | number | Optional | Decimal annual rate |
| collateral_haircut_pct | number | Optional | Decimal 0–1 |

## Liability CSV

| Field | Type | Required | Units / allowed values |
|---|---:|:---:|---|
| tranche_name | string | Yes | Tranche label |
| seniority_rank | integer | Yes | 1 = most senior |
| outstanding_balance | number | Yes | Dollars; non-negative |
| annual_coupon_rate | number | Yes | Decimal annual rate |
| oc_trigger | number | Yes | Ratio trigger |
| ic_trigger | number | Yes | Ratio trigger |

## Deal-terms JSON

Fields: `deal_name` string, `as_of_date` ISO date, `reinvestment_status` string, `ccc_concentration_limit` decimal 0–1, `ccc_excess_haircut_description` string, `defaulted_interest_zero` boolean, `administrative_expenses` non-negative dollars, and `disclaimer` string.
