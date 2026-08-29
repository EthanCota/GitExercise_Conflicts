#!/usr/bin/env python3
"""
ev_model.py -- Expected-value ranking of current credit-card sign-up bonuses.

Loads facts/bonuses.json and computes, per offer:

    EV = bonus_points * currency_valuation_cpp/100
         - first_year_fee (annual_fee_usd, as reported)
         - forgone_2pct_cashback (min_spend_usd * 0.02)

currency_valuation_cpp (cents per point/mile) is extracted from the
"notes" field of each bonus record via a regex looking for phrases like
"valued at 2.05 cents/point" or "valued at ~1.2 cents/mile". This keeps
every valuation traceable to the same fact file the bonus came from,
rather than importing an outside valuation table.

If a record has no parseable valuation (e.g. Marriott Bonvoy Brilliant,
which has no cpp figure anywhere in bonuses.json or redemptions.json),
the script does NOT invent one. It reports the offer with EV = None and
a reason, so the gap is visible rather than silently guessed. Same
graceful handling applies to any other missing/malformed field
(bonus_points, min_spend_usd, annual_fee_usd default to 0 with a flag
rather than crashing).

Run:  python3 ev_model.py
"""

import json
import re
import os

FACTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "facts", "bonuses.json")

# Matches "valued at 2.05 cents/point", "worth $X at 2.05 cents/point",
# "valued at 1.55 cents" (no unit suffix), etc. -- anchored on the word
# "at" immediately preceding the number, followed by "cent(s)" with an
# optional "/point" or "/mile" unit.
VALUATION_RE = re.compile(r"\bat\s*~?(\d+(?:\.\d+)?)\s*cents?(?:/(?:point|mile))?", re.IGNORECASE)

CASHBACK_ALT_RATE = 0.02  # forgone flat-2%-cashback opportunity cost on min spend


def load_bonuses(path):
    with open(path, "r") as f:
        return json.load(f)


def extract_valuation_cpp(notes):
    """Pull a 'valued at X cents/point|mile' figure out of the notes string.
    Returns (cpp_float_or_None, matched_text_or_None)."""
    if not notes or not isinstance(notes, str):
        return None, None
    m = VALUATION_RE.search(notes)
    if not m:
        return None, None
    return float(m.group(1)), m.group(0)


def compute_ev(offer):
    """Returns a dict with all inputs, the computed EV (or None), and flags
    describing any missing/defaulted fields. Never raises on missing data."""
    flags = []

    card = offer.get("card", "UNKNOWN CARD")
    currency = offer.get("currency", "UNKNOWN CURRENCY")

    bonus_points = offer.get("bonus_points")
    if bonus_points is None:
        flags.append("missing bonus_points -> treated as 0")
        bonus_points = 0

    min_spend = offer.get("min_spend_usd")
    if min_spend is None:
        flags.append("missing min_spend_usd -> treated as 0 (no forgone-cashback cost applied)")
        min_spend = 0

    annual_fee = offer.get("annual_fee_usd")
    if annual_fee is None:
        flags.append("missing annual_fee_usd -> treated as 0")
        annual_fee = 0

    notes = offer.get("notes", "")
    cpp, matched_text = extract_valuation_cpp(notes)
    if cpp is None:
        flags.append("no cited cents/point valuation in notes -> EV not computable (no fabricated cpp used)")

    forgone_cashback = round(min_spend * CASHBACK_ALT_RATE, 2)

    ev = None
    gross_value = None
    if cpp is not None:
        gross_value = round(bonus_points * (cpp / 100.0), 2)
        ev = round(gross_value - annual_fee - forgone_cashback, 2)

    return {
        "card": card,
        "issuer": offer.get("issuer", "UNKNOWN"),
        "currency": currency,
        "bonus_points": bonus_points,
        "cpp_used": cpp,
        "cpp_source": "bonuses.json:notes (\"%s\")" % matched_text if matched_text else "N/A",
        "min_spend_usd": min_spend,
        "annual_fee_usd": annual_fee,
        "forgone_2pct_cashback_usd": forgone_cashback,
        "gross_value_usd": gross_value,
        "ev_usd": ev,
        "confidence": offer.get("confidence"),
        "flags": flags,
    }


def rank(rows):
    # Offers with computable EV first (sorted desc by EV), then offers
    # without a citable valuation, alphabetically, at the bottom.
    computable = [r for r in rows if r["ev_usd"] is not None]
    non_computable = [r for r in rows if r["ev_usd"] is None]
    computable.sort(key=lambda r: r["ev_usd"], reverse=True)
    non_computable.sort(key=lambda r: r["card"])
    return computable + non_computable


def format_table(ranked):
    headers = ["#", "Card", "Currency", "Bonus", "cpp", "MinSpend", "AnnFee",
               "ForgoneCB(2%)", "GrossVal", "EV($)"]
    lines = []
    lines.append(" | ".join(headers))
    lines.append(" | ".join(["---"] * len(headers)))
    for i, r in enumerate(ranked, start=1):
        cpp_str = f"{r['cpp_used']:.2f}" if r["cpp_used"] is not None else "N/A"
        gross_str = f"${r['gross_value_usd']:,.0f}" if r["gross_value_usd"] is not None else "N/A"
        ev_str = f"${r['ev_usd']:,.0f}" if r["ev_usd"] is not None else "N/A (no cited cpp)"
        lines.append(" | ".join([
            str(i),
            r["card"],
            r["currency"],
            f"{r['bonus_points']:,}",
            cpp_str,
            f"${r['min_spend_usd']:,}",
            f"${r['annual_fee_usd']:,}",
            f"${r['forgone_2pct_cashback_usd']:,.0f}",
            gross_str,
            ev_str,
        ]))
    return "\n".join(lines)


def main():
    offers = load_bonuses(FACTS_PATH)
    rows = [compute_ev(o) for o in offers]
    ranked = rank(rows)

    print("EV MODEL -- ranked by EV = bonus_points*cpp/100 - annual_fee - (min_spend*2%)")
    print("cpp values are parsed from bonuses.json 'notes' field (self-cited, not external).")
    print()
    print(format_table(ranked))
    print()
    print("Flags (missing/defaulted fields, non-fatal):")
    any_flags = False
    for r in ranked:
        if r["flags"]:
            any_flags = True
            print(f"  - {r['card']}: {'; '.join(r['flags'])}")
    if not any_flags:
        print("  (none)")

    return ranked


if __name__ == "__main__":
    main()
