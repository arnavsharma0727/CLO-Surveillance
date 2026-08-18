"""Constants for ParGuard CLO Surveillance.

All factors and thresholds are illustrative educational simplifications, not
rating-agency methodology, trustee-report logic, legal interpretation, or
investment advice.
"""

from __future__ import annotations

DEFAULT_CCC_LIMIT_PCT = 0.075
DEFAULT_PASS_CUSHION_PCT = 0.01
DEFAULT_WATCH_LOWER_BOUND_PCT = -0.01
DEFAULT_ADMIN_EXPENSES = 1_500_000.0

RATING_ORDER = ["BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D"]
CCC_RATINGS = {"CCC+", "CCC", "CCC-", "CC", "C", "D"}

OC_FORMULA = "Adjusted Collateral Par / (Class Outstanding Par + Senior Debt Outstanding Par)"
IC_FORMULA = "Annual Portfolio Interest Income / Annual Interest Due for Class and Senior Debt"
