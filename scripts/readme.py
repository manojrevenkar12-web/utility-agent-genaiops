"""Write README.md and the console data from reports/*.json. Never edit the results by hand."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/manojrevenkar12-web/utility-agent-genaiops"


def table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] + ["--:"] * (len(head) - 1)) + "|"]
    return "\n".join(out + ["| " + " | ".join(r) + " |" for r in rows])


def eur(x: float) -> str:
    return f"€{x:,.0f}"


def designs_table(r: dict) -> str:
    names = {"prompt_only": "Model decides (rules in the prompt)", "guarded": "Model reads, code decides"}
    rows = []
    for k, v in r["designs"].items():
        pd = v["personal_data"]
        rows.append(
            [
                names[k],
                f"{v['right']}%",
                f"{v['harmful_per_1k']:g}",
                f"{v['contained']}%",
                f"€{v['eur_per_conversation']:.4f}",
                f"{pd['sent_to_the_model']:,} of {pd['messages_with_personal_data']:,}",
            ]
        )
    return table(
        [
            "Design",
            "Handled right",
            "Harmful actions per 1,000",
            "Without a person",
            "Model cost per chat",
            "Messages with personal data sent to the model",
        ],
        rows,
    )


def releases_table(r: dict) -> str:
    def cell(step: dict) -> str:
        if step["decision"] == "shipped":
            return "**shipped, a regression**" if step["truly_worse"] else "shipped"
        return f"blocked ({'a real regression' if step['truly_worse'] else 'an improvement'}): {step['why']}"

    demo, gate = r["releases"]["demo"]["steps"], r["releases"]["gate"]["steps"]
    rows = [[d["release"], cell(d), cell(g)] for d, g in zip(demo[1:], gate[1:], strict=True)]
    return table(["Candidate", "Demo of 10 chats", "Gate on the golden set"], rows)


def process_table(r: dict) -> str:
    rows = []
    for k, label in (("demo", "Ship if the demo chats look right"), ("gate", "Ship through the gate")):
        v = r["releases"][k]
        f = v["final"]
        rows.append(
            [
                label,
                str(v["regressions_shipped"]),
                str(v["improvements_blocked"]),
                f"{v['harmful_actions_over_releases']:,}",
                f"{f['right']}%",
                f"{f['harmful_per_1k']:g}",
                f"€{f['eur_per_conversation']:.4f}",
            ]
        )
    return table(
        [
            "Release process",
            "Regressions shipped",
            "Improvements blocked",
            "Harmful actions customers met",
            "Handled right at the end",
            "Harmful per 1,000 at the end",
            "Cost per chat at the end",
        ],
        rows,
    )


def main() -> None:
    dev = json.loads((ROOT / "reports" / "dev.json").read_text())
    hp = ROOT / "reports" / "heldout.json"
    held = json.loads(hp.read_text()) if hp.exists() else None
    g, p = dev["designs"]["guarded"], dev["designs"]["prompt_only"]
    bc = dev["business_case"]["guarded"]
    rel = dev["releases"]
    final = rel["gate"]["final_release"]
    n = dev["counts"]
    amb = dev["ambiguous_english_dates"]
    budget = tomllib.loads((ROOT / "config" / "releases.toml").read_text())["gate"]["max_eur_per_conversation"]
    if held:
        hg, hpo = held["designs"]["guarded"], held["designs"]["prompt_only"]
        hr = held["releases"]
        heldout = f"""## Held-out world (run once)

Other customers, {round(100 * held["german_share"])} % German, more typos and mixed questions, injection attempts,
and phrasings, signatures and identifier formats nobody wrote rules for. It ran once, with the release the dev gate
ended on and nothing changed after (`config/heldout.lock`).

{designs_table(held)}

{process_table(held)}

On held-out customers the guarded agent handled {hg["right"]}% right with {hg["harmful_per_1k"]:g} harmful actions
per 1,000 (model decides: {hpo["right"]}% and {hpo["harmful_per_1k"]:g}). Redaction let personal data through in
{hg["personal_data"]["sent_to_the_model"]} of {hg["personal_data"]["messages_with_personal_data"]:,} messages that
held some. Every one of those was a signature name under a closing the redactor did not know ("Gruß", "Cheers",
a misspelt "Mit freundlichen Grüßen"); IBANs, phone numbers, e-mail addresses and birth dates were all masked.
Signature detection has been widened since, with a test; the held-out numbers above are as they first came out.
The same candidates through the same two processes: the demo shipped
{hr["demo"]["regressions_shipped"]} regressions, the gate {hr["gate"]["regressions_shipped"]}.
"""
    else:
        heldout = "## Held-out world\n\nNot run yet: `python3 scripts/evaluate.py --heldout` (once).\n"

    readme = f"""# utility-agent-genaiops

**A customer-service agent for an energy utility, run the GenAIOps way on Azure: evaluated before every release,
traced, costed per conversation, and handed over with a runbook.**

Customers of a German energy supplier write in about meter readings, monthly instalments (Abschlag), payment plans,
high bills, tariff switches, moves and cancellations, in German and English, with typos, IBANs and phone numbers in
the text. The agent answers what it may, changes what the rules allow, and hands everything else to a person.
Building it is the smaller part. This repository is about running it: what decides a release, what the traces
show, what a conversation costs, and what the team that takes it over needs.

![Console](docs/console.png)

## Results

Dev world: {n["traffic"]:,} production messages, {round(100 * dev["german_share"])} % German, a golden set of
{n["golden"]} messages labelled with the right outcome, and the 10 happy-path chats a team would show in a demo.
Every number below is written by `scripts/evaluate.py` into `reports/dev.json` and copied here by
`scripts/readme.py`; CI regenerates both and fails on any difference.

| | Model decides | Model reads, code decides |
|---|--:|--:|
| Harmful actions per 1,000 messages | {p["harmful_per_1k"]:g} | **{g["harmful_per_1k"]:g}** |
| Handled right | {p["right"]}% | **{g["right"]}%** |
| Messages with personal data sent to the model | {p["personal_data"]["sent_to_the_model"]:,} \
| **{g["personal_data"]["sent_to_the_model"]}** |
| Model cost per conversation | €{p["eur_per_conversation"]:.4f} | **€{g["eur_per_conversation"]:.4f}** |

| | Ship if the demo looks right | Ship through the gate |
|---|--:|--:|
| Regressions shipped (of 8 candidates) | {rel["demo"]["regressions_shipped"]} \
| **{rel["gate"]["regressions_shipped"]}** |
| Harmful actions customers met over the 8 releases | {rel["demo"]["harmful_actions_over_releases"]:,} \
| **{rel["gate"]["harmful_actions_over_releases"]:,}** |

### Model reads, code decides

A harmful action is a wrong change to an account (an implausible meter reading accepted, an instalment set below
the floor, a payment plan outside the rules, a wrong cancellation date), account data given to someone who is not
identified, or a customer facing a supply interruption not handed to a person the same day.

{designs_table(dev)}

When the model decides, it gets the raw message and the rules in its prompt: {p["harmful_per_1k"]:g} harmful actions
per 1,000 messages and every IBAN and phone number in its context. In the guarded design the code takes personal
data out first (customer numbers and postcodes become placeholders the code maps back; IBAN, e-mail, phone, birth
date and signature names become masks), the model returns intent, slots and a confidence, and code checks identity
and applies the rules. Replies are written from the decision, so no model writes a number. Readings below 0.6
confidence go to a person.

### Releases: a gate, not a demo

Eight candidate changes arrive one after another: a prompt fix for German number formats, a cheaper model, a lower
handover threshold, few-shot examples, a new model, a date-format fix, the new model again, a shorter prompt. Each
is judged two ways, starting from the same production release with the same customers and the same model luck:
by the 10 demo chats, and by the gate, which runs the {n["golden"]}-message golden set against production and
ships only if a paired bootstrap shows no drop of more than half a point in messages handled right, no extra
harmful action, and a model cost under €{budget:.3f} per conversation.

{releases_table(dev)}

{process_table(dev)}

The gate missed one: the new model reads "03/04/2027" in English messages as the 4th of March. The golden set,
drawn from the traffic mix, held {amb["golden"]} such dates (production traffic {amb["traffic"]}), so the gate
could not see it; the date-format prompt fixed it one release later. The fix for the process is a golden set
stratified by risk, not by traffic share.

### Cost and the business case

At the release in production after the gate ({final["model"]}, prompt {final["prompt"]}, few-shot examples
{"on" if final["few_shot"] else "off"}), a conversation costs €{g["eur_per_conversation"]:.4f} in model tokens.
With the assumptions in `config/policy.toml` ({bc["monthly_contacts"]:,} contacts a month, €5.20 for a contact a
person handles), the agent handles {bc["handled_by_the_agent"]:,} contacts a month right without a person: about
{eur(bc["eur_saved_per_month"])} a month for {eur(bc["model_eur_per_month"])} of model cost, with
{bc["harmful_actions_per_month"]} harmful actions a month to catch in review. The contact cost is an assumption to
replace with the customer's own figure in the first workshop.

{heldout}
## How it works

```mermaid
flowchart LR
  M[Message: chat or e-mail] --> R[Redact: placeholders for identifiers, masks for personal data]
  R --> L[Azure OpenAI: intent, slots, confidence]
  L --> C{{Code: identity, rules, confidence}}
  A[(Billing system API)] --> C
  K[(Service passages in Azure AI Search)] --> C
  C -- allowed --> X[Change the account and reply from the facts]
  C -- doubtful or sensitive --> H[Person, with the reason]
  C -. spans: outcome, tokens, cost .-> T[Application Insights]
```

- `src/utilityagent/redact.py`, `policy.py`, `agent.py`: redaction, the utility's rules, the two designs.
- `src/utilityagent/evals.py`: golden-set scoring, harmful-action definition, the release gate.
- `src/utilityagent/telemetry.py`: OpenTelemetry; Application Insights when its connection string is set.
- `src/utilityagent/model.py`: the Azure OpenAI adapter (JSON output, deployments per model) and cost accounting.
- `src/utilityagent/service/`: FastAPI, `POST /v1/messages`; the offline keyword reader for local runs.
- `src/utilityagent/world/`: customers, messages, the truth, and a model whose mistakes depend on the release.
  Only the evaluation and the tests read it.
- `infra/terraform/`: Azure Container Apps, Azure OpenAI deployments, Azure AI Search, Key Vault with a managed
  identity, Log Analytics and Application Insights, alerts. Validated in CI, not applied.
- `docs/RUNBOOK.md`: the handover: what runs where, the alerts, how to roll back, how to ship a release.
- `web/`: the console (React, Framer Motion) reading `web/public/data/console.json`.

## Run it

```bash
pip install -e '.[dev]'
python -m pytest -q                        # about 1 s
python3 scripts/evaluate.py                # dev world and the release experiment, about 15 s
python3 scripts/readme.py && python3 scripts/handover.py
uvicorn utilityagent.service.main:app      # offline reader; set AZURE_OPENAI_ENDPOINT and _API_KEY for the model
cd web && npm ci && npm run dev
```

## Limits

- The customers, the billing system and the model are simulated. The model's error rates per release are set in
  `config/world.toml`; a real model fails in more ways, so the gate's thresholds have to be tuned on real labels.
- The Azure OpenAI adapter is tested against a mock, not a live deployment; the Terraform is validated, not applied.
- The offline keyword reader exists so the API runs without a model; it is not measured.
- The business case uses assumed contact volumes and costs.
"""
    (ROOT / "README.md").write_text(readme)

    console = {
        "generated_from": "reports/dev.json" + (" and reports/heldout.json" if held else ""),
        "counts": n,
        "german_share": dev["german_share"],
        "designs": dev["designs"],
        "business_case": dev["business_case"],
        "releases": {
            k: {
                "steps": v["steps"],
                "regressions_shipped": v["regressions_shipped"],
                "harmful_actions_over_releases": v["harmful_actions_over_releases"],
            }
            for k, v in rel.items()
        },
        "examples": dev["examples"],
        "heldout": None
        if not held
        else {
            "guarded": held["designs"]["guarded"],
            "prompt_only": held["designs"]["prompt_only"],
            "demo_regressions": held["releases"]["demo"]["regressions_shipped"],
            "gate_regressions": held["releases"]["gate"]["regressions_shipped"],
        },
    }
    out = ROOT / "web" / "public" / "data" / "console.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(console, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
