"""Data loading and Pydantic validation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from .models import DealTerms, LiabilityTranche, Loan

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _validate_records(records: Iterable[dict], model: type[Loan] | type[LiabilityTranche]) -> list[dict]:
    return [model(**record).model_dump() for record in records]


def load_collateral_pool(path: Path | str = DATA_DIR / "sample_collateral_pool.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    records = _validate_records(df.to_dict("records"), Loan)
    return pd.DataFrame(records)


def load_liability_stack(path: Path | str = DATA_DIR / "sample_liability_stack.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    records = _validate_records(df.to_dict("records"), LiabilityTranche)
    return pd.DataFrame(records)


def load_deal_terms(path: Path | str = DATA_DIR / "sample_deal_terms.json") -> DealTerms:
    return DealTerms(**json.loads(Path(path).read_text()))


def load_rating_factor_map(path: Path | str = DATA_DIR / "rating_factor_map.json") -> dict[str, object]:
    return json.loads(Path(path).read_text())
