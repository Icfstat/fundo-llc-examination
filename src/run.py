"""End-to-end baseline: generate -> label -> review -> features -> report.

    python src/run.py

With cache/llm/ populated it needs no API key and prints the same report every
time. On a cache miss it needs OPENAI_API_KEY to call GPT-6 Luna once, then
writes the responses into cache/llm/ for you to commit.
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


def _review_metrics(txns):
    """Count what the reviewer did, measured against ground truth."""
    flags = catches = bad_flags = missed = 0
    for t in txns:
        legacy, truth, rev = t["legacy"], t["truth"], t["reviewer"]
        engine_correct = legacy["group"] == truth["group"]
        if rev["verdict"] == "doubt":
            flags += 1
            if not engine_correct and rev["group"] == truth["group"]:
                catches += 1          # fixed a real error
            elif engine_correct:
                bad_flags += 1        # flagged a correct label (wasted time)
        elif not engine_correct:
            missed += 1               # agreed with a wrong label
    return {"flags": flags, "good_catches": catches,
            "bad_flags": bad_flags, "missed_errors": missed}


def _revenue_error(feat, truth):
    """Total absolute dollar error in average monthly revenue across businesses."""
    return sum(abs(feat[b]["avg_monthly_revenue"] - truth[b]["avg_monthly_revenue"])
               for b in truth)


def build_report(txns, have_review):
    truth = features.features_for(txns, "truth")
    legacy = features.features_for(txns, "legacy")
    corrected = features.features_for(txns, "corrected") if have_review else None

    lines = ["# Baseline report", ""]
    lines.append("Average monthly revenue and offer, per business.\n")
    header = "| business | AMR truth | AMR legacy | " + ("AMR corrected | " if have_review else "")
    header += "offer truth | offer legacy | " + ("offer corrected |" if have_review else "")
    lines.append(header)
    sep = "|---|---|---|" + ("---|" if have_review else "") + "---|---|" + ("---|" if have_review else "")
    lines.append(sep)
    for b in sorted(truth):
        row = f"| {b} | {_money(truth[b]['avg_monthly_revenue'])} | {_money(legacy[b]['avg_monthly_revenue'])} | "
        if have_review:
            row += f"{_money(corrected[b]['avg_monthly_revenue'])} | "
        row += f"{_money(truth[b]['offer'])} | {_money(legacy[b]['offer'])} | "
        if have_review:
            row += f"{_money(corrected[b]['offer'])} |"
        lines.append(row)

    lines += ["", "## Measured revenue error (sum of |AMR - truth| over businesses)", ""]
    lines.append(f"- legacy vs truth: {_money(_revenue_error(legacy, truth))}")
    if have_review:
        lines.append(f"- corrected vs truth: {_money(_revenue_error(corrected, truth))}")

    if have_review:
        m = _review_metrics(txns)
        lines += ["", "## Reviewer behavior (vs ground truth)", "",
                  f"- transactions flagged (doubt): {m['flags']}",
                  f"- good catches (fixed a real error): {m['good_catches']}",
                  f"- bad flags (doubted a correct label): {m['bad_flags']}",
                  f"- missed errors (agreed with a wrong label): {m['missed_errors']}"]
    else:
        lines += ["", "_Reviewer step skipped: no cache and no OPENAI_API_KEY. "
                  "Set the key and re-run to populate cache/llm/._"]
    return "\n".join(lines) + "\n"


def main():
    data = _load_data()
    labeled = ke.label_all(data)

    client = _make_client()
    try:
        reviewed = reviewer.review_all(labeled, client)
        have_review = True
    except RuntimeError as e:
        print("WARNING:", e)
        reviewed, have_review = labeled, False

    report = build_report(reviewed, have_review)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(report)
    print(f"(report written to {REPORT_PATH})")


if __name__ == "__main__":
    main()
