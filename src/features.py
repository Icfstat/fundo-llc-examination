"""Per-business credit features and the offer rule.

Features are computed from a chosen label set so we can compare them directly:
    label_key = "truth"      -> the ground truth
    label_key = "legacy"     -> the keyword engine (before review)
    label_key = "corrected"  -> after the reviewer's corrections

Denominators (total deposits, total debits) come from the signed amount, not
the labels, so they are identical across label sets.

Assumptions (documented in docs/specs.md):
    - 90-day window = 3 months; average monthly revenue = revenue dollars / 3.
    - other funders' daily payments = Active-advance debit dollars / 90.
"""

from collections import defaultdict

MONTHS = 3.0
DAYS = 90.0


def _amount_in(txn):
    """Dollars flowing in (credit). Plaid: credit = negative amount."""
    return -txn["amount"] if txn["amount"] < 0 else 0.0


def _amount_out(txn):
    """Dollars flowing out (debit)."""
    return txn["amount"] if txn["amount"] > 0 else 0.0


def features_for(txns: list, label_key: str) -> dict:
    """Return {business_id: feature_dict} using labels from txn[label_key]."""
    deposits = defaultdict(float)
    debits = defaultdict(float)
    revenue = defaultdict(float)
    high_risk_debit = defaultdict(float)
    advance_debit = defaultdict(float)
    nsf = defaultdict(int)
    overdraft = defaultdict(int)

    for t in txns:
        b = t["business_id"]
        lab = t[label_key]
        deposits[b] += _amount_in(t)
        debits[b] += _amount_out(t)
        if lab["revenue"]:
            revenue[b] += _amount_in(t)
        group = lab["group"]
        if group == "NSFs":
            nsf[b] += 1
        elif group == "Overdraft":
            overdraft[b] += 1
        if group and group.startswith("High risk"):
            high_risk_debit[b] += _amount_out(t)
        if group == "Active advance":
            advance_debit[b] += _amount_out(t)

    out = {}
    for b in sorted(deposits):
        amr = revenue[b] / MONTHS
        out[b] = {
            "avg_monthly_revenue": amr,
            "revenue_share_of_deposits": (revenue[b] / deposits[b]) if deposits[b] else 0.0,
            "nsf_count": nsf[b],
            "overdraft_count": overdraft[b],
            "high_risk_share_of_debits": (high_risk_debit[b] / debits[b]) if debits[b] else 0.0,
            "other_funders_daily_payment": advance_debit[b] / DAYS,
            "offer": offer(amr, nsf[b], advance_debit[b] / DAYS),
        }
    return out


def offer(avg_monthly_revenue: float, nsf_count: int, other_funders_daily: float) -> float:
    """offer = 1.2 * AMR - 20 * other funders' daily payments; 0 if NSF > 5."""
    if nsf_count > 5:
        return 0.0
    return max(0.0, 1.2 * avg_monthly_revenue - 20 * other_funders_daily)
