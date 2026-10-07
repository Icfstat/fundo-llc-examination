"""Mislabel sensitivity (brief Part 2): if a given fraction of labels is wrong,
how far does each business's offer move -- and does it matter WHERE the errors
land?

We place the SAME number of errors two ways:
  uniform        - any transaction, chosen at random
  offer-relevant - only the labels that feed the offer (revenue deposits and
                   active-advance payments)

Each error reassigns the transaction's group to a random wrong one (revenue is
then recomputed by the fixed rule). Pure code, no API. Averaged over seeds so
the numbers are stable. Run: python src/sensitivity.py
"""

import json
import random

import generate_data
import features
from keyword_engine import PRECEDENCE as GROUPS

RATES = [0.02, 0.05, 0.10]
SEEDS = 25
OPTIONS = GROUPS + [None]


def _revenue(group, bp, amount):
    """Mirror of the fixed revenue rule (business credit, no group)."""
    return bp == "business" and amount < 0 and group is None


def _corrupt(txns, rate, in_pool, rng):
    """Write a 'corrupt' label onto every txn: truth, except a random `rate`
    fraction (drawn from the pool) whose group is flipped to a wrong one."""
    pool = [i for i, t in enumerate(txns) if in_pool(t)]
    n = round(rate * len(txns))
    chosen = set(rng.sample(pool, min(n, len(pool))))
    for i, t in enumerate(txns):
        base = t["truth"]
        if i in chosen:
            new = rng.choice([g for g in OPTIONS if g != base["group"]])
            t["corrupt"] = {"group": new,
                            "business_personal": base["business_personal"],
                            "revenue": _revenue(new, base["business_personal"], t["amount"])}
        else:
            t["corrupt"] = dict(base)
    return n


def _mean_abs(a, b, key):
    return sum(abs(a[x][key] - b[x][key]) for x in a) / len(a)


def main():
    with open(generate_data.DATA_PATH) as f:
        txns = json.load(f)
    truth = features.features_for(txns, "truth")

    pools = {
        "uniform": lambda t: True,
        "offer-relevant": lambda t: t["truth"]["revenue"] or t["truth"]["group"] == "Active advance",
    }

    rows = []
    for method, in_pool in pools.items():
        for rate in RATES:
            d_amr = d_off = cliff = 0.0
            n = 0
            for s in range(SEEDS):
                n = _corrupt(txns, rate, in_pool, random.Random(s))
                feat = features.features_for(txns, "corrupt")
                d_amr += _mean_abs(feat, truth, "avg_monthly_revenue")
                d_off += _mean_abs(feat, truth, "offer")
                cliff += sum((feat[b]["nsf_count"] > 5) != (truth[b]["nsf_count"] > 5)
                             for b in truth)
            rows.append((method, rate, n, d_amr / SEEDS, d_off / SEEDS, cliff / SEEDS))

    print(f"Mislabel sensitivity (averaged over {SEEDS} seeds, 10 businesses)\n")
    print("| method | rate | txns wrong | avg |Δ AMR| / business | avg |Δ offer| / business | NSF-cliff crossings |")
    print("|---|---|---|---|---|---|")
    for method, rate, n, amr, off, cliff in rows:
        print(f"| {method} | {int(rate*100)}% | {n} | ${amr:,.0f} | ${off:,.0f} | {cliff:.1f} |")


if __name__ == "__main__":
    main()
