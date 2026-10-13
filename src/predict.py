"""Run the pipeline on NEW transactions and print predictions only.

Give it a JSON file holding a list of transactions. Each transaction needs only
two fields:

    name    the description text
    amount  the dollar amount; Plaid sign: negative = money in, positive = money out

Example file (save as data/their_transactions.json):

    [
      {"name": "ACH CREDIT SQUARE INC",  "amount": -1250.00},
      {"name": "SQUARE CAPITAL BT 8842", "amount": -9000.00}
    ]

These are new transactions with no known answer, so there is no truth and no
error metric: it prints the predicted group, business/personal, revenue, a
confidence and a short reason for each.

New transactions are not in the committed cache, so this needs an API key:

    set -a; source .env; set +a
    .venv/bin/python src/predict.py data/their_transactions.json

Responses are cached in out/predict_cache.json (a gitignored scratch file), so
the committed cache/llm.json and the reproducible report are left untouched.
"""

import json
import os
import sys
from pathlib import Path

import cache
import keyword_engine as ke
import reviewer

# Keep new calls out of the committed cache: cache them in the gitignored out/.
cache.CACHE_PATH = Path(__file__).resolve().parent.parent / "out" / "predict_cache.json"


def _client():
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    from openai import OpenAI
    return OpenAI()


def main(path):
    with open(path) as f:
        txns = json.load(f)

    rows = ke.label_all(txns)
    client = _client()
    rows = reviewer.review_all(rows, client)   # Luna
    reviewer.escalate_all(rows, client)        # Terra on the flagged subset

    for t in rows:
        c = t["corrected"]
        decision = t.get("terra", t["reviewer"])
        print(f"{t['name']!r}  amount={t['amount']}")
        print(f"    group={c['group']}  {c['business_personal']}  revenue={c['revenue']}  "
              f"confidence={decision.get('confidence')}  reason={decision.get('reason')!r}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: .venv/bin/python src/predict.py <transactions.json>")
        sys.exit(1)
    main(sys.argv[1])
