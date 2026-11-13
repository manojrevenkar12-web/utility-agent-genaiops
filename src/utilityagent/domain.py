"""What the agent works with: a customer's account as the billing system returns it, what the model read from a
message, and what the agent decided."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

# what each intent needs before account data may be used
NEEDS_IDENTITY = {
    "meter_reading",
    "instalment_change",
    "payment_plan",
    "bill_explanation",
    "tariff_switch",
    "move_out",
    "cancellation",
    "account_info",
}
INTENTS = sorted(NEEDS_IDENTITY | {"outage", "faq", "other"})


@dataclass(frozen=True)
class Account:
    customer_no: str
    postcode: str
    commodity: str  # electricity | gas
    tariff: str  # Grundversorgung | Flex | Fix24 | Oeko12
    fixed_until: date | None
    price_ct: float
    base_eur_month: float
    annual_kwh: float
    prev_year_kwh: float
    prev_price_ct: float
    instalment_eur: float
    last_reading: float
    last_reading_date: date
    balance_eur: float
    dunning_stage: int
    hardship: bool
    broken_plan_12m: bool


class Accounts(Protocol):
    """The billing system's read API, as the customer's IT team would expose it."""

    def get(self, customer_no: str) -> Account | None: ...

    def tariffs_for(self, postcode: str, commodity: str) -> list[str]: ...


@dataclass(frozen=True)
class Message:
    id: str
    text: str
    received: date
    channel: str  # chat | email


@dataclass
class Read:
    """What the model read from a (redacted) message."""

    intent: str
    slots: dict
    confidence: float
    input_tokens: int
    output_tokens: int
    latency_ms: float


@dataclass
class Outcome:
    kind: str  # e.g. accept_reading, offer_plan, escalate_priority, ask_identity, refuse
    params: dict = field(default_factory=dict)
    reason: str = ""

    @property
    def escalated(self) -> bool:
        return self.kind.startswith("escalate") or self.kind.startswith("review")


ACTIONS = {
    "accept_reading",
    "change_instalment",
    "offer_plan",
    "switch_tariff",
    "register_move",
    "register_cancellation",
}  # outcomes that change something in the customer's account
