"""Configurable monitoring rules.

Each rule row in `monitoring_rules` has a `rule_type` and a JSON `parameters` object. The
parameter schema for each type is a Pydantic model below, so an admin cannot save parameters the
engine would not understand. Rules are transparent checks that run next to the model; a hit adds
a `RULE_<CODE>` reason code and can raise the risk level to the rule's severity.
"""

from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import AppError
from app.models.enums import TransactionType


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LargeAmountParams(_Params):
    min_amount: Decimal = Field(gt=0)
    types: list[TransactionType] = Field(min_length=1)


class BalanceDrainParams(_Params):
    min_amount: Decimal = Field(ge=0)
    types: list[TransactionType] = Field(min_length=1)


class NewDestinationParams(_Params):
    min_amount: Decimal = Field(ge=0)
    types: list[TransactionType] = Field(min_length=1)


class VelocityParams(_Params):
    window_hours: int = Field(ge=1, le=24 * 31)
    max_count: int = Field(ge=1, le=10_000)


PARAM_SCHEMAS: dict[str, type[_Params]] = {
    "large_amount": LargeAmountParams,
    "balance_drain": BalanceDrainParams,
    "new_destination": NewDestinationParams,
    "origin_velocity": VelocityParams,
}


def validate_parameters(rule_type: str, parameters: dict) -> dict:
    schema = PARAM_SCHEMAS.get(rule_type)
    if schema is None:
        raise AppError(422, "VALIDATION_ERROR", f"Unknown rule type {rule_type!r}")
    try:
        return schema.model_validate(parameters).model_dump(mode="json")
    except ValidationError as exc:
        details = [
            {"field": "parameters." + ".".join(map(str, e["loc"])), "message": e["msg"]}
            for e in exc.errors()
        ]
        raise AppError(
            422, "VALIDATION_ERROR", f"Invalid parameters for {rule_type}", details
        ) from None


@dataclass(frozen=True)
class TxFacts:
    """What a rule may look at: the transaction plus counts of strictly earlier activity."""

    type: TransactionType
    amount: Decimal
    origin_balance_before: Decimal
    dest_account: str
    dest_prior_in: int
    origin_recent_count: int  # earlier transactions from the origin inside the velocity window


def evaluate_rule(rule_type: str, parameters: dict, facts: TxFacts) -> str | None:
    """Return a short human-readable detail if the rule fires, else None."""
    p = PARAM_SCHEMAS[rule_type].model_validate(parameters)
    if rule_type == "large_amount":
        if facts.type in p.types and facts.amount >= p.min_amount:
            return f"{facts.type.value} of {facts.amount:,.2f} is at least {p.min_amount:,.2f}"
    elif rule_type == "balance_drain":
        if (
            facts.type in p.types
            and facts.amount >= p.min_amount
            and facts.origin_balance_before > 0
            and facts.amount >= facts.origin_balance_before
        ):
            return (
                f"Amount {facts.amount:,.2f} empties a balance of "
                f"{facts.origin_balance_before:,.2f}"
            )
    elif rule_type == "new_destination":
        if (
            facts.type in p.types
            and facts.amount >= p.min_amount
            and not facts.dest_account.startswith("M")
            and facts.dest_prior_in == 0
        ):
            return f"First payment seen to {facts.dest_account}, amount {facts.amount:,.2f}"
    elif rule_type == "origin_velocity":
        total = facts.origin_recent_count + 1
        if total > p.max_count:
            return f"{total} transactions from this account within {p.window_hours} h"
    return None


def max_velocity_window(rules: list) -> int:
    windows = [
        int(r.parameters["window_hours"])
        for r in rules
        if r.enabled and r.rule_type == "origin_velocity"
    ]
    return max(windows, default=0)
