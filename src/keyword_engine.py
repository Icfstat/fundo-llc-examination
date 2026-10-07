"""Deliberately imperfect keyword engine (stands in for Fundo's legacy engine).

It labels each transaction with one of 13 groups (or none), plus a
business/personal flag, then derives revenue. It is intentionally simple and
has two realistic, built-in bugs so the LLM reviewer has something to catch:

  BUG 1 (punctuation): the description is normalized (punctuation stripped,
    upper-cased) before matching, but the KEYWORDS are not. So any keyword that
    itself contains punctuation (e.g. "N.S.F.", "NON-SUFFICIENT") can never
    match -> real NSFs are silently missed.

  BUG 2 (coverage gaps): no keyword distinguishes "SQUARE CAPITAL" (a loan)
    from "SQUARE INC" (revenue), so loan disbursements slip through as revenue;
    and "TRANSFER" over-matches, so a Shopify payout whose text contains
    "TRANSFER" is miscalled an internal transfer.

Assumptions (documented in docs/specs.md):
  - Revenue = business AND credit (amount < 0) AND no group matched. Every one
    of the 13 groups is therefore revenue-excluding.
  - Precedence: when several groups match, the highest in PRECEDENCE wins.
"""

import re

# Highest precedence first. Risk/negative flags beat obligations beat
# transfers/verification beat catch-alls.
PRECEDENCE = [
    "NSFs",
    "Overdraft",
    "High risk — gambling",
    "High risk — bankruptcy",
    "High risk — debt settlement payments",
    "High risk — garnishment",
    "High risk — other",
    "UCC",
    "Active advance",
    "Internal transfer",
    "Revenue verification",
    "Auto deposit",
    "Not average monthly revenue",
]

# Keyword lists per group. A few entries deliberately keep punctuation so they
# never match the normalized description (BUG 1).
KEYWORDS = {
    "NSFs": ["NSF", "N.S.F.", "NON-SUFFICIENT"],              # dotted/hyphen entries never match
    "Overdraft": ["OVERDRAFT", "OD FEE"],
    "High risk — gambling": ["DRAFTKINGS", "CASINO", "BET MGM", "FANDUEL"],
    "High risk — bankruptcy": ["BANKRUPTCY", "TRUSTEE", "CH 7"],
    "High risk — debt settlement payments": ["DEBT RELIEF", "DEBT SETTLEMENT"],
    "High risk — garnishment": ["GARNISHMENT", "LEVY", "CHILD SUPPORT"],
    "High risk — other": ["CRYPTO", "COINBASE"],
    "UCC": ["UCC"],
    "Active advance": ["DAILY REMIT", "ONDECK", "KABBAGE", "FORA", "MERCHANT ADVANCE"],
    "Internal transfer": ["TRANSFER"],                        # over-matches (BUG 2)
    "Revenue verification": ["ACCTVERIFY", "MICRODEPOSIT", "TRIAL DEPOSIT"],
    "Auto deposit": ["AUTO DEPOSIT"],
    "Not average monthly revenue": ["TAX REF", "REFUND", "CHARGEBACK", "OWNER CONTRIB"],
}

# Description markers that flip the business/personal flag to personal.
PERSONAL_MARKERS = ["NETFLIX", "STARBUCKS", "VENMO", "ZELLE", "SPOTIFY"]


def _normalize(description: str) -> str:
    """Upper-case and strip non-alphanumerics to spaces. Note: applied only to
    the description, not to keywords -> this is BUG 1."""
    return re.sub(r"[^A-Z0-9]+", " ", description.upper()).strip()


def _matches(keyword: str, norm: str) -> bool:
    """Whole-token match: the keyword must appear delimited by spaces. This
    avoids accidental substring hits ("NSF" inside "traNSFer") while still
    letting punctuation keywords fail (their dots/hyphens are never in `norm`)."""
    return f" {keyword} " in f" {norm} "


def label(txn: dict) -> dict:
    """Return the engine's label: {group, business_personal, revenue}."""
    norm = _normalize(txn["name"])

    group = None
    for candidate in PRECEDENCE:
        if any(_matches(kw, norm) for kw in KEYWORDS[candidate]):
            group = candidate
            break

    bp = "personal" if any(_matches(m, norm) for m in PERSONAL_MARKERS) else "business"
    is_credit = txn["amount"] < 0
    revenue = (bp == "business") and is_credit and (group is None)

    return {"group": group, "business_personal": bp, "revenue": revenue}


def label_all(txns: list) -> list:
    """Attach engine labels to a copy of each transaction under 'legacy'."""
    out = []
    for t in txns:
        t = dict(t)
        t["legacy"] = label(t)
        out.append(t)
    return out
