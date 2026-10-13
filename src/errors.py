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


def _fmt(label):
    return (f"group={label['group']}  "
            f"business_personal={label['business_personal']}  "
            f"revenue={label['revenue']}")


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
        kind = "bad flag, engine was right" if engine_right else "missed or wrong fix"
        direction = "money in (credit)" if t["amount"] < 0 else "money out (debit)"

        print("=" * 70)
        print(f"{t['transaction_id']}   {t['date']}   {t['name']!r}")
        print(f"  raw:      amount={t['amount']} {t['iso_currency_code']} ({direction})  "
              f"business_id={t['business_id']}")
        print(f"  truth:    {_fmt(t['truth'])}")
        print(f"  engine:   {_fmt(t['legacy'])}"
              f"   [{'matches truth' if engine_right else 'differs from truth'}]")

        luna = t["reviewer"]
        print(f"  Luna:     verdict={luna['verdict']}  {_fmt(luna)}")
        print(f"            confidence={luna.get('confidence')}  reason={luna.get('reason')!r}")

        if "terra" in t:
            terra = t["terra"]
            print(f"  Terra:    verdict={terra['verdict']}  {_fmt(terra)}")
            crit = terra.get("criteria") or {}
            if crit:
                print("            criteria: " + "  ".join(f"{k}={v}" for k, v in crit.items()))
            print(f"            confidence={terra.get('confidence')}  reason={terra.get('reason')!r}")
        else:
            print("  Terra:    not escalated (Luna agreed with the engine)")

        print(f"  final:    {_fmt(t['corrected'])}   [WRONG vs truth, {kind}]\n")


if __name__ == "__main__":
    main()
