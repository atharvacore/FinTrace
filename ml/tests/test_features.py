import pandas as pd
import pytest

from fintrace_ml.features import (
    POST_BALANCE_FEATURES,
    STRICT_FEATURES,
    add_history_counts,
    build_features,
    feature_names,
    risk_indicators,
)
from tests.conftest import frame


def test_history_counts_only_see_strictly_earlier_steps():
    df = frame(
        [
            (1, "TRANSFER", 10.0, "C1", 10, 0, "C9", 0, 10, 0),
            (1, "TRANSFER", 10.0, "C1", 10, 0, "C9", 0, 10, 0),  # same hour: not visible
            (2, "CASH_OUT", 10.0, "C1", 10, 0, "C9", 0, 10, 0),
            (5, "PAYMENT", 10.0, "C2", 10, 0, "C9", 0, 0, 0),
        ]
    )
    out = add_history_counts(df)
    assert out["origin_prior_tx"].tolist() == [0, 0, 2, 0]
    assert out["dest_prior_in"].tolist() == [0, 0, 2, 3]


def test_history_counts_do_not_depend_on_row_order_within_a_step():
    df = frame(
        [
            (1, "TRANSFER", 10.0, "C1", 10, 0, "C9", 0, 10, 0),
            (1, "TRANSFER", 20.0, "C1", 20, 0, "C9", 0, 20, 1),
            (2, "TRANSFER", 30.0, "C1", 30, 0, "C9", 0, 30, 0),
        ]
    )
    forward = add_history_counts(df)
    backward = add_history_counts(df.iloc[[1, 0, 2]].reset_index(drop=True))
    assert sorted(forward["origin_prior_tx"]) == sorted(backward["origin_prior_tx"])
    assert forward.loc[2, "origin_prior_tx"] == backward.loc[2, "origin_prior_tx"] == 2


def test_strict_features_exclude_post_transaction_information_and_identifiers():
    names = feature_names("strict")
    assert names == STRICT_FEATURES
    assert not set(POST_BALANCE_FEATURES) & set(names)
    for forbidden in ("newbalance", "after", "error", "nameOrig", "nameDest", "Flagged", "isFraud"):
        assert not any(forbidden in n for n in names), forbidden


def test_strict_features_unchanged_when_post_balances_change():
    df = add_history_counts(frame([(3, "TRANSFER", 100.0, "C1", 100, 0, "C2", 0, 0, 1)]))
    tampered = df.assign(newbalanceOrig=999.0, newbalanceDest=12345.0)
    pd.testing.assert_frame_equal(build_features(df), build_features(tampered))
    assert not build_features(df, "with_post_balances").equals(
        build_features(tampered, "with_post_balances")
    )


def test_feature_values_for_a_known_row():
    df = add_history_counts(frame([(1, "TRANSFER", 100.0, "C1", 100, 0, "M2", 0, 0, 1)]))
    X = build_features(df).iloc[0]
    assert X["type_TRANSFER"] == 1 and X["type_PAYMENT"] == 0
    assert X["drains_origin_balance"] == 1
    assert X["dest_is_merchant"] == 1
    assert X["is_night"] == 1  # step 1 -> hour 0
    assert X.notna().all()


def test_no_origin_balance_set_drops_every_origin_balance_feature():
    names = feature_names("no_origin_balance")
    assert not any("origin_balance" in n for n in names)
    df = add_history_counts(frame([(3, "TRANSFER", 100.0, "C1", 100, 0, "C2", 0, 0, 1)]))
    assert list(build_features(df, "no_origin_balance").columns) == names


def test_unknown_feature_set_is_rejected():
    with pytest.raises(ValueError, match="Unknown feature set"):
        feature_names("everything")


def test_risk_indicators_are_explainable_flags():
    row = {"step": 3, "type": "TRANSFER", "amount": 500_000, "oldbalanceOrg": 500_000,
           "nameDest": "C77", "oldbalanceDest": 0, "dest_prior_in": 0}  # fmt: skip
    assert risk_indicators(row) == [
        "DRAINS_ORIGIN_BALANCE",
        "HIGH_RISK_TYPE",
        "LARGE_AMOUNT",
        "NEW_DESTINATION",
        "NIGHT_HOUR",
        "EMPTY_DESTINATION_BALANCE",
    ]
    quiet = row | {"type": "PAYMENT", "amount": 10, "nameDest": "M1", "step": 12}
    assert risk_indicators(quiet) == []
