# Dhruva

**Every payments team already has a review queue, and fills it by sorting on risk score or on
transaction size. At the queue sizes real teams actually run, those policies lose money.**

Measured on IEEE-CIS (590,540 card-not-present transactions, 3.4% fraud), held out temporally
with a 7-day label-delay window. Net benefit against a per-transaction cost-optimal Bayes
threshold (₹3,752,646, no queue), 5 seeds. **Every policy escalates the same volume** — only the
choice of cases differs.

| queue policy | 1% capacity | 2% | 5% | 10% |
|---|---|---|---|---|
| **nearest the cost-optimal cut** *(ours)* | **+219,440** | **+405,514** | **+798,331** | **+1,072,836** |
| most suspicious first — *the obvious policy* | **−89,329** | **−15,091** | +577,447 | +1,038,038 |
| biggest amount first — *very common in practice* | +1,899 | +108,327 | +128,600 | +63,451 |
| most rupees at stake | **−87,962** | **−75,921** | +117,620 | +101,915 |

Advantage over the **best rival at each capacity**: 5.8% (1%) · **7.9% (2%)** · 5.9% (5%) ·
0.9% (10%). It **peaks at 2% and collapses by 10%** — at a tenth of traffic under review, sorting
by score nearly catches up. No merchant reviews a tenth of their traffic.

## What this is not claiming

- **Not that escalation is new.** Every team escalates.
- **Not novelty in the method.** The winning rule is one line. The contribution is the
  measurement, the negative result, and the blindness map.
- **Not that conformal prediction is our method.** It finished second-worst of four signals.
- **Not "28% of loss saved."** That compared against a baseline with no queue at all, which nobody
  runs. It is retired, and the shrinkage to 6–8% was correct.

## Start here

| Read | Why |
|---|---|
| [`RESULTS.md`](RESULTS.md) §0 | the result, on one page, with the standard metrics up front |
| [`START_HERE.md`](START_HERE.md) | run it and present it, assuming no knowledge of the code |
| [`RUNBOOK.html`](RUNBOOK.html) | six-minute script and the questions, with answers |
| [`PROTOCOL.md`](PROTOCOL.md) | what was decided *before* any result existed |
| [`RESULTS.md`](RESULTS.md) §8, §10 | threats to validity, and the "never say this" table |

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -q              # 22 passed
open app/dashboard.html                 # or just double-click it
```

Full reproduction steps, including the two blocks that do **not** reproduce, are in
[`RESULTS.md`](RESULTS.md) §12.

## The deployable surface

`dhruva/gate.py` — three lines, no retraining, and **no labels required to fit**: the escalation
cutoff is a quantile of an unlabelled ranking, so it re-fits on recent traffic without waiting for
chargebacks.

```python
gate   = Gate.fit(cal_scores, cal_amounts, capacity=0.02)   # no labels used
action = gate.decide(score, amount)                         # APPROVE / REVIEW / BLOCK
record = gate.explain(score, amount)                        # audit trail per decision
```

Measured **p50 14.6 µs / p99 24.1 µs** per decision — the gate's own cost, on top of whatever the
base scorer costs, which we did not measure and which dominates.

## The record

This project was designed around conformal prediction. A kill test was pre-registered; it fired,
and a one-line rule beat conformal 22× (p = 0.0020). The project was reframed around what the
data supported.

- Of five hypotheses: **two supported, two refuted, one supported only in part**; two never tested.
- **One of our own headlines was retracted** after it was found to be scoring itself on the cells
  it had calibrated on.
- **External validation failed.** Below ~0.1% prevalence the method does not work at all.
- **Our own baseline is 0.6% favourable to us**, which we found by sweeping the test set
  ourselves and disclosed (§0b).
- **Two claims have no code behind them** and are marked as such: `band`'s ±50% cost sweep was
  never run, and Block 11 has no committed script.

The method the project was named after lost, and the headline shrank from 28% to 7.9% under
scrutiny. That record is the point, not a blemish on it.

## Data

Not in this repository. IEEE-CIS must be fetched separately:

```bash
python scripts/fetch_data.py
```

Expects `train_transaction.csv` (683 MB) and `train_identity.csv` (27 MB) outside the repo. ULB
must come from the **raw ARFF** — OpenML flags `Time` as `row_id_attribute`, so `fetch_openml`
silently drops it and the chronological split has nothing to sort on.

---

Built for the Razorpay AI Buildathon, Track 02 (AI Risk Manager).
