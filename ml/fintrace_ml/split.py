"""Chronological train / validation / test split by PaySim step (hour)."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SplitBoundaries:
    train_last_step: int
    valid_last_step: int
    test_last_step: int

    def as_dict(self) -> dict:
        return asdict(self)


def chronological_split(
    df: pd.DataFrame, train_frac: float = 0.70, valid_frac: float = 0.15
) -> tuple[pd.Series, pd.Series, pd.Series, SplitBoundaries]:
    """Return boolean masks (train, valid, test) and the step boundaries.

    Cuts happen between whole steps, so no hour appears in two splits: every validation row is
    later than every training row, and every test row is later than every validation row.
    """
    if not 0 < train_frac < 1 or not 0 < valid_frac < 1 or train_frac + valid_frac >= 1:
        raise ValueError("Need 0 < train_frac, valid_frac and train_frac + valid_frac < 1")
    counts = df.groupby("step").size().sort_index()
    cum = counts.cumsum() / counts.sum()
    steps = counts.index.to_numpy()

    train_last = int(steps[np.searchsorted(cum.to_numpy(), train_frac)])
    valid_last = int(steps[np.searchsorted(cum.to_numpy(), train_frac + valid_frac)])
    if valid_last <= train_last:
        later = steps[steps > train_last]
        if len(later) < 2:
            raise ValueError("Not enough distinct steps for a chronological split")
        valid_last = int(later[0])
    test_last = int(steps[-1])
    if test_last <= valid_last:
        raise ValueError("Not enough distinct steps left for a test split")

    train = df["step"] <= train_last
    valid = (df["step"] > train_last) & (df["step"] <= valid_last)
    test = df["step"] > valid_last
    return train, valid, test, SplitBoundaries(train_last, valid_last, test_last)
