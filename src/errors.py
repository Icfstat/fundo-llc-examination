"""Show the labels the reviewer got wrong, to walk through them.

Runs the pipeline on the committed dataset (which carries ground-truth labels)
entirely from the committed cache, then prints every transaction whose final
label disagrees with the truth, with the reason the reviewer gave.

Read-only and needs NO API key: it only replays cached responses.

    .venv/bin/python src/errors.py
"""

import json

import generate_data
import keyword_engine as ke
import reviewer


def main():
    with open(generate_data.DATA_PATH) as f:
        txns = json.load(f)

    rows = ke.label_all(txns)          # engine label -> 'legacy'
    rows = reviewer.review_all(rows)   # Luna (client=None: cache only)
    reviewer.escalate_all(rows)        # Terra on the flagged subset (cache only)

    wrong = [t for t in rows
             if t["corrected"]["group"] != t["truth"]["group"]
             or t["corrected"]["business_personal"] != t["truth"]["business_personal"]]

    print(f"{len(wrong)} label(s) the reviewer got wrong (final vs truth)\n")
    for t in wrong:
        engine_right = (t["legacy"]["group"] == t["truth"]["group"]
                        and t["legacy"]["business_personal"] == t["truth"]["business_personal"])
        kind = "bad flag (engine was right)" if engine_right else "missed or wrong fix"
        decision = t.get("terra", t["reviewer"])   # Terra's record if it ran, else Luna's
        print(f"- {t['transaction_id']}  {t['name']!r}")
        print(f"    truth={t['truth']['group']}  legacy={t['legacy']['group']}  "
              f"final={t['corrected']['group']}  [{kind}]")
        print(f"    confidence={decision.get('confidence')}  reason={decision.get('reason')!r}\n")


if __name__ == "__main__":
    main()
