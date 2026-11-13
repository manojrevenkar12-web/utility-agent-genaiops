# Working on utility-agent-genaiops

## Fast feedback

```bash
python -m pytest -q                       # redaction, rules, agent, traces, gate, API, adapter (~1 s)
ruff check src tests scripts && ruff format --check src tests scripts
python3 scripts/evaluate.py               # dev world and the release experiment (~15 s); writes reports/dev.json
python3 scripts/readme.py && python3 scripts/handover.py
git diff --exit-code README.md docs/RUNBOOK.md web/public/data/console.json
cd web && npm test && npm run build
```

## Invariants

1. **The truth stays in the world.** `src/utilityagent/world/` knows what each customer meant and what the right
   handling is. Only `scripts/evaluate.py` and the tests read it; nothing else under `src/utilityagent` imports it.
2. **The world does not read the agent's settings.** `config/world.toml` drives the world; `config/policy.toml`,
   `releases.toml`, `models.toml` and `knowledge.toml` drive the agent.
3. **The model reads; code decides.** The model returns intent, slots and a confidence. Identity, the utility's
   rules and every change to an account are code. Replies are written from the decision, never by the model.
4. **Personal data out first.** Nothing reaches the model before `redact()`; spans carry decisions, tokens and
   cost, never message text.
5. **Every release through the gate.** A change to model, prompt, examples or threshold is a release in
   `config/releases.toml` and ships only if the gate passes on the golden set.
6. **Same luck for every release.** The simulated model draws its mistakes per message, so two releases differ
   only where their error rates differ.
7. **Settings in config; documents generated.** `reports/dev.json`, `config/release.json` and
   `examples/accounts.json` by `scripts/evaluate.py`; README results and console data by `scripts/readme.py`;
   `docs/RUNBOOK.md` by `scripts/handover.py`.

## The held-out rule

`python3 scripts/evaluate.py --heldout` runs the held-out world once, with the release the dev gate ended on, and
writes `config/heldout.lock`. After that, changes are measured on the dev world only, and the held-out numbers stay
as they first came out.
