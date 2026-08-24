# Three things a risk team can do on Monday

**Measured on IEEE-CIS, 110,377 held-out card-not-present transactions, 3.4% fraud. None of this needs my code deployed. Two of the three need nothing from me at all.**

---

## 1. Re-rank the review queue by distance to the cut, not by risk score

Your analysts can review some small share of transactions. Whatever fills that queue today is almost certainly sorted by risk score, or by transaction size. **At the queue sizes a real team staffs, both lose money.**

| how the queue is filled | net vs no queue, @2% capacity |
|---|---|
| most suspicious first | **−₹15,091** |
| most rupees at stake | **−₹75,921** |
| biggest amount first | +₹108,327 |
| **nearest the cost-optimal cut** | **+₹405,514** |

**Expected recovery, measured against the best of those existing policies — not against doing nothing:**

| your review capacity | loss recovered |
|---|---|
| 1% of transactions | **5.8%** (+₹217,542) |
| 2% of transactions | **7.9%** (+₹297,187) |

**Why score-sorting loses.** It sends analysts to cases the model is *already confident about*. A human costs ₹40, spends four minutes, and changes no decision. The cases worth a human are the ones sitting near the decision boundary, where the model is genuinely torn.

**This is a sort-order change.** No retraining, no new features, no model call. p50 14.6 µs per decision.

**One caveat that decides whether it is worth your time:** the advantage peaks at 2% capacity and falls to **0.9% at 10%**. If you can review a tenth of your traffic, sorting by score nearly catches up and this is not worth doing. Almost nobody can.

---

## 2. Retrain and staff where the losses actually concentrate

This requires **adopting none of my code**. It is a measurement you can repeat on your own data this week.

| segment | share of traffic | error rate | share of ₹ lost | concentration |
|---|---|---|---|---|
| **ProductCD C** | 10.3% | **10.61%** | 19.4% | **1.9×** |
| **credit cards** | 23.2% | **6.65%** | 38.0% | **1.6×** |
| **largest amount decile** (₹270–5,367) | 10.0% | 5.48% | 20.8% | **2.1×** |
| ProductCD W *(for contrast)* | 79.1% | 2.42% | 68.5% | 0.9× |

**Product C carries 4.4× the error rate of product W. Credit carries 2.6× debit.**

Three concrete uses: **target retraining** at product C rather than uniformly; **add features** where the error rate is 4× your average, not where volume is highest; **staff the queue** with reviewers who know the segments carrying 2× their share of losses.

The method is borrowed from [arXiv:2607.06605](https://arxiv.org/abs/2607.06605), which localises a model's confident errors to specific molecular scaffolds in drug discovery. The payments analogue is business segments.

---

## 3. Measure your real analyst capacity — then re-validate on your own data

**Do this before anything above.** Every number here is conditional on two things you have and I do not: your real review capacity, and your real analyst accuracy.

The re-ranking is six lines on top of whatever scorer you run:

```python
c_fp = 0.25 * amount + 250          # your margin and goodwill numbers, not mine
c_fn = amount + 1500                # your chargeback fee
t     = c_fp / (c_fp + c_fn)        # per-transaction cutoff; it MOVES with amount
stake = np.maximum(p * c_fn, (1 - p) * c_fp)
order = -np.abs(p - t) * 1e6 + stake / 1e6      # distance to cut, tie-broken by rupees
queue = np.argsort(-order)[:int(capacity * len(p))]
```

Then compare realised rupee cost against your current queue order on a held-out window. **If it does not beat your existing policy on your data, do not adopt it.** The apparatus is about 300 lines and the experiment is an afternoon.

**Two measurements to take while you are there:**

- **Your actual review capacity**, as a share of transactions. It is an operational fact, not a parameter — and every conclusion here depends on which column of the table you are in.
- **Your actual analyst accuracy.** I assumed 95% and never measured it. This matters more than it sounds: the "more fraud caught *and* fewer good customers blocked" result **holds at 90% accuracy and inverts below it.** At 80%, adjusting for analyst error, the false-positive rate rises to 2.74% against a baseline of 1.85%. The rupee advantage of the re-ranking survives all the way down to 70% — and in fact *grows*, because a weak analyst does the most damage when you send them cases the model had already settled — but the dominance claim does not.

---

## What this memo is **NOT** claiming

| Not claimed | The honest version |
|---|---|
| ❌ "This will save Razorpay X rupees" | One merchant profile, one dataset, **declared** cost constants. The transferable thing is the *method and the shape*, not the number. Measure your own capacity, price your own errors, check whether the curve bends the same way. |
| ❌ Anything about Vulcan | **I have never seen its scores and cannot get them.** The effect grows as the scorer improves across three base models — but that is n = 3 and two of the three are broken models. Directional, not proof. |
| ❌ Algorithmic novelty | The winning rule is **one line**. A learned rejector with the same inputs, trained on realised rupee value, **did not beat it** — and lands 0.0165 points from a statistical tie, so the honest reading is *level, never ahead*. The contribution is the measurement, not the method. |
| ❌ That this is verified in production | It cannot be. A transaction you block never acquires an outcome, so its true label is unobservable — the **selective labels** problem. Every number here is an offline replay, and no offline study escapes that, mine included. |
| ❌ General applicability | **Below ~0.1% fraud prevalence it does not work at all.** External validation on a second dataset failed at every setting, and that failure is in the write-up rather than omitted from it. |
| ❌ "28% of loss saved" | **Retired.** That compared against a baseline with no review queue, which nobody runs. I cut it to 6–8% myself when I noticed. |

**Full boundaries: [`RESULTS.md`](RESULTS.md) §8 (threats to validity), §9b (analyst-accuracy sweep), §10 (the "never say this" table).**
