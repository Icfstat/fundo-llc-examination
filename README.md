# Fundo AI Engineer Challenge — Baseline (v1)

An LLM **reviewer** of an imperfect keyword transaction-labeling engine. The
reviewer reads each transaction and the engine's label, flags the ones it
doubts, proposes a correction, and we measure what those corrections are worth
to a funding decision.

See `docs/specs.md` for the requirements and the adopted assumptions, and
`SOLUTION.md` for the writeup.

## Pipeline

```
generate_data.py  ->  keyword_engine.py  ->  reviewer.py  ->  features.py  ->  report
   (truth labels)        (legacy labels)      (corrections)    (offer rule)
```

Every transaction carries three label layers so error is **measured**, not
claimed: `truth` → `legacy` (engine) → `corrected` (reviewer).

## Setup

```bash
pip install -r requirements.txt
```

Model: **GPT-6 Luna** (`gpt-6-luna`) via the OpenAI API — a cheap,
high-throughput model that fits a high-volume, simple per-transaction review.

## Run it

```bash
# 1) First run: populates the LLM response cache. Needs a key.
export OPENAI_API_KEY=sk-...
python src/run.py

# 2) Commit the cache so the output reproduces without a key.
git add cache/llm && git commit -m "Add LLM response cache"
```

## Reproduce from cache (no API key)

```bash
unset OPENAI_API_KEY
python src/run.py        # replays cache/llm/, identical output
```

The committed data (`data/transactions.json`) and cache (`cache/llm/`) make a
clean checkout reproduce the report deterministically. The report is written to
`out/report.md`.

## Layout

```
src/generate_data.py   seeded synthetic Plaid transactions + ground truth
src/keyword_engine.py  the 13-group keyword engine (deliberately imperfect)
src/reviewer.py        one cached GPT-6 Luna call per transaction
src/cache.py           file cache keyed by sha256(model + prompt)
src/features.py        per-business features + offer rule
src/run.py             orchestrates the pipeline and writes the report
```
