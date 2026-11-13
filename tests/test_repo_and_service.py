"""Repository invariants, the HTTP API, and the Azure OpenAI adapter."""

import json
import re
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from utilityagent.knowledge import Knowledge
from utilityagent.model import AzureOpenAIModel, Release
from utilityagent.offline import KeywordModel
from utilityagent.service.app import create_app
from utilityagent.telemetry import tracer

ROOT = Path(__file__).resolve().parents[1]


def test_only_the_evaluation_reads_the_world():
    for path in (ROOT / "src" / "utilityagent").rglob("*.py"):
        text = path.read_text()
        if "world" in path.parts:
            assert "policy.toml" not in text and "releases.toml" not in text, path
            continue
        assert not re.search(r"(from|import)\s+[.\w]*world", text), f"{path} imports the world"


def test_api_answers_from_the_offline_reader(cfg, world):
    import utilityagent.service.main as main_mod

    accounts = main_mod.FileAccounts(ROOT / "examples" / "accounts.json")
    acct = next(iter(accounts.accounts.values()))
    app = create_app(
        accounts,
        Knowledge.load(ROOT / "config" / "knowledge.toml"),
        KeywordModel(),
        Release(**json.loads((ROOT / "config" / "release.json").read_text())),
        cfg,
        tracer(),
    )
    c = TestClient(app)
    assert c.get("/healthz").json()["ok"]
    r = c.post(
        "/v1/messages",
        json={
            "id": "1",
            "text": f"Kundennummer {acct.customer_no}, PLZ {acct.postcode}. "
            "Wie hoch ist mein aktueller Abschlag und was ist noch offen?",
        },
    ).json()
    assert r["outcome"] == "give_account_info" and acct.customer_no not in r["reply"]
    assert (
        c.post("/v1/messages", json={"id": "2", "text": "Bei uns ist der Strom weg!"}).json()["outcome"]
        == "redirect_grid"
    )
    assert c.post("/v1/messages", json={"id": "3", "text": "x", "channel": "fax"}).status_code == 422


def test_azure_openai_adapter_calls_the_deployment_and_parses_json():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"} and body["temperature"] == 0
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"intent": "meter_reading", "slots": {"reading": 41917}, "confidence": 0.93}
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 812, "completion_tokens": 41},
            },
        )

    m = AzureOpenAIModel(
        "https://example.openai.azure.com/", "key", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    read = m.read("1", "Zählerstand 41.917", Release("r", "large-2025", "v4", False, 0.6))
    assert "/openai/deployments/large-2025/chat/completions" in seen["url"]
    assert (read.intent, read.slots["reading"], read.input_tokens) == ("meter_reading", 41917, 812)


def test_alert_thresholds_in_terraform_match_the_config(cfg):
    tf = (ROOT / "infra" / "terraform" / "main.tf").read_text()
    thresholds = [float(x) for x in re.findall(r"threshold\s*=\s*([\d.]+)", tf)]
    assert thresholds == [cfg["alerts"]["handed_to_people_share"], cfg["alerts"]["eur_per_conversation"]]
    assert cfg["alerts"]["eur_per_conversation"] == cfg["releases"]["gate"]["max_eur_per_conversation"]
