"""End-to-end: generate -> label -> review (Luna) -> escalate (Terra) ->
features -> report.

    python src/run.py

With cache/llm.json populated it needs no API key and prints the same report
every time. On a cache miss it needs OPENAI_API_KEY to call the models once,
then writes the responses into cache/llm.json for you to commit.
"""

import json
import os
from pathlib import Path

import generate_data
import keyword_engine as ke
import reviewer
import features

ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "out" / "report.md"


def _make_client():
    """Return an OpenAI client if a key is set, else None (cache-only mode)."""
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    from openai import OpenAI
    return OpenAI()


def _load_data():
    if not generate_data.DATA_PATH.exists():
        generate_data.main()
    with open(generate_data.DATA_PATH) as f:
        return json.load(f)


def _money(x):
    return f"${x:,.0f}"


def _metrics(txns, key):
    """Count what a label set (txn[key]) did vs ground truth and the engine."""
    flagged = good = bad = missed = 0
    for t in txns:
        legacy, truth, c = t["legacy"], t["truth"], t[key]
        engine_correct = (legacy["group"] == truth["group"]
                          and legacy["business_personal"] == truth["business_personal"])
        changed = (c["group"] != legacy["group"]
                   or c["business_personal"] != legacy["business_personal"])
        corrected_right = (c["group"] == truth["group"]
                           and c["business_personal"] == truth["business_personal"])
        if changed:
            flagged += 1
            if not engine_correct and corrected_right:
                good += 1          # fixed a real error
            elif engine_correct:
                bad += 1           # changed an already-correct label
        elif not engine_correct:
            missed += 1            # left a wrong label in place
    return {"flagged": flagged, "good_catches": good,
            "bad_flags": bad, "missed_errors": missed}


def _revenue_error(feat, truth):
    """Total absolute dollar error in average monthly revenue across businesses."""
    return sum(abs(feat[b]["avg_monthly_revenue"] - truth[b]["avg_monthly_revenue"])
               for b in truth)


def build_report(txns, have_v2):
    truth = features.features_for(txns, "truth")
    legacy = features.features_for(txns, "legacy")
    luna = features.features_for(txns, "reviewer")        # v1: stage 1 only
    final = features.features_for(txns, "corrected")      # v2: after Terra (== v1 if no stage 2)

    lines = ["# Report (v2: Luna triage + Terra adjudication)", "",
             "Average monthly revenue and offer, per business.", "",
             "| business | AMR truth | AMR legacy | AMR v1 | AMR v2 | offer truth | offer legacy | offer v2 |",
             "|---|---|---|---|---|---|---|---|"]
    for b in sorted(truth):
        lines.append(
            f"| {b} | {_money(truth[b]['avg_monthly_revenue'])} | {_money(legacy[b]['avg_monthly_revenue'])} | "
            f"{_money(luna[b]['avg_monthly_revenue'])} | {_money(final[b]['avg_monthly_revenue'])} | "
            f"{_money(truth[b]['offer'])} | {_money(legacy[b]['offer'])} | {_money(final[b]['offer'])} |")

    lines += ["", "## Measured revenue error (sum of |AMR - truth| over businesses)", "",
              f"- legacy vs truth:        {_money(_revenue_error(legacy, truth))}",
              f"- v1 Luna vs truth:       {_money(_revenue_error(luna, truth))}",
              f"- v2 Luna+Terra vs truth: {_money(_revenue_error(final, truth))}"
              + ("" if have_v2 else "   (stage 2 skipped; equals v1)")]

    m1 = _metrics(txns, "reviewer")
    lines += ["", "## Reviewer behavior vs ground truth", "",
              f"- v1 Luna:       flagged {m1['flagged']}, good {m1['good_catches']}, "
              f"bad {m1['bad_flags']}, missed {m1['missed_errors']}"]
    if have_v2:
        m2 = _metrics(txns, "corrected")
        lines.append(f"- v2 Luna+Terra: flagged {m2['flagged']}, good {m2['good_catches']}, "
                     f"bad {m2['bad_flags']}, missed {m2['missed_errors']}")
    else:
        lines.append("- v2 Luna+Terra: stage 2 skipped (no cache and no OPENAI_API_KEY).")
    return "\n".join(lines) + "\n"


def main():
    data = _load_data()
    labeled = ke.label_all(data)

    client = _make_client()
    reviewed = reviewer.review_all(labeled, client)   # stage 1
    try:
        reviewer.escalate_all(reviewed, client)       # stage 2 (in place)
        have_v2 = True
    except RuntimeError as e:
        print("WARNING:", e)
        have_v2 = False

    report = build_report(reviewed, have_v2)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(report)
    print(f"(report written to {REPORT_PATH})")


if __name__ == "__main__":
    main()
