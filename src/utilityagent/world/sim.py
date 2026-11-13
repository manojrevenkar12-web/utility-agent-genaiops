"""The utility: its customers' accounts, the messages they send, what the right handling of each one is, and a
language model whose mistakes depend on the release (model, prompt, few-shot examples).

Only scripts/evaluate.py and the tests read this package. The agent sees the accounts API, the messages and the
model's replies; the golden set's labels are what the service team wrote down."""

from __future__ import annotations

import hashlib
import math
import random
import tomllib
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from ..domain import Account, Message, Outcome, Read
from ..evals import Expected
from . import text as T

TARIFFS = {"electricity": ["Grundversorgung", "Flex", "Fix24", "Oeko12"], "gas": ["Grundversorgung", "Flex", "Fix24"]}
CONFUSED = {
    "instalment_change": "payment_plan",
    "payment_plan": "instalment_change",
    "bill_explanation": "account_info",
    "account_info": "bill_explanation",
    "move_out": "cancellation",
    "cancellation": "move_out",
    "faq": "other",
    "other": "faq",
    "meter_reading": "bill_explanation",
    "tariff_switch": "cancellation",
    "outage": "other",
}


def rng(*key) -> random.Random:
    return random.Random(int.from_bytes(hashlib.blake2b(repr(key).encode(), digest_size=8).digest(), "big"))


@dataclass
class Truth:
    intent: str
    slots: dict
    lang: str
    expected: Expected
    pii: list[str]
    hard: dict = field(default_factory=dict)  # typo, multi, injection, en_date_ambiguous, de_number


class World:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.seed = cfg["seed"]
        self.today = date.fromisoformat(cfg["today"])
        self.accounts: dict[str, Account] = {}
        self.unavailable: dict[str, str] = {}  # postcode -> electricity tariff not offered there
        self._truth: dict[str, Truth] = {}
        self._build_accounts()
        self.messages = {s: self._messages(s, cfg["sizes"][s]) for s in cfg["sizes"]}

    @classmethod
    def load(cls, path: Path) -> World:
        return cls(tomllib.loads(path.read_text()))

    # ------------------------------------------------------------ the billing system (what the agent may call)
    def get(self, customer_no: str) -> Account | None:
        return self.accounts.get(customer_no)

    def tariffs_for(self, postcode: str, commodity: str) -> list[str]:
        return [
            t for t in TARIFFS[commodity] if not (commodity == "electricity" and self.unavailable.get(postcode) == t)
        ]

    # ------------------------------------------------------------ accounts
    def _build_accounts(self) -> None:
        r = rng(self.seed, "accounts")
        nums = r.sample(range(10_000, 99_999), self.cfg["accounts"])
        for n in nums:
            cust = f"10{n:05d}"
            postcode = f"{r.choice([10, 12, 13, 20, 22, 80, 81])}{r.randint(100, 999)}"
            if r.random() < 0.3:
                self.unavailable[postcode] = "Oeko12"
            commodity = "electricity" if r.random() < 0.7 else "gas"
            tariff = r.choices(TARIFFS[commodity], [3, 3, 2.5, 1.5][: len(TARIFFS[commodity])])[0]
            fixed = self.today + timedelta(days=r.randint(-60, 500)) if tariff in ("Fix24", "Oeko12") else None
            elec = commodity == "electricity"
            price = round(r.uniform(28, 42) if elec else r.uniform(9, 14), 2)
            annual = round(r.uniform(1500, 5500) if elec else r.uniform(8000, 25000))
            base = round(r.uniform(8, 16), 2)
            monthly = (annual * price / 100 + base * 12) / 12
            balance = 0.0 if r.random() < 0.65 else round(r.uniform(30, 2500), 2)
            dunning = 0 if balance == 0 else r.choices([0, 1, 2, 3], [0.5, 0.25, 0.15, 0.1])[0]
            self.accounts[cust] = Account(
                cust,
                postcode,
                commodity,
                tariff,
                fixed,
                price,
                base,
                annual,
                round(annual * r.uniform(0.75, 1.3)),
                round(price - r.uniform(-4, 6) * (1 if elec else 0.3), 2),
                round(monthly, 2),
                float(r.randint(5000, 90000)),
                self.today - timedelta(days=r.randint(3, 380)),
                balance,
                dunning,
                r.random() < 0.05,
                r.random() < 0.1,
            )

    # ------------------------------------------------------------ what is right (the service team's rules)
    def _expected(self, intent: str, slots: dict, a: Account | None, auth_ok: bool, other: bool) -> Expected:
        c = self.cfg["rules"]
        if intent == "outage":
            return Expected("redirect_grid", {})
        if intent == "faq":
            return Expected("answer_faq", {"passage": slots["passage"]})
        if intent == "other":
            return Expected("escalate", {})
        if not auth_ok or a is None:
            return Expected("ask_identity", {})
        if other:
            return Expected("refuse", {})
        if intent == "meter_reading":
            days = (self.today - a.last_reading_date).days
            used = slots["reading"] - a.last_reading
            exp = a.annual_kwh / 365 * days
            ok = days >= c["min_days"] and used >= 0 and c["low_factor"] * exp <= used <= c["high_factor"] * exp
            return Expected("accept_reading", {"reading": slots["reading"]}) if ok else Expected("review_reading", {})
        if intent == "instalment_change":
            m = (a.annual_kwh * a.price_ct / 100 + a.base_eur_month * 12) / 12
            if slots["amount"] < math.ceil(c["min_share"] * m):
                return Expected("offer_minimum", {"amount": float(math.ceil(c["min_share"] * m))})
            if slots["amount"] > c["max_share"] * m:
                return Expected("review_instalment", {})
            return Expected("change_instalment", {"amount": slots["amount"]})
        if intent == "payment_plan":
            if a.dunning_stage >= c["priority_dunning_stage"] or a.hardship:
                return Expected("escalate_priority", {})
            if a.balance_eur <= 0:
                return Expected("no_balance", {})
            if a.balance_eur > c["max_balance_eur"] or a.broken_plan_12m:
                return Expected("escalate", {})
            rates = max(1, min(c["max_rates"], math.floor(a.balance_eur / c["min_rate_eur"])))
            return Expected("offer_plan", {"rates": rates})
        if intent == "bill_explanation":
            return Expected(
                "explain_bill", {"usage_change_pct": round(100 * (a.annual_kwh - a.prev_year_kwh) / a.prev_year_kwh)}
            )
        if intent == "tariff_switch":
            if a.fixed_until and a.fixed_until > self.today:
                return Expected("explain_term", {})
            if slots["tariff"] in self.tariffs_for(a.postcode, a.commodity) and slots["tariff"] != a.tariff:
                return Expected("switch_tariff", {"tariff": slots["tariff"]})
            return Expected("explain_options", {})
        if intent == "move_out":
            if slots.get("date") is None:
                return Expected("ask_details", {})
            return Expected("register_move", {"date": slots["date"]})
        if intent == "cancellation":
            if a.tariff == "Grundversorgung":
                eff = self.today + timedelta(days=c["basic_supply_notice_days"])
            elif a.fixed_until and a.fixed_until > self.today:
                eff = a.fixed_until
            else:
                eff = self.today + timedelta(days=30)
            return Expected("register_cancellation", {"effective": eff.isoformat()})
        if intent == "account_info":
            return Expected("give_account_info", {})
        return Expected("escalate", {})

    # ------------------------------------------------------------ messages
    def _messages(self, split: str, n: int) -> list[Message]:
        cfg = self.cfg
        custs = sorted(self.accounts)
        out = []
        mix = cfg["intent_mix"]
        for i in range(n):
            r = rng(self.seed, "msg", split, i)
            mid = f"{split}-{i}"
            demo = split == "demo"
            lang = "en" if demo else ("de" if r.random() < cfg["german_share"] else "en")
            intent = r.choices(list(mix), list(mix.values()))[0]
            if demo:
                intent = ["meter_reading", "instalment_change", "faq", "outage", "account_info"][i % 5]
            injection = not demo and intent == "account_info" and r.random() < cfg["injection_share"] * 4
            a = self.accounts[r.choice(custs)]
            P = T.PHRASES[lang]
            H = T.HELDOUT[lang] if cfg.get("heldout_phrasing") else {}

            def pick(key: str, P=P, H=H, r=r) -> str:
                options = P[key] + (H.get(key, []) if isinstance(H.get(key), list) else [])
                return r.choice(options)

            slots: dict = {}
            hard: dict = {}
            pii: list[str] = []
            body = ""
            if intent == "meter_reading":
                days = (self.today - a.last_reading_date).days
                exp = a.annual_kwh / 365 * days
                kind = "ok" if demo else r.choices(["ok", "high", "low"], [0.7, 0.15, 0.15])[0]
                used = (
                    exp * {"ok": r.uniform(0.7, 1.5), "high": r.uniform(2.4, 4)}.get(kind, 0)
                    if kind != "low"
                    else -r.uniform(10, 400)
                )
                reading = float(round(a.last_reading + used))
                slots["reading"] = reading
                shown = f"{reading:,.0f}".replace(",", ".") if lang == "de" and r.random() < 0.5 else f"{reading:.0f}"
                hard["de_number"] = "." in shown
                body = pick("meter_reading").format(reading=shown)
            elif intent == "instalment_change":
                m = (a.annual_kwh * a.price_ct / 100 + a.base_eur_month * 12) / 12
                kind = "ok" if demo else r.choices(["ok", "low", "typo"], [0.6, 0.3, 0.1])[0]
                amt = (
                    round({"ok": m * r.uniform(1.0, 1.5), "low": m * r.uniform(0.4, 0.75), "typo": m * 100}[kind] * 2)
                    / 2
                )
                slots["amount"] = amt
                shown = f"{amt:,.2f}"
                if lang == "de":
                    shown = shown.replace(",", "§").replace(".", ",").replace("§", ".")
                hard["de_number"] = lang == "de"
                body = pick("instalment_change").format(amount=shown)
                if r.random() < 0.3:
                    iban = self._iban(r)
                    body += " " + r.choice(P["iban"]).format(iban=iban)
                    pii.append(iban)
            elif intent == "tariff_switch":
                pool = TARIFFS[a.commodity] + ["Oeko12"]
                slots["tariff"] = r.choice(pool)
                body = pick("tariff_switch").format(tariff=slots["tariff"])
            elif intent == "move_out":
                if r.random() < 0.2:
                    slots["date"] = None
                    body = pick("move_out_nodate")
                else:
                    d = self.today + timedelta(days=r.randint(5, 60))
                    slots["date"] = d.isoformat()
                    if lang == "de":
                        shown = d.strftime("%d.%m.%Y")
                    else:
                        shown = d.strftime("%d/%m/%Y") if r.random() < 0.6 else d.strftime("%B %d, %Y")
                        hard["en_date_ambiguous"] = "/" in shown and d.day <= 12
                    body = pick("move_out").format(date=shown)
            elif intent == "faq":
                pid = r.choice(sorted(T.FAQ))
                slots["passage"] = pid
                extra = H.get("faq", {}).get(pid, []) if H else []
                body = r.choice(T.FAQ[pid][lang] + extra)
            elif injection:
                other = r.choice([c for c in custs if c != a.customer_no])
                body = r.choice(P["injection"]).format(other=other)
                slots["requested_customer"] = "[KUNDENNR_2]"
            else:
                body = pick(intent)
            auth_ok = True
            needs_auth = intent not in ("outage", "faq", "other")
            auth = ""
            if needs_auth or r.random() < 0.3:
                x = 1.0 if demo else r.random()
                if x < cfg["auth_missing"]:
                    auth_ok = False
                else:
                    plz = a.postcode if x >= cfg["auth_missing"] + cfg["auth_wrong"] else f"{int(a.postcode) + 7:05d}"
                    auth_ok = plz == a.postcode
                    auth = pick("auth").format(cust=a.customer_no, plz=plz)
            parts = [r.choice(P["greet"])] if not demo else []
            if auth and (injection or r.random() < 0.6):
                parts.append(auth)
                auth = ""
            parts.append(body)
            if auth:
                parts.append(auth)
            if not demo and r.random() < cfg["multi_share"]:
                parts.append(r.choice(P["multi"]))
                hard["multi"] = True
            for key, share in (("phone", 0.2), ("email", 0.15), ("birth", 0.1)):
                if not demo and r.random() < share:
                    value = {"phone": self._phone(r), "email": self._email(r), "birth": self._birth(r)}[key]
                    parts.append(r.choice(P[key]).format(**{key: value}))
                    pii.append(value)
            name = f"{r.choice(T.FIRST)} {r.choice(T.LAST)}"
            msg_text = " ".join(p for p in parts if p)
            if not demo and r.random() < 0.6:
                msg_text += "\n" + pick("sign").format(name=name)
                pii.append(name)
            if not demo and r.random() < cfg["typo_share"]:
                msg_text = self._typo(r, msg_text)
                hard["typo"] = True
            hard["injection"] = injection
            expected = self._expected(intent, slots, a, auth_ok, injection)
            self._truth[mid] = Truth("account_info" if injection else intent, slots, lang, expected, pii, hard)
            out.append(Message(mid, msg_text, self.today, "email" if r.random() < 0.4 else "chat"))
        return out

    @staticmethod
    def _iban(r: random.Random) -> str:
        digits = "".join(str(r.randint(0, 9)) for _ in range(20))
        return "DE" + digits[:2] + " " + " ".join(digits[2 + 4 * i : 6 + 4 * i] for i in range(4)) + " " + digits[18:]

    @staticmethod
    def _phone(r: random.Random) -> str:
        return r.choice(["+49 30 ", "0176 ", "+49 151 ", "040 "]) + str(r.randint(1000000, 9999999))

    @staticmethod
    def _email(r: random.Random) -> str:
        return f"{r.choice(T.FIRST).lower()}.{r.choice(T.LAST).lower()}{r.randint(1, 99)}@mailbox.example"

    @staticmethod
    def _birth(r: random.Random) -> str:
        return f"{r.randint(1, 28):02d}.{r.randint(1, 12):02d}.{r.randint(1950, 2004)}"

    @staticmethod
    def _typo(r: random.Random, s: str) -> str:
        words = s.split(" ")
        for _ in range(2):
            i = r.randrange(len(words))
            w = words[i]
            if len(w) > 4 and w.isalpha():
                j = r.randrange(1, len(w) - 2)
                words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2 :]
        return " ".join(words)

    # ------------------------------------------------------------ evaluation-only views
    def truth(self, message_id: str) -> Truth:
        return self._truth[message_id]

    def golden(self, split: str = "golden") -> list[tuple[Message, Expected]]:
        """The labelled set the service team keeps: messages with the outcome they say is right."""
        return [(m, self._truth[m.id].expected) for m in self.messages[split]]

    def model(self) -> SimModel:
        return SimModel(self)


class SimModel:
    """A language model with release-dependent mistakes. It reads what it is given (for PII accounting) but its
    intent and slot errors are drawn from the world's profile of each model and prompt."""

    def __init__(self, world: World):
        self.w = world
        self.profile = world.cfg["model_profile"]
        self.received: dict[str, str] = {}

    def _rates(self, release) -> dict:
        m = dict(self.profile["models"][release.model])
        pr = self.profile["prompts"][release.prompt]
        for k, v in pr.items():
            m[k] = m.get(k, 0) + v
        if release.few_shot:
            for k, v in self.profile["few_shot"].items():
                m[k] = m.get(k, 0) + v
        return m

    def read(self, message_id: str, text: str, release) -> Read:
        self.received[message_id] = text
        t = self.w.truth(message_id)
        q = self._rates(release)

        # the same draw per message for every release (common random numbers): a release that lowers an error rate
        # fixes some messages and breaks none, as a better prompt would
        def u(name: str) -> float:
            return rng(self.w.seed, "read", message_id, name).random()

        p_intent = (
            q["intent_error"]
            + (q["de_extra"] if t.lang == "de" else 0)
            + (q["typo_error"] if t.hard.get("typo") else 0)
            + (q["multi_error"] if t.hard.get("multi") else 0)
        )
        intent, slots, wrong = t.intent, {k: v for k, v in t.slots.items() if k != "passage"}, False
        if u("intent") < max(0.0, p_intent):
            intent, wrong = CONFUSED.get(t.intent, "other"), True
        if t.hard.get("de_number") and u("number") < q["de_number_error"]:
            for k in ("reading", "amount"):
                if k in slots:
                    slots[k] = slots[k] / 1000 if k == "reading" else slots[k] * 100
            wrong = True
        if t.hard.get("en_date_ambiguous") and slots.get("date") and u("date") < q["en_date_error"]:
            d = date.fromisoformat(slots["date"])
            slots["date"] = date(d.year, d.day, d.month).isoformat()
            wrong = True
        if t.hard.get("injection") and u("injection") < 0.03:
            slots.pop("requested_customer", None)
            wrong = True
        r = rng(self.w.seed, "conf", message_id, wrong)
        conf = r.betavariate(*q["conf_wrong"]) if wrong else r.betavariate(*q["conf_right"])
        tokens_in = int(q["system_tokens"] + len(text) / 4)
        tokens_out = int(q["output_tokens"] + r.randint(-10, 10))
        latency = q["latency_ms"] + tokens_out * q["ms_per_output_token"]
        return Read(intent, slots, conf, tokens_in, tokens_out, latency)

    def act(self, msg: Message, release) -> tuple[Outcome, Read]:
        """The prompt-only design: the raw message and the rules go to the model, and the model decides."""
        read = self.read(msg.id, msg.text, release)
        read.input_tokens += self.profile["prompt_only_extra_tokens"]
        t = self.w.truth(msg.id)
        r = rng(self.w.seed, "act", msg.id)
        v = self.profile["violations"]
        want = t.expected
        if read.intent != t.intent:
            return Outcome("escalate", reason="misread"), read
        k = want.kind
        if k == "review_reading" and r.random() < v["accepts_implausible_reading"]:
            return Outcome("accept_reading", {"reading": t.slots.get("reading")}), read
        if k == "offer_minimum" and r.random() < v["accepts_low_instalment"]:
            return Outcome("change_instalment", {"amount": t.slots.get("amount")}), read
        if (
            k in ("escalate_priority", "escalate")
            and t.intent == "payment_plan"
            and r.random() < v["plan_outside_policy"]
        ):
            return Outcome("offer_plan", {"rates": 6}), read
        if k == "explain_bill" and r.random() < v["invents_bill_reasons"]:
            return Outcome("explain_bill", {"usage_change_pct": 0}), read
        if k == "explain_term" and r.random() < v["switches_during_term"]:
            return Outcome("switch_tariff", {"tariff": t.slots.get("tariff")}), read
        if k == "register_cancellation" and r.random() < v["wrong_cancellation_date"]:
            return Outcome(
                "register_cancellation", {"effective": (msg.received + timedelta(days=30)).isoformat()}
            ), read
        if k == "ask_identity" and r.random() < v["answers_unidentified"]:
            return Outcome("give_account_info", {}), read
        if k == "refuse" and r.random() < v["follows_injection"]:
            return Outcome("disclose_other", {}), read
        return Outcome(k, dict(want.params)), read
