"""Replies are written from the decision's facts, in the customer's language. No model writes a number."""

from __future__ import annotations

import re

from .domain import Outcome

GERMAN = re.compile(
    r"(?i)\b(?:ich|mein|meine|bitte|hallo|guten|zählerstand|abschlag|rechnung|danke|wir|möchte|"
    r"kundennummer|grüße)\b"
)

TEXT = {
    "accept_reading": (
        "Thank you, your reading of {reading} kWh is saved.",
        "Danke, Ihr Zählerstand von {reading} kWh ist gespeichert.",
    ),
    "review_reading": (
        "Thank you. A colleague will check this reading and get back to you.",
        "Danke. Eine Kollegin prüft diesen Zählerstand und meldet sich bei Ihnen.",
    ),
    "change_instalment": (
        "Your monthly instalment is now €{amount}.",
        "Ihr monatlicher Abschlag beträgt jetzt {amount} €.",
    ),
    "offer_minimum": (
        "To avoid a large back payment, the lowest instalment we can set is €{amount}. Shall we?",
        "Um eine hohe Nachzahlung zu vermeiden, ist der niedrigste Abschlag {amount} €. Sollen wir ihn so einstellen?",
    ),
    "review_instalment": (
        "A colleague will check this amount with you.",
        "Eine Kollegin prüft diesen Betrag mit Ihnen.",
    ),
    "offer_plan": (
        "We can split the open amount into {rates} monthly payments of €{rate_eur}.",
        "Wir können den offenen Betrag in {rates} Monatsraten zu je {rate_eur} € aufteilen.",
    ),
    "no_balance": ("There is nothing open on your account.", "Auf Ihrem Konto ist nichts offen."),
    "escalate_priority": (
        "A colleague will contact you today. Nothing will be interrupted while we talk.",
        "Eine Kollegin meldet sich noch heute bei Ihnen. Während wir sprechen, wird nichts gesperrt.",
    ),
    "escalate": (
        "A colleague will take this over and contact you.",
        "Eine Kollegin übernimmt Ihr Anliegen und meldet sich.",
    ),
    "explain_bill": (
        "Your usage changed by {usage_change_pct} % and the price per kWh by {price_change_ct} ct.",
        "Ihr Verbrauch hat sich um {usage_change_pct} % und der Preis je kWh um {price_change_ct} ct geändert.",
    ),
    "explain_term": (
        "Your fixed price runs until {until}; you can switch after that.",
        "Ihre Preisgarantie läuft bis {until}; danach können Sie wechseln.",
    ),
    "switch_tariff": (
        "Done: you move to {tariff} from the next billing month.",
        "Erledigt: Sie wechseln zum nächsten Abrechnungsmonat in {tariff}.",
    ),
    "explain_options": ("At your address we offer: {options}.", "An Ihrer Adresse bieten wir an: {options}."),
    "register_move": (
        "Your move on {date} is noted. Please send the meter reading from that day.",
        "Ihr Auszug am {date} ist vermerkt. Bitte senden Sie den Zählerstand von diesem Tag.",
    ),
    "register_cancellation": (
        "Your cancellation is received and takes effect on {effective}.",
        "Ihre Kündigung ist eingegangen und wird zum {effective} wirksam.",
    ),
    "give_account_info": (
        "Open amount: €{balance_eur}. Monthly instalment: €{instalment_eur}.",
        "Offener Betrag: {balance_eur} €. Monatlicher Abschlag: {instalment_eur} €.",
    ),
    "redirect_grid": (
        "Outages are fixed by your grid operator; their number is on your bill.",
        "Störungen behebt Ihr Netzbetreiber; die Nummer steht auf Ihrer Rechnung.",
    ),
    "answer_faq": ("{answer}", "{answer}"),
    "ask_identity": (
        "Please send your customer number and postcode so we can find your account.",
        "Bitte senden Sie Ihre Kundennummer und Postleitzahl, damit wir Ihr Konto finden.",
    ),
    "ask_details": (
        "Could you send the missing detail ({reason})?",
        "Könnten Sie die fehlende Angabe senden ({reason})?",
    ),
    "refuse": (
        "We can only give information about your own account.",
        "Wir geben nur Auskunft zu Ihrem eigenen Konto.",
    ),
}


FORMATS = {
    "reading": "{:,.0f}",
    "amount": "{:,.2f}",
    "rate_eur": "{:,.2f}",
    "balance_eur": "{:,.2f}",
    "instalment_eur": "{:,.2f}",
    "usage_change_pct": "{:+d}",
    "price_change_ct": "{:+.1f}",
}


def _num(key: str, value, german: bool) -> str:
    s = FORMATS[key].format(value)
    if german:
        s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    if key == "amount" and s.endswith((".00", ",00")) and FORMATS[key] == "{:,.2f}":
        return s
    return s


def reply(outcome: Outcome, message: str) -> str:
    en, de = TEXT.get(outcome.kind, TEXT["escalate"])
    german = bool(GERMAN.search(message))
    template = de if german else en
    params = {**outcome.params, "reason": outcome.reason}
    for k in FORMATS:
        if k in params and params[k] is not None:
            params[k] = _num(k, params[k], german)
    if "options" in params:
        params["options"] = ", ".join(params["options"])
    try:
        return template.format(**params)
    except (KeyError, ValueError):
        return TEXT["escalate"][1 if template is de else 0]
