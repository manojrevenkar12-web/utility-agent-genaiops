"""A keyword reader for running the service without a model endpoint (local runs, the container smoke test).
It is not measured and not meant for customers; production reads with Azure OpenAI (model.AzureOpenAIModel)."""

from __future__ import annotations

import re
from datetime import date

from .domain import Read

KEYWORDS = [
    ("outage", r"strom weg|stromausfall|gas im keller|rieche gas|smell gas|power .*out|blackout"),
    ("meter_reading", r"zählerstand|meter reading|stand vom|reading off"),
    ("instalment_change", r"abschlag.*(?:auf|ändern|setzen|runter)|instalment to|monthly payment to|pay €"),
    ("payment_plan", r"ratenzahlung|in raten|payment plan|in instalments|split the"),
    ("bill_explanation", r"so hoch|nachzahl|so much|bill so high"),
    ("tariff_switch", r"tarif .* wechseln|umstellen|switch to|move me to|change to"),
    ("move_out", r"ziehe|auszug|umzug|moving|move-out"),
    ("cancellation", r"kündig|cancel"),
    ("account_info", r"offen\b|was ist noch offen|how much .*owe|open amount|kontostand|balance"),
    ("faq", r"\?"),
]
NUMBER = r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)"


def _parse(num: str, german: bool) -> float:
    if german:
        return float(num.replace(".", "").replace(",", "."))
    return float(num.replace(",", ""))


class KeywordModel:
    def read(self, message_id: str, text: str, release) -> Read:
        low = text.lower()
        german = bool(re.search(r"\b(?:ich|mein|bitte|der|die|das)\b", low))
        intent = next((i for i, rx in KEYWORDS if re.search(rx, low)), "other")
        slots: dict = {}
        if intent == "meter_reading" and (m := re.search(NUMBER + r"\s*(?:kwh)?\s*\.?\s*$|:\s*" + NUMBER, low)):
            slots["reading"] = _parse(m.group(1) or m.group(2), german)
        if intent == "instalment_change" and (m := re.search(r"€\s?" + NUMBER + "|" + NUMBER + r"\s?(?:€|euro)", low)):
            slots["amount"] = _parse(m.group(1) or m.group(2), german)
        if m := re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", text):
            slots["date"] = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        if m := re.search(r"\b(Grundversorgung|Flex|Fix24|Oeko12)\b", text):
            slots["tariff"] = m.group(1)
        if m := re.search(r"\[KUNDENNR_[2-9]\]", text):
            slots["requested_customer"] = m.group(0)
        return Read(intent, slots, 0.9 if intent != "other" else 0.3, 0, 0, 0.0)
