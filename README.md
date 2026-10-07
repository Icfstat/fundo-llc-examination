# Fundo Senior AI Engineer examination: v2

A two-stage LLM **reviewer** of an imperfect keyword transaction-labeling engine.
GPT-6 Luna triages every transaction and flags the doubtful ones; GPT-5.6 Terra
then adjudicates only that flagged subset. We measure what the corrections are
worth to a funding decision.

See `docs/specs.md` for the requirements and the adopted assumptions, and
`SOLUTION.md` for the writeup.

## Pipeline

```
generate_data.py -> keyword_engine.py -> reviewer.py ------------> features.py -> report
  (truth labels)      (legacy labels)    Luna triage, Terra adj.    (offer rule)
```

Every transaction carries four label layers so error is **measured**, not
claimed: `truth` → `legacy` (engine) → `reviewer` (Luna / v1) → `corrected`
(Luna+Terra / v2).

Models (OpenAI API): **GPT-6 Luna** (`gpt-6-luna`), cheap and high-throughput, for
the full triage pass; **GPT-5.6 Terra** (`gpt-5.6-terra`), stronger reasoning, for
the small flagged subset only.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Reproduce the results (no API key)

The dataset and the LLM responses are committed, so the full report regenerates
offline and identically every run:

```bash
.venv/bin/python src/run.py          # writes out/report.md
.venv/bin/python src/sensitivity.py  # Part 2 mislabel-sensitivity table
```

The committed `data/transactions.json` and `cache/llm.json` make a clean checkout
reproduce the report deterministically.

## Regenerate the cache from scratch (needs a key)

Create a gitignored `.env` file containing `OPENAI_API_KEY=<your key>`, then:

```bash
set -a; source .env; set +a
.venv/bin/python src/run.py          # repopulates cache/llm.json
```

Results then reproduce from the committed cache with no key.

## Layout

```
src/generate_data.py   seeded synthetic Plaid transactions + ground truth
src/keyword_engine.py  the 13-group keyword engine (deliberately imperfect)
src/reviewer.py        two-stage: Luna triage (all) + Terra adjudication (flags)
src/cache.py           single-file cache keyed by sha256(model + prompt)
src/features.py        per-business features + offer rule
src/sensitivity.py     mislabel-sensitivity analysis (Part 2)
src/run.py             orchestrates the pipeline and writes the report
```
