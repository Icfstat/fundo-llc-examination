# Fundo AI Engineer Challenge — Requirements

Source: https://github.com/Fundo-LLC/fundo-take-home/blob/main/ai-engineer-challenge/README.md

## Objective and scope

Build an LLM reviewer of an imperfect keyword transaction-labeling engine. Flag doubtful labels, propose corrections, quantify their impact on funding decisions, and describe production readiness.

Select a defensible scope; document omitted work and why. The quality of decisions matters more than the number of features implemented. These requirements describe outcomes, not architecture or implementation choices.

## Data and legacy engine

- Obtain data in Plaid transaction format: approximately 10 businesses, 90 days per business, and a couple of thousand transactions overall. Use Plaid Sandbox, synthetic data, or both; no real customer data.
- Consult Plaid documentation for fields, categories, and amount sign conventions. Include funding-relevant cases, noisy descriptions (e.g., `ACH CREDIT 0423 SQ *JOES TACOS`), counterparty ambiguity (`SQUARE INC` deposits are revenue; `SQUARE CAPITAL` is a loan), punctuation-related keyword failures (a keyword containing punctuation can silently never match), hard negatives, and untrusted counterparty text.
- Build a small, deliberately imperfect keyword engine with precedence rules and a business/personal flag. Support these 13 groups:
  - Not average monthly revenue
  - NSFs
  - Overdraft
  - Internal transfer
  - UCC
  - Active advance
  - Auto deposit
  - Revenue verification
  - High risk — gambling
  - High risk — bankruptcy
  - High risk — debt settlement payments
  - High risk — garnishment
  - High risk — other
- A transaction is revenue only if it is a business credit and no excluding group matched.

## Reviewer and evaluation

- Review each transaction's legacy label. For doubtful labels, return the proposed group, business/personal classification, revenue yes/no, confidence, and a reason readable by an underwriter in five seconds.
- Evaluate monthly revenue error in dollars per business after corrections, unnecessary flags on hard negatives, and behavior on untrusted description text. Examine concrete reviewer mistakes.
- State which changes the model may propose and which responsibilities stay in code. Address invalid model output and provider outages.

## Credit impact

- Compare features before and after corrections for each business: average monthly revenue, revenue share of total deposits, NSF and overdraft counts, high-risk share of debits, and other funders' daily payments.
- Compare offers using the supplied rule, or justify an alternative:
  `offer = 1.2 × average monthly revenue − 20 × other funders' daily payments`; offer is zero when NSF count exceeds 5.
- Show how small mislabel rates, such as 2%, 5%, and 10%, affect features and offers. Explain which errors matter and the direction and different costs of false revenue and false active-advance labels.
- Answer in one paragraph each: what zero observed NSFs means at a bank charging no NSF fees; what breaks when production history is 61 days while training used 90 days, and how to detect it.

## Production proposal

Provide one page, with no production implementation required, covering shadow operation and the gate for changing live decisions; shifts in risk-model inputs following keyword/classifier changes; reproduction of an original decline after later label changes and the records needed; underwriter involvement and feedback.

## What is evaluated

- It runs, and the output reproduces from the committed cache.
- Review quality: dollar error, hard negatives, and specific errors examined — not just an aggregate score.
- Credit judgment: which mislabels move risk, in which direction, and why.
- Model/code boundary: what goes to the model and what stays in code.
- Production thinking: shadow rollout, input drift, reproducibility, human in the loop.
- Safety: untrusted text in the prompt, invalid model output, provider outages.
- Simplicity: the smallest thing that works. Agent frameworks and vector databases need a reason to exist.
- An honest gap costs less than a confident guess — state what is missing rather than rushing it.

## Execution and deliverables

- Any language and LLM provider/model are allowed; justify the model choice. One documented command runs the solution, with any required API key supplied through an environment variable.
- Commit LLM responses as a cache. A clean checkout must regenerate the submitted output from cache without an API key and with the same results.
- Keep total LLM spending below US$10 and report actual spending.
- Deliver code for the selected scope, `README.md` with ordered copy-paste execution and cache commands, and a 2–3-page `SOLUTION.md`.
- `SOLUTION.md` must cover scope and omissions; numerical results marked measured or estimated; model/prompt choices and unsuccessful attempts; model/code boundary; credit-impact answers; production proposal; and tools used, including AI assistants and how they were used.
- Submit the repository link. Be prepared to defend decisions, explain reviewer errors, process supplied transactions, extend the code live, and explain and verify AI-written work in a 60-minute debrief with two engineers.

## Definitions requiring explicit assumptions

The brief does not supply keyword lists, precedence order, complete group semantics, the set of revenue-excluding groups, or exact aggregation conventions. State the definitions adopted for evaluation references, unmatched transactions, monthly revenue, daily funder payments, feature denominators, mislabel experiments, and applying proposed corrections. Identify these as submission assumptions rather than Fundo-provided rules.

### Adopted assumptions (v1)

Submission assumptions, not Fundo rules:

- **Plaid sign convention:** `amount > 0` is money out of the account (debit); `amount < 0` is money in (credit).
- **Evaluation reference:** the generated ground-truth label on each transaction. Error is measured against it.
- **Revenue-excluding groups:** all 13 groups exclude revenue. Revenue = business AND credit AND no group matched.
- **Unmatched transactions:** a transaction matching no group gets group = none; a business credit with no group is revenue.
- **Precedence:** highest-priority group wins when several match, in the order listed in `src/keyword_engine.py` (risk/negative flags, then obligations, then transfers/verification, then catch-alls).
- **Average monthly revenue:** revenue dollars over the 90-day window ÷ 3 months.
- **Daily funder payments:** Active-advance debit dollars ÷ 90 days.
- **Feature denominators:** total deposits = all credit dollars; total debits = all debit dollars (from the signed amount, label-independent).
- **Applying proposed corrections:** a correction is applied only when the reviewer returns `verdict = doubt`; otherwise the legacy label stands.
- **Mislabel experiments:** deferred to the next pass (not in v1).
