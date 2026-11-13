"""Container entry point. With AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY set the agent reads with Azure OpenAI;
without them it uses the offline keyword reader. Accounts come from ACCOUNTS_PATH (an export for local runs)."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from .. import settings as settings_mod
from ..domain import Account
from ..knowledge import Knowledge
from ..model import AzureOpenAIModel, Release
from ..offline import KeywordModel
from ..telemetry import tracer
from .app import create_app

ROOT = settings_mod.ROOT


class FileAccounts:
    def __init__(self, path: Path):
        raw = json.loads(path.read_text())
        self.accounts = {}
        for a in raw["accounts"]:
            a["fixed_until"] = date.fromisoformat(a["fixed_until"]) if a["fixed_until"] else None
            a["last_reading_date"] = date.fromisoformat(a["last_reading_date"])
            self.accounts[a["customer_no"]] = Account(**a)
        self.tariffs = raw["tariffs"]

    def get(self, customer_no: str) -> Account | None:
        return self.accounts.get(customer_no)

    def tariffs_for(self, postcode: str, commodity: str) -> list[str]:
        return self.tariffs[commodity]


cfg = settings_mod.load()
endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
model = AzureOpenAIModel(endpoint, os.environ["AZURE_OPENAI_API_KEY"]) if endpoint else KeywordModel()
release = Release(**json.loads((ROOT / "config" / "release.json").read_text()))
app = create_app(
    FileAccounts(Path(os.environ.get("ACCOUNTS_PATH", ROOT / "examples" / "accounts.json"))),
    Knowledge.load(ROOT / "config" / "knowledge.toml"),
    model,
    release,
    cfg,
    tracer(),
)
