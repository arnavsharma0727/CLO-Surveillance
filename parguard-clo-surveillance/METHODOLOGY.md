# Methodology

ParGuard uses synthetic inputs and simplified CLO math designed for transparency and recruiter demonstration.

## Adjusted collateral

Loan-level adjusted par equals par less explicit collateral haircut for performing assets. Defaulted assets receive par times disclosed recovery rate and zero annual interest income. Portfolio adjusted collateral equals loan-level adjusted par less excess-CCC haircut.

## CCC concentration treatment

CCC par is compared with the configured CCC concentration limit. Excess CCC par above the limit is valued using the lower of aggregate CCC market value or 50% of CCC par, applied proportionally to the excess amount. The shortfall is deducted from adjusted collateral.

## OC tests

OC ratio = adjusted collateral par / cumulative debt balance through the tested class. Cushion = actual ratio minus trigger and is displayed in basis points.

## IC tests

IC ratio = annual portfolio interest income / cumulative annual interest due through the tested class. Defaulted assets contribute zero interest income.

## Collateral-quality metrics

The dashboard calculates WARF, WAS, WARR, WAL, CCC exposure, a ParGuard Diversification Index, largest single-obligor concentration, and largest industry concentration. The diversification index is educational and combines issuer HHI, issuer count, and industry HHI.

## Scenario mechanics

Preset scenarios deterministically migrate ratings, shock prices, apply haircuts, override recoveries, or compress rates/spreads. Base case applies no stress. Severe default stress sets selected assets to default, applies disclosed recovery values, and zeros defaulted-loan income.

## Simplified waterfall

Available annual interest pays administrative expenses, debt interest in seniority order, then diverts residual cash to debt paydown if any OC/IC test fails. Remaining residual is distributed to equity. The waterfall reconciles available interest to admin, interest paid, diversion, and equity distribution.

## Differences from actual CLO calculations

Actual CLO indentures and trustee reports vary materially. Production calculations may include asset-specific eligibility, discount obligations, CCC buckets by agency, defaulted-interest conventions, trading gains/losses, reinvestment criteria, fees, taxes, hedges, cure mechanics, payment-date timing, and legal definitions not modeled here.
