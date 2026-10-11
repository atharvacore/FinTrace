"""Feature engineering shared by offline training and online scoring.

Leakage rules this module follows:

* No identifiers as features (account IDs only feed the history counts).
* No `isFlaggedFraud` (output of PaySim's own rule, a label proxy).
* The default `strict` feature set uses only what is known *before* the transaction executes:
  type, amount, pre-transaction balances, time of day, and counts of strictly earlier activity.
* Post-transaction balances (`newbalanceOrig`, `newbalanceDest`) are used only by the
  `with_post_balances` ablation, which exists to show how much they inflate results.
* History counts look only at strictly earlier steps (hours). Transactions in the same hour are
  not visible to each other, so row order inside an hour cannot leak information.
"""

import numpy as np
import pandas as pd

from fintrace_ml.data import TRANSACTION_TYPES

FEATURE_SETS = ("strict", "with_post_balances")
NIGHT_HOURS = range(0, 6)
LARGE_AMOUNT = 200_000.0  # same scale as PaySim's documented 200,000 transfer rule

STRICT_FEATURES = [
    *(f"type_{t}" for t in TRANSACTION_TYPES),
    "log_amount",
    "log_origin_balance_before",
    "log_dest_balance_before",
    "origin_balance_zero",
    "dest_balance_zero",
    "log_amount_to_origin_balance",
    "drains_origin_balance",
    "dest_is_merchant",
    "hour_sin",
    "hour_cos",
    "is_night",
    "log_origin_prior_tx",
    "log_dest_prior_in",
]
POST_BALANCE_FEATURES = [
    "log_origin_balance_after",
    "log_dest_balance_after",
    "origin_balance_error",
    "dest_balance_error",
]


def feature_names(feature_set: str) -> list[str]:
    if feature_set == "strict":
        return list(STRICT_FEATURES)
    if feature_set == "with_post_balances":
        return STRICT_FEATURES + POST_BALANCE_FEATURES
    raise ValueError(f"Unknown feature set {feature_set!r}; choose from {FEATURE_SETS}")


def _prior_count(df: pd.DataFrame, account_col: str) -> pd.Series:
    """For each row: how many rows with the same account occurred in strictly earlier steps."""
    per_step = df.groupby([account_col, "step"], sort=True, observed=True).size()
    before = per_step.groupby(level=0).cumsum() - per_step  # exclude the current step
    before.name = "_count"
    keys = pd.MultiIndex.from_frame(df[[account_col, "step"]])
    return pd.Series(before.reindex(keys).to_numpy(), index=df.index)


def add_history_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Add `origin_prior_tx` and `dest_prior_in` computed from the data frame itself.

    Offline only. Online scoring supplies these two counts from the database instead.
    """
    out = df.copy()
    out["origin_prior_tx"] = _prior_count(out, "nameOrig")
    out["dest_prior_in"] = _prior_count(out, "nameDest")
    return out


def build_features(df: pd.DataFrame, feature_set: str = "strict") -> pd.DataFrame:
    """Turn PaySim-shaped rows (with history counts) into a numeric feature matrix."""
    names = feature_names(feature_set)
    amount = df["amount"].astype("float64")
    orig_before = df["oldbalanceOrg"].astype("float64")
    dest_before = df["oldbalanceDest"].astype("float64")
    hour = (df["step"].astype("int64") - 1) % 24
    tx_type = df["type"].astype(str)

    X = pd.DataFrame(index=df.index)
    for t in TRANSACTION_TYPES:
        X[f"type_{t}"] = (tx_type == t).astype("float64")
    X["log_amount"] = np.log1p(amount)
    X["log_origin_balance_before"] = np.log1p(orig_before)
    X["log_dest_balance_before"] = np.log1p(dest_before)
    X["origin_balance_zero"] = (orig_before == 0).astype("float64")
    X["dest_balance_zero"] = (dest_before == 0).astype("float64")
    X["log_amount_to_origin_balance"] = np.log1p(amount / (orig_before + 1.0))
    X["drains_origin_balance"] = ((orig_before > 0) & (amount >= orig_before)).astype("float64")
    X["dest_is_merchant"] = df["nameDest"].astype(str).str.startswith("M").astype("float64")
    X["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    X["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    X["is_night"] = hour.isin(NIGHT_HOURS).astype("float64")
    X["log_origin_prior_tx"] = np.log1p(df["origin_prior_tx"].astype("float64"))
    X["log_dest_prior_in"] = np.log1p(df["dest_prior_in"].astype("float64"))

    if feature_set == "with_post_balances":
        orig_after = df["newbalanceOrig"].astype("float64")
        dest_after = df["newbalanceDest"].astype("float64")
        X["log_origin_balance_after"] = np.log1p(orig_after)
        X["log_dest_balance_after"] = np.log1p(dest_after)
        X["origin_balance_error"] = orig_before - amount - orig_after
        X["dest_balance_error"] = dest_before + amount - dest_after
    return X[names]


def risk_indicators(row: dict) -> list[str]:
    """Human-readable indicator codes for one transaction (explanations, not model attributions).

    `row` uses PaySim column names plus `dest_prior_in`. These flags describe *why a transaction
    looks unusual*; they do not claim to be what the model weighted most.
    """
    codes = []
    amount = float(row["amount"])
    orig_before = float(row["oldbalanceOrg"])
    if orig_before > 0 and amount >= orig_before:
        codes.append("DRAINS_ORIGIN_BALANCE")
    if row["type"] in ("TRANSFER", "CASH_OUT"):
        codes.append("HIGH_RISK_TYPE")
    if amount >= LARGE_AMOUNT:
        codes.append("LARGE_AMOUNT")
    if not str(row["nameDest"]).startswith("M") and int(row.get("dest_prior_in", 0)) == 0:
        codes.append("NEW_DESTINATION")
    if (int(row["step"]) - 1) % 24 in NIGHT_HOURS:
        codes.append("NIGHT_HOUR")
    if float(row["oldbalanceDest"]) == 0 and not str(row["nameDest"]).startswith("M"):
        codes.append("EMPTY_DESTINATION_BALANCE")
    return codes
