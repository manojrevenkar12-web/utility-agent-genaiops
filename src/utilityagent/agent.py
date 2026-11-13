"""The agent. Two designs share the tools and the model:

- guarded: personal data out, the model reads intent and slots, code checks identity and applies the rules,
  replies are written from the decision, doubtful reads go to a person;
- prompt_only: the model gets the raw message and the rules in its prompt and decides itself (the common first
  version, kept here to measure against)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from opentelemetry.trace import Tracer

from . import policy
from .domain import NEEDS_IDENTITY, Accounts, Message, Outcome, Read
from .knowledge import Knowledge
from .model import Model, Release, cost_eur
from .redact import redact
from .replies import reply


class ActingModel(Protocol):
    """A model given tools and the rules in its prompt, which decides the outcome itself."""

    def act(self, message: Message, release: Release) -> tuple[Outcome, Read]: ...


@dataclass
class Result:
    message_id: str
    design: str
    release: str
    outcome: Outcome
    read: Read
    cost_eur: float
    model_input: str  # exactly what the model received
    reply: str


def _number(x) -> float | None:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def _date(x) -> date | None:
    try:
        return None if not x else date.fromisoformat(str(x))
    except ValueError:
        return None


class Agent:
    def __init__(
        self,
        accounts: Accounts,
        knowledge: Knowledge,
        model: Model,
        release: Release,
        settings: dict,
        prices: dict,
        tracer: Tracer,
        design: str = "guarded",
        acting: ActingModel | None = None,
    ):
        self.accounts, self.kb, self.model, self.release = accounts, knowledge, model, release
        self.p, self.prices, self.tracer, self.design, self.acting = settings, prices, tracer, design, acting

    def handle(self, msg: Message) -> Result:
        with self.tracer.start_as_current_span("conversation") as span:
            if self.design == "prompt_only":
                outcome, read = self.acting.act(msg, self.release)
                model_input = msg.text
            else:
                red = redact(msg.text)
                model_input = red.text
                read = self.model.read(msg.id, red.text, self.release)
                outcome = self._decide(msg, red, read)
                for label, n in red.masked.items():
                    span.set_attribute(f"pii.masked.{label.lower()}", n)
            cost = cost_eur(read, self.release.model, self.prices)
            span.set_attributes(
                {
                    "agent.design": self.design,
                    "agent.release": self.release.name,
                    "agent.channel": msg.channel,
                    "model.name": self.release.model,
                    "model.intent": read.intent,
                    "model.confidence": round(read.confidence, 3),
                    "model.input_tokens": read.input_tokens,
                    "model.output_tokens": read.output_tokens,
                    "model.latency_ms": round(read.latency_ms, 1),
                    "agent.outcome": outcome.kind,
                    "agent.escalated": outcome.escalated,
                    "agent.reason": outcome.reason[:120],
                    "cost.eur": round(cost, 6),
                }
            )
            return Result(
                msg.id, self.design, self.release.name, outcome, read, cost, model_input, reply(outcome, msg.text)
            )

    def _decide(self, msg: Message, red, read: Read) -> Outcome:
        rules = self.p
        if read.input_tokens + read.output_tokens > rules["agent"]["max_tokens_per_conversation"]:
            return Outcome("escalate", reason="token budget exceeded")
        if read.intent == "other":
            return Outcome("escalate", reason="not understood")
        if read.confidence < self.release.threshold:
            return Outcome("escalate", reason=f"low confidence ({read.confidence:.2f})")
        if read.intent == "outage":
            return Outcome("redirect_grid", reason="grid operator's job")
        if read.intent == "faq":
            questions = [q.strip() + "?" for q in red.text.split("?")[:-1] if len(q.strip()) > 8]
            passage, score = self.kb.search(questions[0].split(".")[-1] if questions else red.text)
            if passage is None:
                return Outcome("escalate", reason=f"no passage answers this (best {score:.2f})")
            return Outcome(
                "answer_faq",
                {"passage": passage.id, "answer": passage.text.split(". ")[0] + "."},
                f"passage {passage.id}",
            )
        if read.intent in NEEDS_IDENTITY:
            account = self.accounts.get(red.identity) if red.identity else None
            if account is None or red.postcode is None or account.postcode != red.postcode:
                return Outcome("ask_identity", reason="identity not confirmed")
            asked = read.slots.get("requested_customer")
            if asked and red.customers.get(asked, asked) != account.customer_no:
                return Outcome("refuse", reason="asked about another customer's account")
            s = read.slots
            today = msg.received
            if read.intent == "meter_reading":
                return policy.meter_reading(account, _number(s.get("reading")), today, rules["meter_reading"])
            if read.intent == "instalment_change":
                return policy.instalment_change(account, _number(s.get("amount")), rules["instalment"])
            if read.intent == "payment_plan":
                return policy.payment_plan(account, rules["payment_plan"])
            if read.intent == "bill_explanation":
                return policy.bill_explanation(account)
            if read.intent == "tariff_switch":
                return policy.tariff_switch(account, self.accounts, s.get("tariff"), today)
            if read.intent == "move_out":
                return policy.move_out(_date(s.get("date")))
            if read.intent == "cancellation":
                return policy.cancellation(account, today, rules["cancellation"])
            if read.intent == "account_info":
                return policy.account_info(account)
        return Outcome("escalate", reason="no rule for this intent")
