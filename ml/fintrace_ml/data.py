"""Loading PaySim-format CSV files with explicit dtypes and a schema check."""

import hashlib
from pathlib import Path

import pandas as pd

PAYSIM_DTYPES = {
    "step": "int32",
    "type": "category",
    "amount": "float64",
    "nameOrig": "string",
    "oldbalanceOrg": "float64",
    "newbalanceOrig": "float64",
    "nameDest": "string",
    "oldbalanceDest": "float64",
    "newbalanceDest": "float64",
    "isFraud": "int8",
}
OPTIONAL_DTYPES = {"isFlaggedFraud": "int8"}
TRANSACTION_TYPES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]
LABEL = "isFraud"


class DataError(ValueError):
    """The input file cannot be used for training."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_paysim(path: Path, nrows: int | None = None) -> pd.DataFrame:
    """Read a PaySim-format CSV, check its columns and values, return it sorted by step."""
    if not path.is_file():
        raise DataError(
            f"Data file not found: {path}. Download PaySim as described in the README "
            "('Getting PaySim') or use data/sample/synthetic_transactions.csv for a smoke test."
        )
    header = pd.read_csv(path, nrows=0).columns
    missing = sorted(set(PAYSIM_DTYPES) - set(header))
    if missing:
        raise DataError(f"{path.name} is missing required columns: {', '.join(missing)}")
    dtypes = PAYSIM_DTYPES | {k: v for k, v in OPTIONAL_DTYPES.items() if k in header}
    df = pd.read_csv(path, dtype=dtypes, usecols=list(dtypes), nrows=nrows)

    unknown_types = set(df["type"].astype(str).unique()) - set(TRANSACTION_TYPES)
    if unknown_types:
        raise DataError(f"Unknown transaction types: {sorted(unknown_types)}")
    if not set(df[LABEL].unique()) <= {0, 1}:
        raise DataError("isFraud must contain only 0 and 1")
    df["type"] = df["type"].cat.set_categories(TRANSACTION_TYPES)
    # Stable sort keeps the original file order inside each hour.
    return df.sort_values("step", kind="stable").reset_index(drop=True)
