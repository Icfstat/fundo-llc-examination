"""Simple keyword engine (stands in for Fundo's legacy engine).

It labels each transaction with one of 13 groups (or none), plus a
business/personal flag, then derives revenue. It is intentionally simple and
performs decently, but its mistakes come from the inherent LIMITATIONS of
literal keyword matching -- not from deliberately planted bugs:

  - Incomplete vocabulary: it matches a fixed keyword list, so phrasings it
    does not list are missed (e.g. an NSF described as "RETURNED ITEM").
  - No counterparty disambiguation: the same token means different things, and
    the engine cannot tell "SQUARE INC" (revenue) from "SQUARE CAPITAL" (loan),
    so an unlisted loan counterparty slips through as revenue.
  - Blunt matching: a generic keyword over-matches, so "STRIPE TRANSFER" (a
    revenue payout) is caught by the "TRANSFER" rule for internal transfers.
  - No punctuation handling: matching is token-based and does not normalize
    punctuation, so a keyword fused to adjacent punctuation in a noisy
    description ("OVERDRAFT-FEE") is not recognized and the fee is missed.

These are exactly the gaps an LLM reviewer is positioned to catch.

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

# Keyword lists per group. Reasonable but incomplete -- phrasings not listed
# here are simply missed (a vocabulary-coverage limitation, not a bug).
KEYWORDS = {
    "NSFs": ["NSF", "INSUFFICIENT FUNDS"],                    # misses "RETURNED ITEM", "NON-SUFFICIENT"
    "Overdraft": ["OVERDRAFT", "OD FEE"],
    "High risk — gambling": ["DRAFTKINGS", "CASINO", "BET MGM", "FANDUEL"],
    "High risk — bankruptcy": ["BANKRUPTCY", "TRUSTEE", "CH 7"],
    "High risk — debt settlement payments": ["DEBT RELIEF", "DEBT SETTLEMENT"],
    "High risk — garnishment": ["GARNISHMENT", "LEVY", "CHILD SUPPORT"],
    "High risk — other": ["CRYPTO", "COINBASE"],
    "UCC": ["UCC"],
    "Active advance": ["DAILY REMIT", "ONDECK", "KABBAGE", "FORA", "MERCHANT ADVANCE"],
    "Internal transfer": ["TRANSFER"],                        # generic; also catches "STRIPE TRANSFER"
    "Revenue verification": ["ACCTVERIFY", "MICRODEPOSIT", "TRIAL DEPOSIT"],
    "Auto deposit": ["AUTO DEPOSIT"],
    "Not average monthly revenue": ["TAX REF", "REFUND", "CHARGEBACK", "OWNER CONTRIB"],
}

# Description markers that flip the business/personal flag to personal.
PERSONAL_MARKERS = ["NETFLIX", "STARBUCKS", "VENMO", "ZELLE", "SPOTIFY"]


def _normalize(description: str) -> str:
    """Upper-case and collapse whitespace. Punctuation is left in place: the
    engine does not canonicalize it, which is one of its limitations."""
    return re.sub(r"\s+", " ", description.upper()).strip()


def _matches(keyword: str, norm: str) -> bool:
    """Whole-token match: the keyword must appear delimited by spaces, so "NSF"
    does not match inside "TRANSFER", and punctuation fused to a word
    ("OVERDRAFT-FEE") keeps the plain keyword ("OVERDRAFT") from matching."""
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
