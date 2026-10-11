from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CSV = REPO_ROOT / "data" / "sample" / "synthetic_transactions.csv"


@pytest.fixture
def sample_csv() -> Path:
    return SAMPLE_CSV


def frame(rows: list[tuple]) -> pd.DataFrame:
    """rows: (step, type, amount, nameOrig, oldOrg, newOrig, nameDest, oldDest, newDest, isFraud)"""
    cols = ["step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
            "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud"]  # fmt: skip
    return pd.DataFrame(rows, columns=cols)
