# SOLUTION — Fundo AI Engineer Challenge (v2)

A two-stage LLM reviewer of an imperfect keyword labeling engine, with measured
credit impact. v1 was a single Luna pass; v2 adds a Terra adjudication stage on
the flagged subset. Deferred analysis is listed explicitly at the end.

## Scope, and what is deferred

**Done (runnable):**
- Synthetic Plaid-shaped dataset with ground-truth labels (10 businesses, 90
  days, ~1,850 transactions).
- Deliberately imperfect 13-group keyword engine with precedence and a
  business/personal flag.
- Two-stage reviewer: GPT-6 Luna triages every transaction; GPT-5.6 Terra
  re-reviews only the flagged subset to confirm or overturn.
- Credit-impact compute: per-business features and the offer rule, for
  truth / legacy / v1 / v2 labels.
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
`SQUARE CAPITAL`), NSF phrasings outside the keyword list, hard negatives (a
large legitimate invoice that looks like a loan), and untrusted counterparty text.

## The keyword engine and its limitations

Simple token matching with a precedence order; ~92% accurate. We make it
imperfect through the inherent **limitations** of keyword matching, not planted
bugs — a more honest and defensible stand-in for a legacy engine, and still
"deliberately imperfect" as the brief asks. Four limitations:
1. **Incomplete vocabulary** — a fixed keyword list misses unlisted phrasings,
   so an NSF written as `RETURNED ITEM FEE` / `NON-SUFFICIENT FUNDS` is missed.
2. **No counterparty disambiguation** — nothing separates `SQUARE CAPITAL` (a
   loan) from `SQUARE INC` (revenue), so the loan slips through as revenue.
3. **Blunt matching** — generic `TRANSFER` over-matches `STRIPE TRANSFER`, a
   real payout, miscalling it an internal transfer.
4. **No punctuation handling** — matching is token-based and does not normalize
   punctuation, so `OVERDRAFT-FEE` isn't recognized and the fee is missed
   (undercounting overdrafts). The same blind spot harmlessly spares a noisy
   `...DESCR:TRANSFER` Shopify payout from the blunt-match error in (3).

## The two-stage reviewer, and the model/code boundary

The models are reviewers, not relabelers.

- **Stage 1 — Luna triage (every transaction).** The fast, cheap model sees the
  transaction and the engine label and returns `agree`/`doubt` (+ corrected
  group, business/personal, reason). It is deliberately high-recall: it
  over-flags rather than miss, so stage 2 mostly needs to *prune* false flags.
- **Stage 2 — Terra adjudication (flagged subset only).** The stronger reasoning
  model sees the engine label *and Luna's suggestion* and confirms or overturns.
  Running it only on the ~190 flags (not all ~1,850 txns) keeps cost tiny while
  putting the strong model exactly where the hard calls are.

**Confidence as scored criteria (not a guess).** Terra scores four criteria 0–1
— counterparty clarity, direction consistency, group fit, evidence strength —
and the confidence is their **mean, computed in code**. This makes the judgment
legible to an underwriter instead of an opaque number.

**Boundary (deliberate):** the models propose only `group` and
`business_personal` (plus Terra's criterion scores). Code owns the rest:
**revenue** is derived from the fixed rule (business AND credit AND no group),
and the confidence is averaged in code. The dollar that drives the offer is
never at the mercy of a free-form model answer. Structured Outputs constrains
the JSON; an invalid group or malformed response **fails safe to the legacy
label**.

A known limitation: stage 2 only sees Luna's flags, so it cannot fix a case Luna
wrongly *agreed* with (a false negative). Luna's high-recall design keeps that
set small (0 missed in the measured run).

## Results (measured)

Summed absolute error in average monthly revenue across the 10 businesses, and
flags (changes to the engine label) vs ground truth:

| | revenue error vs truth | good catches | bad flags | missed |
|---|---|---|---|---|
| legacy (keyword engine) | **$43,395** | — | — | — |
| v1 — Luna only | **$12,386** | 152 | 42 | 0 |
| v2 — Luna + Terra | **$898** | 152 | 4 | 0 |

v2 cuts revenue error **98% vs legacy and 93% vs v1**. Terra overturns almost all
of Luna's false flags (42 → 4) while keeping every good catch, and every
business's offer now matches truth (e.g. the engine wrongly offered biz_04/biz_08
~$33–40k on an NSF undercount; both correctly return to $0).

**What did not work (v1):** the first prompt listed the 13 group *names* with no
definitions. Luna invented semantics and reclassified ~620 payment-processor
deposits (real revenue) as "Not average monthly revenue", *tripling* error to
$128k. A one-line glossary per group — stating explicitly that processor payouts
are revenue — brought it to $12,386. Luna's remaining weakness was over-flagging
(42 false flags); the Terra stage is what removed it.

(GPT-6 Luna at temperature 0 is only best-effort deterministic, so separate live
runs vary slightly; the committed cache is the fixed, reproducible result.)

## Determinism

The dataset is seeded and committed; the engine is pure; the LLM cache is keyed
on `sha256(model + prompt)`. A clean checkout replays the committed cache with
no API key and identical output. (OpenAI's `seed` is best-effort; the cache is
the actual guarantee.)

## Cost

Two models, both cached (1,745 Luna + 169 Terra responses in `cache/llm.json`):

- **Luna** ($0.10 / $0.50 per M): one full triage pass ≈ **$0.07** (measured).
- **Terra** ($2 / $12 per M, `reasoning_effort=low`): 169 flagged calls ≈
  **~$1** (estimate; confirm on the usage dashboard).

Reproducing from the committed cache costs **$0**. Restricting Terra to the
flagged subset is what keeps the stronger model affordable. Total actual spend is
a few dollars at most — far under the $10 cap.

## Tools used

Built with Claude Code (Opus) as a pair: it drafted the generator, engine,
reviewer, and report, and wrote this document. Every design decision (ground
truth in the generator, the model/code boundary, the engine's limitations) was
reviewed and verified by running the pipeline and inspecting the known error cases.
