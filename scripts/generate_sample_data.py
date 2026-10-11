"""Generate a small SYNTHETIC transaction file in the PaySim CSV format.

This is NOT PaySim. It is a stand-in so that the app, tests and demo work before you download
the real PaySim dataset (see README). It deliberately copies PaySim's column layout and a few of
its documented behaviours, and makes no claim to match its statistics:

* Five transaction types with roughly PaySim-like proportions.
* `step` is an hour index; normal activity follows a day/night cycle, fraud does not.
* Fraud pattern: an account is taken over, its whole balance is TRANSFERred to a mule account and
  then CASHed OUT, both rows labelled isFraud=1.
* Merchant accounts ("M...") have zero recorded balances, as in PaySim.
* isFlaggedFraud mimics PaySim's toy rule (TRANSFER over 200,000), which the app ignores.

The fraud rate defaults to ~2% of rows, far higher than PaySim's ~0.13%, so a small demo file
contains enough positives to look at. Never report model metrics from this file as real results.

Usage (standard library only, works in PowerShell and bash):
    python scripts/generate_sample_data.py --rows 5000 --out data/sample/synthetic_transactions.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

HEADER = [
    "step",
    "type",
    "amount",
    "nameOrig",
    "oldbalanceOrg",
    "newbalanceOrig",
    "nameDest",
    "oldbalanceDest",
    "newbalanceDest",
    "isFraud",
    "isFlaggedFraud",
]

TYPE_WEIGHTS = {
    "CASH_OUT": 0.35,
    "PAYMENT": 0.34,
    "CASH_IN": 0.22,
    "TRANSFER": 0.083,
    "DEBIT": 0.007,
}
# (median, spread) of a log-normal amount distribution per type
AMOUNT_PARAMS = {
    "CASH_OUT": (120_000, 0.9),
    "PAYMENT": (9_000, 1.0),
    "CASH_IN": (100_000, 0.9),
    "TRANSFER": (450_000, 1.1),
    "DEBIT": (3_500, 0.9),
}
# Relative activity by hour of day: quiet at night, busy in the day (fraud ignores this).
HOURLY_ACTIVITY = [0.1, 0.05, 0.03, 0.03, 0.05, 0.1, 0.3, 0.6, 0.9, 1.0, 1.0, 1.0,
                   1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.95, 0.9, 0.8, 0.6, 0.4, 0.2]  # fmt: skip
PAYSIM_FLAG_THRESHOLD = 200_000


class Generator:
    def __init__(self, seed: int, n_customers: int, n_merchants: int) -> None:
        self.rng = random.Random(seed)  # noqa: S311 (reproducible simulation, not security)
        self.customers = [f"C{self.rng.randrange(10**8, 10**10)}" for _ in range(n_customers)]
        self.merchants = [f"M{self.rng.randrange(10**8, 10**10)}" for _ in range(n_merchants)]
        self.balance = {
            c: (0.0 if self.rng.random() < 0.3 else round(self.rng.lognormvariate(11, 1.2), 2))
            for c in self.customers
        }

    def amount(self, tx_type: str) -> float:
        median, spread = AMOUNT_PARAMS[tx_type]
        return max(round(self.rng.lognormvariate(math.log(median), spread), 2), 1.0)

    def normal(self, step: int) -> list:
        rng = self.rng
        tx_type = rng.choices(list(TYPE_WEIGHTS), weights=list(TYPE_WEIGHTS.values()))[0]
        orig = rng.choice(self.customers)
        amount = self.amount(tx_type)
        old_orig = self.balance[orig]
        if tx_type == "CASH_IN":
            new_orig = round(old_orig + amount, 2)
        else:
            new_orig = round(max(old_orig - amount, 0.0), 2)
        self.balance[orig] = new_orig

        if tx_type == "PAYMENT":
            dest, old_dest, new_dest = rng.choice(self.merchants), 0.0, 0.0
        else:
            dest = rng.choice(self.customers)
            old_dest = self.balance[dest]
            delta = -amount if tx_type == "CASH_IN" else amount
            new_dest = round(max(old_dest + delta, 0.0), 2)
            self.balance[dest] = new_dest
        return [step, tx_type, amount, orig, old_orig, new_orig, dest, old_dest, new_dest, 0, 0]

    def fraud(self, step: int) -> list[list]:
        rng = self.rng
        funded = [c for c in self.customers if self.balance[c] > 1_000]
        victim = rng.choice(funded or self.customers)
        amount = round(min(max(self.balance[victim], 1.0), 10_000_000), 2)
        old = self.balance[victim]
        self.balance[victim] = 0.0
        mule = f"C{rng.randrange(10**8, 10**10)}"
        cash_dest = rng.choice(self.customers)
        flagged = 1 if amount > PAYSIM_FLAG_THRESHOLD and rng.random() < 0.02 else 0
        transfer = [step, "TRANSFER", amount, victim, old, 0.0, mule, 0.0, 0.0, 1, flagged]
        old_cash_dest = self.balance[cash_dest]
        cash_out = [step, "CASH_OUT", amount, victim, amount, 0.0, cash_dest,
                    old_cash_dest, round(old_cash_dest + amount, 2), 1, 0]  # fmt: skip
        return [transfer, cash_out]


def generate(rows: int, steps: int, fraud_rate: float, seed: int) -> list[list]:
    """Simulate hour by hour, in order, so account balances carry forward consistently."""
    gen = Generator(seed, n_customers=max(rows // 3, 50), n_merchants=max(rows // 20, 10))
    hourly = [HOURLY_ACTIVITY[(s - 1) % 24] for s in range(1, steps + 1)]
    normal_total = rows * (1 - fraud_rate)
    fraud_events_per_step = rows * fraud_rate / 2 / steps  # each fraud event writes two rows

    out: list[list] = []
    for step in range(1, steps + 1):
        # Normal volume follows the day/night cycle; fraud arrives at a flat rate.
        expected_normal = normal_total * hourly[step - 1] / sum(hourly)
        n_normal = int(expected_normal) + (gen.rng.random() < expected_normal % 1)
        n_fraud = int(fraud_events_per_step) + (gen.rng.random() < fraud_events_per_step % 1)
        events = ["normal"] * n_normal + ["fraud"] * n_fraud
        gen.rng.shuffle(events)
        for event in events:
            out.extend(gen.fraud(step) if event == "fraud" else [gen.normal(step)])
    return out[:rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--steps", type=int, default=72, help="Simulated hours (72 = 3 days)")
    parser.add_argument("--fraud-rate", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/sample/synthetic_transactions.csv"))
    args = parser.parse_args()

    rows = generate(args.rows, args.steps, args.fraud_rate, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow([f"{v:.2f}" if isinstance(v, float) else v for v in row])
    frauds = sum(r[9] for r in rows)
    print(f"Wrote {len(rows)} synthetic rows ({frauds} labelled fraud) to {args.out}")


if __name__ == "__main__":
    main()
