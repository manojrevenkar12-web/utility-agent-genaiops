"""The utility's rules, applied in code. The model only reads the message; these functions decide."""

from __future__ import annotations

import math
from datetime import date, timedelta

from .domain import Account, Accounts, Outcome


def projected_monthly(a: Account) -> float:
    return (a.annual_kwh * a.price_ct / 100 + a.base_eur_month * 12) / 12


def meter_reading(a: Account, reading: float | None, today: date, p: dict) -> Outcome:
    if reading is None:
        return Outcome("ask_details", reason="no reading in the message")
    days = (today - a.last_reading_date).days
    if days < p["min_days"]:
        return Outcome("review_reading", reason=f"last reading only {days} days ago")
    used = reading - a.last_reading
    expected = a.annual_kwh / 365 * days
    if used < 0:
        return Outcome("review_reading", reason="lower than the last reading: meter change or typo")
    if not p["low_factor"] * expected <= used <= p["high_factor"] * expected:
        return Outcome("review_reading", reason=f"{used:.0f} kWh in {days} days, expected about {expected:.0f}")
    return Outcome("accept_reading", {"reading": reading}, "plausible")


def instalment_change(a: Account, amount: float | None, p: dict) -> Outcome:
    if amount is None:
        return Outcome("ask_details", reason="no amount in the message")
    monthly = projected_monthly(a)
    minimum = math.ceil(p["min_share"] * monthly)
    if amount < minimum:
        return Outcome("offer_minimum", {"amount": float(minimum)}, f"below {p['min_share']:.0%} of projected cost")
    if amount > p["max_share"] * monthly:
        return Outcome("review_instalment", reason="far above projected cost; possibly a typo")
    return Outcome("change_instalment", {"amount": round(amount, 2)}, "within bounds")


def payment_plan(a: Account, p: dict) -> Outcome:
    if a.dunning_stage >= p["priority_dunning_stage"] or a.hardship:
        why = "supply interruption announced" if a.dunning_stage >= p["priority_dunning_stage"] else "hardship"
        return Outcome("escalate_priority", reason=why)
    if a.balance_eur <= 0:
        return Outcome("no_balance", reason="nothing open")
    if a.balance_eur > p["max_balance_eur"] or a.broken_plan_12m:
        return Outcome("escalate", reason="above the self-service limit or a broken plan in the last year")
    rates = max(1, min(p["max_rates"], math.floor(a.balance_eur / p["min_rate_eur"])))
    return Outcome("offer_plan", {"rates": rates, "rate_eur": round(a.balance_eur / rates, 2)}, "within limits")


def bill_explanation(a: Account) -> Outcome:
    usage = round(100 * (a.annual_kwh - a.prev_year_kwh) / a.prev_year_kwh)
    price = round(a.price_ct - a.prev_price_ct, 1)
    return Outcome("explain_bill", {"usage_change_pct": usage, "price_change_ct": price}, "from the billing data")


def tariff_switch(a: Account, accounts: Accounts, tariff: str | None, today: date) -> Outcome:
    if a.fixed_until and a.fixed_until > today:
        return Outcome("explain_term", {"until": a.fixed_until.isoformat()}, "fixed term still running")
    options = accounts.tariffs_for(a.postcode, a.commodity)
    if tariff and tariff in options and tariff != a.tariff:
        return Outcome("switch_tariff", {"tariff": tariff}, "available at this postcode")
    return Outcome("explain_options", {"options": options}, "tariff not named or not available here")


def move_out(moved: date | None) -> Outcome:
    if moved is None:
        return Outcome("ask_details", reason="no moving date")
    return Outcome("register_move", {"date": moved.isoformat()}, "date given")


def cancellation(a: Account, today: date, p: dict) -> Outcome:
    if a.tariff == "Grundversorgung":
        effective = today + timedelta(days=p["basic_supply_notice_days"])
    elif a.fixed_until and a.fixed_until > today:
        effective = a.fixed_until
    else:
        effective = today + timedelta(days=30)
    return Outcome("register_cancellation", {"effective": effective.isoformat()}, f"{a.tariff} notice rules")


def account_info(a: Account) -> Outcome:
    return Outcome("give_account_info", {"balance_eur": a.balance_eur, "instalment_eur": a.instalment_eur})
