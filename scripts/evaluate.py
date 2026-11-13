"""Measure the agent designs and the two ways of shipping releases against the world's truth.

python3 scripts/evaluate.py            dev world: reports/dev.json
python3 scripts/evaluate.py --heldout  held-out world, once, with the release the dev gate ended on (writes the lock)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from utilityagent import settings as settings_mod  # noqa: E402
from utilityagent.agent import Agent  # noqa: E402
from utilityagent.evals import Scores, gate, matches  # noqa: E402
from utilityagent.knowledge import Knowledge  # noqa: E402
from utilityagent.model import Release  # noqa: E402
from utilityagent.telemetry import tracer  # noqa: E402
from utilityagent.world.sim import World  # noqa: E402


def run(world, kb, cfg, release, design, messages, exporter=None):
    model = world.model()
    agent = Agent(world, kb, model, release, cfg, cfg["prices"], tracer(exporter), design=design, acting=model)
    return [agent.handle(m) for m in messages]


def truth_scores(world, results, messages) -> Scores:
    return Scores.of(results, [world.truth(m.id).expected for m in messages])


def pii_leaks(world, results) -> dict:
    with_pii = [r for r in results if world.truth(r.message_id).pii]
    leaked = [r for r in with_pii if any(p in r.model_input for p in world.truth(r.message_id).pii)]
    return {"messages_with_personal_data": len(with_pii), "sent_to_the_model": len(leaked)}


def span_leaks(world, exporter, messages) -> int:
    values = {p for m in messages for p in world.truth(m.id).pii}
    text = json.dumps([dict(s.attributes) for s in exporter.get_finished_spans()], ensure_ascii=False)
    return sum(1 for v in values if v in text)


def design_report(world, kb, cfg, release, split) -> dict:
    msgs = world.messages[split]
    out = {}
    for design in ("prompt_only", "guarded"):
        exp = InMemorySpanExporter()
        res = run(world, kb, cfg, release, design, msgs, exp)
        sc = truth_scores(world, res, msgs)
        lat = np.array([r.read.latency_ms for r in res])
        right_contained = np.mean(
            [matches(r.outcome, world.truth(r.message_id).expected) and not r.outcome.escalated for r in res]
        )
        out[design] = {
            **sc.summary(),
            "right_and_contained": round(100 * right_contained, 2),
            "p95_model_latency_ms": round(float(np.quantile(lat, 0.95))),
            "personal_data": pii_leaks(world, res),
            "personal_data_in_traces": span_leaks(world, exp, msgs),
            "spans": len(exp.get_finished_spans()),
        }
    return out


def release_experiment(world, kb, cfg) -> dict:
    rel = cfg["releases"]
    start = Release(**rel["production"])
    golden = world.messages["golden"]
    demo = world.messages["demo"]
    traffic = world.messages["traffic"]
    cache: dict = {}

    def scores(release: Release, split: str, msgs) -> Scores:
        key = (release.model, release.prompt, release.few_shot, release.threshold, split)
        if key not in cache:
            cache[key] = truth_scores(world, run(world, kb, cfg, release, "guarded", msgs), msgs)
        return cache[key]

    out = {}
    for process in ("demo", "gate"):
        prod = start
        steps = [
            {"release": prod.name, "decision": "in production", "why": "", **scores(prod, "traffic", traffic).summary()}
        ]
        for c in rel["candidate"]:
            cand = prod.patched(c["name"], **c["changes"])
            if process == "demo":
                ok = bool(scores(cand, "demo", demo).right.all())
                why = "every demo chat handled right" if ok else "a demo chat went wrong"
            else:
                d = gate(scores(prod, "golden", golden), scores(cand, "golden", golden), rel["gate"], c["name"])
                ok, why = d.ship, "; ".join(d.reasons)
            truth_prod, truth_cand = scores(prod, "traffic", traffic), scores(cand, "traffic", traffic)
            regression = (
                truth_cand.right.mean() < truth_prod.right.mean() - 0.002
                or truth_cand.harm.sum() > truth_prod.harm.sum()
            )
            if ok:
                prod = cand
            steps.append(
                {
                    "release": c["name"],
                    "decision": "shipped" if ok else "blocked",
                    "why": why,
                    "truly_worse": bool(regression),
                    **scores(prod, "traffic", traffic).summary(),
                }
            )
        final = scores(prod, "traffic", traffic)
        out[process] = {
            "steps": steps,
            "final_release": prod.__dict__,
            "regressions_shipped": sum(s.get("truly_worse", False) and s["decision"] == "shipped" for s in steps),
            "improvements_blocked": sum((not s.get("truly_worse", True)) and s["decision"] == "blocked" for s in steps),
            "final": final.summary(),
        }
        # harmful actions customers met over the whole sequence: production after each step, on that step's traffic
        out[process]["harmful_actions_over_releases"] = int(
            round(sum(s["harmful_per_1k"] * len(traffic) / 1000 for s in steps[1:]))
        )
    return out


def business_case(cfg, summary: dict) -> dict:
    c = cfg["cost"]
    contacts = c["monthly_contacts"]
    handled = contacts * summary["right_and_contained"] / 100
    ai = contacts * summary["eur_per_conversation"]
    return {
        "monthly_contacts": contacts,
        "handled_by_the_agent": round(handled),
        "eur_saved_per_month": round(handled * c["eur_per_human_contact"] - ai),
        "model_eur_per_month": round(ai, 2),
        "harmful_actions_per_month": round(contacts * summary["harmful_per_1k"] / 1000),
    }


def examples(world, kb, cfg, release) -> list[dict]:
    msgs = world.messages["golden"][:80]
    res = run(world, kb, cfg, release, "guarded", msgs)
    picked, seen = [], set()
    for m, r in zip(msgs, res, strict=True):
        t = world.truth(m.id)
        key = (t.lang, r.outcome.kind)
        if key in seen or len(picked) >= 6 or "\n" not in m.text:
            continue
        seen.add(key)
        picked.append(
            {
                "id": m.id,
                "channel": m.channel,
                "lang": t.lang,
                "text": m.text,
                "model_saw": r.model_input,
                "intent": r.read.intent,
                "confidence": round(r.read.confidence, 2),
                "outcome": r.outcome.kind,
                "reason": r.outcome.reason,
                "reply": r.reply,
                "right": matches(r.outcome, t.expected),
                "cost_eur": round(r.cost_eur, 5),
            }
        )
    return picked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heldout", action="store_true")
    args = ap.parse_args()
    lock = ROOT / "config" / "heldout.lock"
    if args.heldout and lock.exists():
        sys.exit(f"the held-out world already ran ({lock.read_text().strip()}); see AGENTS.md")
    cfg = settings_mod.load()
    kb = Knowledge.load(ROOT / "config" / "knowledge.toml")
    report: dict = {"world": "heldout" if args.heldout else "dev"}
    if args.heldout:
        dev = json.loads((ROOT / "reports" / "dev.json").read_text())
        release = Release(**dev["releases"]["gate"]["final_release"])
        world = World.load(ROOT / "config" / "heldout.toml")
        report["releases"] = release_experiment(world, kb, cfg)  # the same candidates, other customers
    else:
        world = World.load(ROOT / "config" / "world.toml")
        report["releases"] = release_experiment(world, kb, cfg)
        release = Release(**report["releases"]["gate"]["final_release"])
        (ROOT / "config" / "release.json").write_text(json.dumps(release.__dict__, indent=1) + "\n")
        export = [
            {
                **a.__dict__,
                "fixed_until": a.fixed_until.isoformat() if a.fixed_until else None,
                "last_reading_date": a.last_reading_date.isoformat(),
            }
            for a in list(world.accounts.values())[:200]
        ]
        (ROOT / "examples").mkdir(exist_ok=True)
        (ROOT / "examples" / "accounts.json").write_text(
            json.dumps(
                {
                    "note": "synthetic accounts from the dev world, for local runs of the API",
                    "accounts": export,
                    "tariffs": {
                        "electricity": ["Grundversorgung", "Flex", "Fix24", "Oeko12"],
                        "gas": ["Grundversorgung", "Flex", "Fix24"],
                    },
                },
                indent=1,
            )
            + "\n"
        )
    report["release_measured"] = release.__dict__
    report["counts"] = {s: len(m) for s, m in world.messages.items()}
    report["ambiguous_english_dates"] = {
        s: sum(bool(world.truth(m.id).hard.get("en_date_ambiguous")) for m in msgs)
        for s, msgs in world.messages.items()
    }
    report["german_share"] = round(np.mean([world.truth(m.id).lang == "de" for m in world.messages["traffic"]]), 3)
    report["designs"] = design_report(world, kb, cfg, release, "traffic")
    report["business_case"] = {d: business_case(cfg, report["designs"][d]) for d in report["designs"]}
    report["examples"] = examples(world, kb, cfg, release)
    out = ROOT / "reports" / ("heldout.json" if args.heldout else "dev.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str) + "\n")
    if args.heldout:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        lock.write_text(f"ran at commit {commit or 'uncommitted'}\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("examples",)}, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
