"""Personal data out before a model or a trace sees the message.

Identifiers the agent needs (customer number, postcode) become placeholders the code can map back; everything else
(IBAN, e-mail, phone, birth date, the name in a signature) becomes a typed mask."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# customer numbers have a fixed format (10 and five digits); phones are masked before this runs
CUSTOMER = re.compile(r"(?<![\d.,])(10\d{5})(?![\d.,]\d)")
POSTCODE = re.compile(r"(?i)\b(?:plz|postleitzahl|postcode|post code|zip)(?:\s+(?:ist|is|lautet))?[:\s]*(\d{5})\b")
POSTCODE_NEAR = re.compile(r"\[KUNDENNR_1\][^\d\n]{1,25}?(\d{5})\b")
MASKS = [
    ("IBAN", re.compile(r"(?i)\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,3})?\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+\d{2}[\s/-]?|0)\d{2,4}[\s/-]?\d{3,8}(?:[\s-]?\d{2,5})?(?!\w)")),
    (
        "BIRTHDATE",
        re.compile(
            r"(?i)\b(?:geb\.?|geboren(?: am)?|born(?: on)?|date of birth:?|dob:?)\s*"
            r"\d{1,2}[./]\d{1,2}[./]\d{2,4}"
        ),
    ),
]
SIGNATURE = re.compile(
    r"(?im)^(?:viele grüße|mit freundlichen grüßen|beste grüße|lg|best regards|kind regards|"
    r"regards|thanks|danke|best),?\s*\n\s*([A-ZÄÖÜ][\w\-]+(?:\s+[A-ZÄÖÜ][\w\-]+){0,2})\s*$"
)
NAME_INTRO = re.compile(
    r"(?:mein name ist|ich bin|my name is|this is)\s+([A-ZÄÖÜ][\w\-]+\s+[A-ZÄÖÜ][\w\-]+)", re.IGNORECASE
)


@dataclass
class Redacted:
    text: str
    customers: dict[str, str] = field(default_factory=dict)  # placeholder -> customer number
    postcode: str | None = None
    masked: dict[str, int] = field(default_factory=dict)

    @property
    def identity(self) -> str | None:
        return self.customers.get("[KUNDENNR_1]")


def redact(text: str) -> Redacted:
    out = Redacted(text)
    seen: dict[str, str] = {}

    def cust(m: re.Match) -> str:
        num = m.group(1)
        if num not in seen:
            seen[num] = f"[KUNDENNR_{len(seen) + 1}]"
            out.customers[seen[num]] = num
        return m.group(0).replace(num, seen[num])

    t = text
    for label, rx in MASKS[:3]:  # IBAN, e-mail and phone first, so their digits are never read as a customer number
        t, n = rx.subn(f"[{label}]", t)
        if n:
            out.masked[label] = n
    t = CUSTOMER.sub(cust, t)
    pm = POSTCODE.search(t) or POSTCODE_NEAR.search(t)
    if pm:
        out.postcode = pm.group(1)
        t = t[: pm.start(1)] + "[PLZ]" + t[pm.end(1) :]
    for label, rx in MASKS[3:]:
        t, n = rx.subn(f"[{label}]", t)
        if n:
            out.masked[label] = out.masked.get(label, 0) + n
    for rx in (SIGNATURE, NAME_INTRO):

        def name(m: re.Match) -> str:
            out.masked["NAME"] = out.masked.get("NAME", 0) + 1
            return m.group(0).replace(m.group(1), "[NAME]")

        t = rx.sub(name, t)
    out.text = t
    return out
