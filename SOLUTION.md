# SOLUTION — Fundo AI Engineer Challenge (v1 baseline)

This is the **baseline**: the smallest thing that runs end to end and produces
measured numbers. Deferred analysis is listed explicitly at the end.

## Scope, and what is deferred

**Done in v1 (runnable):**
- Synthetic Plaid-shaped dataset with ground-truth labels (10 businesses, 90
  days, ~1,850 transactions).
- Deliberately imperfect 13-group keyword engine with precedence and a
  business/personal flag.
- LLM reviewer: one cached GPT-6 Luna call per transaction.
- Credit-impact compute: per-business features and the offer rule, for
  truth / legacy / corrected labels.
- A measured report: revenue dollar error and reviewer behavior vs truth.

**Deferred to the next pass (writeup, mostly not code):**
- Mislabel-rate sensitivity sweep (2 % / 5 % / 10 %).
- The two short-answer questions (zero-NSF bank; 61-day vs 90-day history).
- False-revenue vs false-active-advance cost analysis.
- Production one-pager (shadow rollout, input drift, reproducibility, humans).

## Data

Generated, not sourced — building it is part of the test. Each transaction is
born with a correct label; the keyword engine then mislabels some. This is the
only way to report a *measured* dollar error. Cases deliberately included:
noisy ACH descriptions, counterparty ambiguity (`SQUARE INC` vs
`SQUARE CAPITAL`), punctuation that defeats a keyword, hard negatives (a large
legitimate invoice that looks like a loan), and untrusted counterparty text.

## The keyword engine and its planted errors

Simple token matching with a precedence order. Two realistic bugs give the
reviewer something to catch:
1. **Punctuation** — the description is normalized but the keywords are not, so
   `N.S.F.` / `NON-SUFFICIENT` never match and real NSFs are missed.
2. **Coverage gaps** — nothing distinguishes `SQUARE CAPITAL` (a loan) from
   revenue, and `TRANSFER` over-matches, so `STRIPE TRANSFER` revenue and a
   noisy Shopify payout are miscalled internal transfers.

## The reviewer, and the model/code boundary

The model is a reviewer, not a relabeler: it sees the transaction and the
engine's label and returns `agree` or `doubt` (+ corrected group,
business/personal, confidence, one-line reason). Structured Outputs constrains
the JSON; an invalid group or malformed response **fails safe to the legacy
label**.

**Boundary (deliberate):** the model may propose only `group` and
`business_personal`. It never decides **revenue** — that is derived in code
from the fixed rule (business AND credit AND no group). The dollar that drives
the offer is therefore never at the mercy of a free-form model answer.

## Results

- **Measured** — legacy vs truth, summed absolute error in average monthly
  revenue across the 10 businesses: **$42,497**. The punctuation bug also
  undercounts NSFs, which flips some offers from $0 to a positive number
  (e.g. biz_04, biz_08) — a concrete funding error.
- **Pending first real run** — corrected vs truth error and the reviewer
  behavior counts (good catches / bad flags / missed) are produced by
  `python src/run.py` once the cache is populated; numbers go here, marked
  measured.

## Determinism

The dataset is seeded and committed; the engine is pure; the LLM cache is keyed
on `sha256(model + prompt)`. A clean checkout replays the committed cache with
no API key and identical output. (OpenAI's `seed` is best-effort; the cache is
the actual guarantee.)

## Cost

GPT-6 Luna at $0.10 / $0.50 per M tokens, ~1,850 short calls (with prompt-level
deduplication). Estimated first-run spend **< $0.25**; $0 thereafter from cache.
Actual spend to be recorded after the first real run.

## Tools used

Built with Claude Code (Opus) as a pair: it drafted the generator, engine,
reviewer, and report, and wrote this document. Every design decision (ground
truth in the generator, the model/code boundary, the planted bugs) was reviewed
and verified by running the pipeline and inspecting the known error cases.
