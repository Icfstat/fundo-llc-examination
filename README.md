# Fundo AI Engineer Challenge — v2

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

## Setup

```bash
pip install -r requirements.txt
```

Models (OpenAI API): **GPT-6 Luna** (`gpt-6-luna`) — cheap, high-throughput — for
the full triage pass; **GPT-5.6 Terra** (`gpt-5.6-terra`) — stronger reasoning —
for the small flagged subset only.

## Run it

```bash
# 1) First run: populates the LLM response cache. Needs a key.
export OPENAI_API_KEY=sk-...
python src/run.py

# 2) Commit the cache so the output reproduces without a key.
git add cache/llm.json && git commit -m "Add LLM response cache"
```

## Reproduce from cache (no API key)

```bash
unset OPENAI_API_KEY
python src/run.py        # replays cache/llm.json, identical output
```

The committed data (`data/transactions.json`) and cache (`cache/llm.json`) make a
clean checkout reproduce the report deterministically. The report is written to
`out/report.md`.

## Layout

```
src/generate_data.py   seeded synthetic Plaid transactions + ground truth
src/keyword_engine.py  the 13-group keyword engine (deliberately imperfect)
src/reviewer.py        two-stage: Luna triage (all) + Terra adjudication (flags)
src/cache.py           single-file cache keyed by sha256(model + prompt)
src/features.py        per-business features + offer rule
src/run.py             orchestrates the pipeline and writes the report
```
