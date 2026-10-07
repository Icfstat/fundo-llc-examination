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

## Results (measured)

Summed absolute error in average monthly revenue across the 10 businesses:

| | revenue error vs truth |
|---|---|
| legacy (keyword engine) | **$43,395** |
| after reviewer corrections | **$12,386** |

The reviewer cuts revenue error by ~71%. Of 196 transactions it flagged: **152
good catches** (fixed a real error), **44 bad flags** (doubted an already-correct
label), **0 missed** engine errors. It also fixes offers: the engine's NSF
undercount (missed NSF variants) wrongly offered biz_04/biz_08 ~$33–40k when the
truth is $0; after review both correctly return to $0.

**First-pass learning (what did not work):** the initial prompt listed the 13
group *names* with no definitions. GPT-6 Luna invented semantics and reclassified
~620 payment-processor deposits (real revenue) as "Not average monthly revenue",
*tripling* the error to $128k. Adding a one-line glossary per group — and stating
explicitly that processor payouts are revenue — fixed it.

Residual $12,386 / 44 bad flags are left for the next pass. (GPT-6 Luna at
temperature 0 is only best-effort deterministic, so separate live runs vary
slightly; the committed cache is the fixed, reproducible result.)

## Determinism

The dataset is seeded and committed; the engine is pure; the LLM cache is keyed
on `sha256(model + prompt)`. A clean checkout replays the committed cache with
no API key and identical output. (OpenAI's `seed` is best-effort; the cache is
the actual guarantee.)

## Cost

GPT-6 Luna at $0.10 / $0.50 per M tokens, 1,745 cached calls (after prompt-level
deduplication). One full pass costs **~$0.07** (measured); reproducing from the
committed cache costs **$0**. Development used a few passes (prompt fix + cache
format), so **total actual spend ≈ $0.2** — far under the $10 cap.

## Tools used

Built with Claude Code (Opus) as a pair: it drafted the generator, engine,
reviewer, and report, and wrote this document. Every design decision (ground
truth in the generator, the model/code boundary, the engine's limitations) was
reviewed and verified by running the pipeline and inspecting the known error cases.
