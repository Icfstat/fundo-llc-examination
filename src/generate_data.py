"""Generate a synthetic, Plaid-shaped transaction dataset with GROUND TRUTH labels.

Why ground truth:
    The challenge grades "dollar error in monthly revenue AFTER corrections".
    You cannot measure error without a truth to compare against. Because we
    generate the data ourselves, every transaction is BORN with its correct
    label (group / business-or-personal / revenue). The keyword engine then
    mislabels some of them. That gives three layers per transaction:

        truth  ->  legacy (keyword engine)  ->  reviewer (LLM)

    so "did the reviewer reduce dollar error?" becomes a MEASURED number.

Plaid sign convention (documented assumption, see docs/specs.md):
    amount > 0  -> money OUT of the account  (debit)
    amount < 0  -> money IN to the account   (credit)

The engine and the reviewer only ever read the Plaid fields
(name, amount, ...). The "truth" block is our evaluation annotation; it is
never shown to the engine or the model.
"""

import json
import random
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "transactions.json"

START_DATE = "2025-07-02"  # fixed window so the committed dataset never drifts
NUM_DAYS = 90
SEED = 42

# Ten businesses with different profiles. Variety here is what exercises the
# funding-relevant cases (processors, active advances, high-risk activity).
BUSINESSES = [
    {"id": "biz_01", "processor": "SQUARE",  "advance": None,       "high_risk": None},
    {"id": "biz_02", "processor": "STRIPE",  "advance": "ONDECK",   "high_risk": None},
    {"id": "biz_03", "processor": "SHOPIFY", "advance": None,       "high_risk": "gambling"},
    {"id": "biz_04", "processor": "SQUARE",  "advance": "KABBAGE",  "high_risk": None},
    {"id": "biz_05", "processor": "CLOVER",  "advance": None,       "high_risk": None},
    {"id": "biz_06", "processor": "STRIPE",  "advance": "FORA",     "high_risk": "debt_settlement"},
    {"id": "biz_07", "processor": "SHOPIFY", "advance": None,       "high_risk": None},
    {"id": "biz_08", "processor": "SQUARE",  "advance": "ONDECK",   "high_risk": "garnishment"},
    {"id": "biz_09", "processor": "CLOVER",  "advance": None,       "high_risk": None},
    {"id": "biz_10", "processor": "STRIPE",  "advance": "KABBAGE",  "high_risk": "bankruptcy"},
]

# Revenue deposit description templates per processor. Some are intentionally
# noisy (counterparty-written text, ACH prefixes) so keywords struggle.
REVENUE_TEMPLATES = {
    "SQUARE":  ["SQ *{m}", "SQUARE INC DEPOSIT {m}", "ACH CREDIT SQUARE INC"],
    "STRIPE":  ["STRIPE TRANSFER {m}", "ACH CREDIT STRIPE PAYMENTS"],
    "SHOPIFY": ["SHOPIFY PAYMENT {m}", "ACH CREDIT SHOPIFY"],
    "CLOVER":  ["CLOVER APP DEPOSIT {m}", "ACH CREDIT CLOVER"],
}
MERCHANTS = ["JOES TACOS", "BELLA SALON", "MIDTOWN AUTO", "GREEN GROCER",
             "CITY BAKERY", "PRINT SHOP", "YOGA LOFT", "PET SPA"]

# (description, group, business_personal, amount_sign)  amount_sign: +debit / -credit
EXPENSES = [
    ("GUSTO PAYROLL", None, "business", +1),
    ("WHOLESALE SUPPLY CO", None, "business", +1),
    ("CITY UTILITIES", None, "business", +1),
    ("ADOBE SUBSCRIPTION", None, "business", +1),
    ("COMMERCIAL RENT LLC", None, "business", +1),
]
PERSONAL = [
    ("NETFLIX", None, "personal", +1),
    ("STARBUCKS", None, "personal", +1),
    ("VENMO TO FRIEND", None, "personal", +1),
    ("ZELLE TO J SMITH", None, "personal", +1),
]
HIGH_RISK = {
    "gambling":        ("DRAFTKINGS BET", "High risk — gambling"),
    "bankruptcy":      ("CH 7 TRUSTEE PAYMENT", "High risk — bankruptcy"),
    "debt_settlement": ("NATIONAL DEBT RELIEF", "High risk — debt settlement payments"),
    "garnishment":     ("WAGE GARNISHMENT LEVY", "High risk — garnishment"),
}


def _iso_dates(rng):
    """All 90 calendar dates in the window, as YYYY-MM-DD strings."""
    import datetime as dt
    start = dt.date.fromisoformat(START_DATE)
    return [(start + dt.timedelta(days=i)).isoformat() for i in range(NUM_DAYS)]


def generate(seed: int = SEED):
    """Return a deterministic list of transactions. Same seed -> identical bytes."""
    rng = random.Random(seed)
    txns = []
    counter = [0]

    def emit(biz, date, name, amount, group, bp):
        """Append one transaction plus its ground-truth annotation.

        Truth revenue rule mirrors the engine's rule so truth and engine labels
        are computed the same way (only the GROUP differs when the engine errs):
        revenue = business AND credit AND no group matched.
        """
        is_credit = amount < 0
        revenue = (bp == "business") and is_credit and (group is None)
        txns.append({
            "transaction_id": f"txn_{counter[0]:05d}",
            "account_id": biz["id"],
            "business_id": biz["id"],
            "date": date,
            "name": name,
            "amount": round(amount, 2),
            "iso_currency_code": "USD",
            "truth": {"group": group, "business_personal": bp, "revenue": revenue},
        })
        counter[0] += 1

    dates = _iso_dates(rng)
    for biz in BUSINESSES:
        for date in dates:
            day = int(date[-2:])

            # --- revenue deposits (the bread and butter) ---
            if rng.random() < 0.85:
                tmpl = rng.choice(REVENUE_TEMPLATES[biz["processor"]])
                name = tmpl.format(m=rng.choice(MERCHANTS))
                emit(biz, date, name, -rng.uniform(150, 1800), None, "business")

            # --- ordinary business expenses ---
            if rng.random() < 0.6:
                name, grp, bp, sign = rng.choice(EXPENSES)
                emit(biz, date, name, sign * rng.uniform(40, 900), grp, bp)

            # --- personal spend mixed into the account ---
            if rng.random() < 0.15:
                name, grp, bp, sign = rng.choice(PERSONAL)
                emit(biz, date, name, sign * rng.uniform(8, 120), grp, bp)

            # --- weekly internal transfer ---
            if day % 7 == 0:
                emit(biz, date, "TRANSFER TO SAVINGS", +rng.uniform(500, 3000),
                     "Internal transfer", "business")

            # --- active advance repayment to another funder (weekly) ---
            if biz["advance"] and day % 7 == 3:
                emit(biz, date, f"{biz['advance']} DAILY REMIT",
                     +rng.uniform(80, 400), "Active advance", "business")

            # --- high-risk activity (weekly) ---
            if biz["high_risk"] and day % 7 == 5:
                name, grp = HIGH_RISK[biz["high_risk"]]
                emit(biz, date, name, +rng.uniform(50, 600), grp, "business")

            # --- occasional bank fees ---
            if rng.random() < 0.05:
                emit(biz, date, "NSF FEE", +35.0, "NSFs", "business")
            if rng.random() < 0.04:
                emit(biz, date, "OVERDRAFT FEE", +35.0, "Overdraft", "business")

        _emit_special_cases(biz, dates, rng, emit)

    txns.sort(key=lambda t: (t["date"], t["transaction_id"]))
    return txns


def _emit_special_cases(biz, dates, rng, emit):
    """A handful of deliberately tricky transactions per business.

    These are the cases the keyword engine gets WRONG (so the reviewer can earn
    its keep) or RIGHT-but-suspicious (hard negatives the reviewer must leave
    alone). Truth is set to the correct answer; whether the engine agrees is
    decided later by keyword_engine.py.
    """
    d = dates[10]
    # Shopify payout whose counterparty text contains "TRANSFER" -> engine will
    # over-match Internal transfer, but it is real revenue.
    emit(biz, d, "ORIG CO NAME:SHOPIFY CO ENTRY DESCR:TRANSFER",
         -rng.uniform(400, 1500), None, "business")

    # Square Capital loan disbursement -> truth is Active advance (NOT revenue),
    # but no keyword catches "SQUARE CAPITAL", so the engine will call it revenue.
    emit(biz, dates[20], "SQUARE CAPITAL BT 8842",
         -rng.uniform(5000, 12000), "Active advance", "business")

    # NSF written with punctuation -> engine normalizes the description but its
    # "N.S.F." keyword keeps the dots, so this real NSF is silently missed.
    emit(biz, dates[30], "N.S.F. RETURN ITEM FEE", +35.0, "NSFs", "business")
    emit(biz, dates[35], "NON-SUFFICIENT FUNDS CHARGE", +35.0, "NSFs", "business")

    # One-off credit that must NOT count as revenue.
    emit(biz, dates[40], "IRS TREAS 310 TAX REF",
         -rng.uniform(800, 2500), "Not average monthly revenue", "business")

    # Micro-deposit used to verify the account, not revenue.
    emit(biz, dates[45], "ACCTVERIFY TRIAL DEPOSIT", -0.02,
         "Revenue verification", "business")

    # UCC filing fee.
    emit(biz, dates[50], "UCC FILING FEE SOS", +125.0, "UCC", "business")

    # HARD NEGATIVE: a large, legitimate wholesale invoice payment. Looks like a
    # loan but is genuine revenue; engine labels it revenue (correct). The
    # reviewer should AGREE — flagging it wastes underwriter time.
    emit(biz, dates[55], "ACH CREDIT WHOLESALE INV 50000 ACME CORP",
         -rng.uniform(8000, 15000), None, "business")


def main():
    txns = generate()
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w") as f:
        json.dump(txns, f, indent=2, sort_keys=True)
    print(f"wrote {len(txns)} transactions to {DATA_PATH}")


if __name__ == "__main__":
    main()
