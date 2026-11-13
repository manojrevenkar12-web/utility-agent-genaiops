"""HTTP API in front of the agent. Replies and decisions go back; personal data is never echoed or logged."""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from opentelemetry.trace import Tracer
from pydantic import BaseModel, Field

from ..agent import Agent
from ..domain import Accounts, Message
from ..knowledge import Knowledge
from ..model import Model, Release


class MessageIn(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=5000)
    channel: str = Field(default="chat", pattern="^(chat|email)$")
    received: date | None = None


def create_app(
    accounts: Accounts, knowledge: Knowledge, model: Model, release: Release, settings: dict, tracer: Tracer
) -> FastAPI:
    app = FastAPI(title="utility-agent-genaiops", version="1.0.0")
    agent = Agent(accounts, knowledge, model, release, settings, settings["prices"], tracer)

    @app.get("/healthz")
    def health() -> dict:
        return {"ok": True, "release": release.name, "model": release.model}

    @app.post("/v1/messages")
    def handle(m: MessageIn) -> dict:
        r = agent.handle(Message(m.id, m.text, m.received or date.today(), m.channel))
        return {
            "id": m.id,
            "reply": r.reply,
            "outcome": r.outcome.kind,
            "handed_to_a_person": r.outcome.escalated,
            "reason": r.outcome.reason,
            "release": r.release,
            "cost_eur": round(r.cost_eur, 6),
        }

    return app
