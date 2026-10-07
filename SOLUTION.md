# SOLUTION: Fundo AI Engineer Challenge (v2)

A two-stage LLM reviewer of an imperfect keyword labeling engine, with measured
credit impact. v1 was a single Luna pass; v2 adds a Terra adjudication stage on
the flagged subset.

## Scope

**Code (runnable):**
- Synthetic Plaid-shaped dataset with ground-truth labels (10 businesses, 90
  days, ~1,850 transactions).
- Deliberately imperfect 13-group keyword engine with precedence and a
  business/personal flag.
- Two-stage reviewer: GPT-6 Luna triages every transaction; GPT-5.6 Terra
  re-reviews only the flagged subset to confirm or overturn.
- Credit-impact compute: per-business features and the offer rule, for
  truth / legacy / v1 / v2 labels.
- A measured report: revenue dollar error and reviewer behavior vs truth.

**Analysis and writeup:**
- Credit impact (Part 2): mislabel sensitivity, false-label costs, the no-NSF-fee
  bank, and 61-day histories.
- Production proposal (Part 3): shadow rollout, input shift, reproducibility, and
  underwriters in the loop.

**Left out, on purpose:** a cheaper discriminative jev model (a v3 idea) was
explored and set aside because the current model was already strong at a reasonable cost. 

## Data

Generated, not sourced: building it is part of the test. Each transaction is
born with a correct label; the keyword engine then mislabels some. This is the
only way to report a *measured* dollar error. Cases deliberately included:
noisy ACH descriptions, counterparty ambiguity (`SQUARE INC` vs
`SQUARE CAPITAL`), NSF phrasings outside the keyword list, hard negatives (a
large legitimate invoice that looks like a loan), and untrusted counterparty text.

## The keyword engine and its limitations

Simple token matching with a precedence order; ~92% accurate. We make it
imperfect through the inherent **limitations** of keyword matching, not planted
bugs: a more honest and defensible stand-in for a legacy engine, and still
"deliberately imperfect" as the brief asks. Four limitations:
1. **Incomplete vocabulary:** a fixed keyword list misses unlisted phrasings,
   so an NSF written as `RETURNED ITEM FEE` / `NON-SUFFICIENT FUNDS` is missed.
2. **No counterparty disambiguation:** nothing separates `SQUARE CAPITAL` (a
   loan) from `SQUARE INC` (revenue), so the loan slips through as revenue.
3. **Blunt matching:** generic `TRANSFER` over-matches `STRIPE TRANSFER`, a
   real payout, miscalling it an internal transfer.
4. **No punctuation handling:** matching is token-based and does not normalize
   punctuation, so `OVERDRAFT-FEE` isn't recognized and the fee is missed
   (undercounting overdrafts). The same blind spot harmlessly spares a noisy
   `...DESCR:TRANSFER` Shopify payout from the blunt-match error in (3).

## The two-stage reviewer, and the model/code boundary

The models are reviewers, not relabelers.

- **Stage 1 (Luna triage, every transaction).** The fast, cheap model sees the
  transaction and the engine label and returns `agree`/`doubt` (+ corrected
  group, business/personal, reason). It is deliberately high-recall: it
  over-flags rather than miss, so stage 2 mostly needs to *prune* false flags.
- **Stage 2 (Terra adjudication, flagged subset only).** The stronger reasoning
  model sees the engine label *and Luna's suggestion* and confirms or overturns,
  run at low reasoning effort to keep its cost small. Running it only on the ~190
  flags (not all ~1,850 txns) keeps cost tiny while putting the strong model
  exactly where the hard calls are.

**Confidence as scored criteria (not a guess).** Terra scores four criteria 0–1
(counterparty clarity, direction consistency, group fit, evidence strength), and
the confidence is their **mean, computed in code**. This makes the judgment
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
| v1 (Luna only) | **$12,386** | 152 | 42 | 0 |
| v2 (Luna + Terra) | **$898** | 152 | 4 | 0 |

v2 cuts revenue error **98% vs legacy and 93% vs v1**. Terra overturns almost all
of Luna's false flags (42 → 4) while keeping every good catch, and every
business's offer now matches truth (e.g. the engine wrongly offered business 04
and business 08 ~$33–40k on an NSF undercount; both correctly return to $0).

**What did not work (v1):** the first prompt listed the 13 group *names* with no
definitions. Luna invented semantics and reclassified ~620 payment-processor
deposits (real revenue) as "Not average monthly revenue", *tripling* error to
$128k. A one-line glossary per group, stating explicitly that processor payouts
are revenue, brought it to $12,386. Luna's remaining weakness was over-flagging
(42 false flags); the Terra stage is what removed it.

(GPT-6 Luna at temperature 0 is only best-effort deterministic, so separate live
runs vary slightly; the committed cache is the fixed, reproducible result.)

## Credit impact: how much mislabels move the offer (Part 2)

`src/sensitivity.py` takes the correct labels, makes a share of them wrong, and
measures how far each business's offer moves. The same number of mistakes is
placed two ways: *uniform* (any transaction, chosen at random) and
*offer-relevant* (only the labels that feed the offer: revenue deposits and
payments to other funders). Results are averaged over 25 runs.

| placement | mislabel rate | transactions wrong | avg. change in monthly revenue (per business) | avg. change in offer (per business) | businesses crossing the NSF>5 cut-off |
|---|---|---|---|---|---|
| uniform | 2% | 37 | $516 | $1,534 | 0.4 |
| uniform | 5% | 93 | $1,381 | $4,373 | 1.1 |
| uniform | 10% | 186 | $2,896 | $7,524 | 1.9 |
| offer-relevant | 2% | 37 | $1,190 | $1,126 | 0.2 |
| offer-relevant | 5% | 93 | $3,220 | $5,166 | 1.1 |
| offer-relevant | 10% | 186 | $6,138 | $9,551 | 2.2 |

Two findings. First, monthly revenue is about twice as sensitive to mistakes on
revenue and other-funder labels as to random mistakes, at every rate. Second,
the offer moves sharply under random mistakes as well: at 2% it moves even more
than under the offer-relevant placement. The reason is the rule that sets the
offer to zero once the NSF count passes five: a random mistake can relabel a
transaction as an NSF and cross that cut-off, and this single step overrides the
revenue effect.

The conclusion: a headline mislabel rate on its own tells nothing about risk.
What matters is whether the mistakes land on the labels that drive the offer:
the NSF count and its cut-off first, then the revenue total and payments to other
funders. Monitoring those specific labels is reliable; tracking an overall error
rate is not.

## Credit impact: false revenue vs. false active-advance labels (Part 2)

Both labels feed the offer, but through different terms, so they cost different
amounts and move risk in different directions.

**Direction.** A revenue label set too high raises average monthly revenue and
overstates the offer; set too low, it understates the offer. An active-advance
label set too high (more payments to other funders than real) understates the
offer; missed or set too low, it overstates the offer.

**Why the amounts differ.** Revenue enters the offer as `1.2 × (revenue ÷ 3
months)`, so each mislabelled revenue dollar moves the offer by `$0.40`. Payments
to other funders enter as `20 × (payments ÷ 90 days)`, so each mislabelled
active-advance dollar moves the offer by `$0.22`. A revenue dollar is therefore
about 1.8 times as costly as an active-advance dollar. Revenue deposits are also
larger and far more common. In this data the average revenue deposit is $1,109
and the average active-advance payment is $245, so one false revenue label moves
the offer by about **$444**, against about **$54** for one false active-advance
label, roughly eight times as much.

**Which way the risk runs.** The dangerous direction is overstating the offer,
which leads to lending more than the business can support and lending on top of
existing advances. The offer is overstated in two cases: revenue labelled too
high, and active advance missed or labelled too low. Both make the business look
healthier or less indebted than it is. Understating the offer only costs a lost
deal. The review stage should therefore guard hardest against false revenue and
missed active advance.

## Credit impact: a bank that charges no NSF fees (Part 2)

When a bank charges no NSF fees, the NSF count is always zero, whatever the
business does. The model cannot tell this empty zero apart from a real zero
earned by a healthy account, so it reads the record as clean and gives the
business credit it has not earned. The result is that the model under-rates the
risk of businesses at no-fee banks and tends to offer them too much: the
dangerous, over-lending direction.

The fix is to add an indicator that records whether the bank charges NSF fees.
This lets the model treat a zero NSF count as meaningful only when the bank
actually charges fees, and disregard it otherwise. For this to work the model
must be allowed to combine the indicator with the NSF count, so that a zero at a
no-fee bank no longer counts as a sign of health. Building a separate model for
each type of bank would also work, but it splits the data into smaller groups
and needs many businesses in each; the indicator is simpler and learns from all
the data, so it is the better default unless no-fee banks make up a large share
of applicants.

## Credit impact: 61 days of history when the model expects 90 (Part 2)

**What breaks.** Totals and counts grow with time, and the current code divides
by a fixed 90 days (3 months), so a 61-day history understates monthly revenue
and the daily funder payment. The fix is one general model that is given the
number of days as a variable, divides every total by the actual number of days,
and is trained on histories of different lengths, built by trimming the 90-day
histories to shorter ones, so the same business can appear once as a 60-day row
and once as a 90-day row, each carrying its day count:

| business | number_of_days | avg_monthly_revenue | nsf_per_90_days |
|---|---|---|---|
| business 01 | 90 | 29,600 | 6 |
| business 01 | 60 | 29,900 | 4 |
| business 02 | 90 | 32,400 | 2 |

(The 60-day row for the same business gives a close but noisier estimate: fewer
days, so the NSF figure is less settled.) One rule needs special care: the
`NSF > 5` cut-off counts raw NSFs, so a short history shows fewer and can slip
under the limit (4 NSFs in 61 days is about 6 over 90 days), so the cut-off
should use an NSF count scaled to 90 days, not the raw number.

**How to detect it.** Record the number of days of history on every application
and watch how it changes over time, so a rise in short histories is visible.
Also watch the average input values for a steady fall: for example, if the
average NSF count across new applications drops from about 4 to about 2 over a
short period, shorter histories are a likely cause. Very short histories can be
sent for a human review.

## Production proposal (Part 3)

**Shadow and the promotion gate.** The pipeline runs the keyword engine and the
reviewer side by side and logs every case where the reviewer would change the
engine's decision, with the dollar effect on the offer, without touching the
live decision. Underwriters review those logs later, to improve the pipeline,
not to approve each release. The reviewer is promoted to change live decisions
on an objective bar: its logged changes show a stable, bounded dollar impact and
it passes the golden test set. Production has no ground truth, so the bar uses
impact and the golden set, not dollar error.

**Catching a silent input shift after a retrain.** The risk model's inputs are
the features the pipeline produces (monthly revenue, NSF count, high-risk share,
funder payments). Each engine and reviewer version is pinned, and after any
retrain the new version re-scores a fixed reference sample; if the feature
distributions or the label mix move meaningfully against the previous version,
that shift is logged so it is visible. A retrain is not necessarily bad; the
point is that a change in the risk model's inputs must not go unnoticed.

**Reproducing a past decline.** The pipeline is deterministic and the model
responses are cached and versioned in git, so a decision replays exactly from
the same inputs and code. To reproduce a specific past decline after a later
label fix, a record is stored per decision: a snapshot of the input
transactions, the code version, the model id, and the labels and offer produced.
Re-running that version on that snapshot reproduces the original decline, kept
separate from the new labels; nothing is overwritten.

**Underwriters in the loop.** Underwriters review a sample of the reviewer's
flags and mark agree or correct, with a short reason. That feedback flows back
three ways: recurring mistakes are added to the model instructions; stable,
clear-cut rules are enforced in code after the model; and the hardest,
business-critical cases become a golden test set that every new version must
pass before promotion, so a fix for one case cannot quietly break others.

## Determinism

The dataset is seeded and committed; the engine is pure; the LLM cache is keyed
on `sha256(model + prompt)`. A clean checkout replays the committed cache with
no API key and identical output. (OpenAI's `seed` is best-effort; the cache is
the actual guarantee.)

## Cost

Two models, both cached (1,745 Luna + 169 Terra responses in `cache/llm.json`):

- **Luna** ($0.10 / $0.50 per M): one full triage pass ≈ **$0.07** (measured).
- **Terra** ($2 / $12 per M, `reasoning_effort=low`): 169 flagged calls ≈
  **$0.08** (measured).

A full from-scratch run costs about **$0.15** in total (≈$0.07 Luna plus $0.08 Terra).
Reproducing from the committed cache costs **$0**. Restricting Terra to the
flagged subset keeps the stronger model affordable, and total spend stays far
under the $10 cap.

## Tools used

Claude Code (an AI coding assistant) was used to implement the pipeline and run
the experiments. The design, methods, thresholds, and the conclusions in this
document are the author's, reached by directing that work and verifying every
result against the pipeline's output.
