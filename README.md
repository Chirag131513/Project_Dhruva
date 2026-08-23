# Project Dhruva

**Your fraud model is right 98% of the time across nine tenths of your traffic. That is a good
model. But its mistakes are not spread evenly — and the review queue your analysts work is filled
in a way that systematically misses them.**

Dhruva is a routing layer that sits on top of whatever scorer you already run and decides *which
transactions a human should look at*. Three lines to integrate. No retraining. 14.6 µs per
decision.

I measured what that choice is worth on 590,540 real card-not-present transactions. **At the
queue sizes real teams actually staff, the two most common ways of filling a review queue lose
money.**

---

## Why this matters here specifically

Razorpay's own published material describes the exact constraint this addresses. Vulcan is
reported as identifying **5× more fraudulent or disputed transactions "without increasing the
number of alerts"** ([Aug 2026](https://www.dqindia.com/news/razorpay-vulcan-8x-fraud-detection-baseline-12398348)).
That phrase *is* an alert budget: more fraud found, same number of cases a human can look at.

And the human side is already saturated. Razorpay's own engineering team reports that merchant
risk review ran at **10,000–12,000 manual reviews a month, roughly 700–800 human hours**, before
they automated it ([Bumblebee](https://dev.to/razorpaytech/meet-bumblebee-agentic-ai-flagging-risky-merchants-in-under-90-seconds-2nlf)).
*That* queue is merchant websites, not transactions — a different queue from the one this project
routes — but it shows the shape of the constraint: **analysts are finite and the queue is already
full.**

So the question is not *should you review transactions* — you already do. It is **which ones**,
and that turns out to be worth real money:

| If your team fills its queue by… | at 2% review capacity |
|---|---|
| sorting on risk score — *the most common policy* | **loses ₹15,091** |
| sorting on rupees at stake | **loses ₹75,921** |
| sorting on transaction size | makes ₹108,327 |
| **sorting on distance to the cost-optimal cut** *(this project)* | **makes ₹405,514** |

Sorting by risk score sends analysts to cases the model is **already confident about**, where a
human costs ₹40 and changes no decision. The cases actually worth a human are the ones sitting
near the decision boundary.

## What you get

- **6–8% of realised fraud loss recovered**, measured against the queue policy you are already
  running — not against a strawman. It peaks at **7.9%** at 2% review capacity.
- **More fraud caught *and* fewer good customers blocked, at the same headcount.** At 10%
  capacity: fraud recall **49.7% → 73.4%** while the false-positive rate **halves, 1.85% → 0.86%**.
  A threshold cannot do that — it can only trade one against the other. Escalation escapes the
  trade-off because a human *resolves* the case instead of the system guessing.
- **A map of where your model is blind** — which costs you nothing and requires adopting none of
  my code. See below.
- **An audit record for every decision**, which matters if anyone has to explain a block.

## Drop-in integration

```python
from dhruva.gate import Gate

gate   = Gate.fit(scores, amounts, capacity=0.02)   # no labels required
action = gate.decide(score, amount)                 # APPROVE / REVIEW / BLOCK
record = gate.explain(score, amount)                # full audit trail
```

| | |
|---|---|
| **Latency** | p50 **14.6 µs**, p99 24.1 µs per decision (0.08 µs batched) |
| **Retraining** | none — it consumes your existing scores |
| **Labels needed to fit** | **none**. The cutoff is a quantile of an *unlabelled* ranking |
| **Tuning** | one number: how many cases your team can review |

That "no labels" property is the operationally important one. Chargeback labels arrive weeks
late, so anything that needs them cannot respond during the window that matters. Dhruva re-fits on
last week's traffic without waiting for a single dispute to resolve.

## Where your model is blind

This part requires adopting nothing of mine. I localised the model's confident errors to business
segments — the same method [arXiv:2607.06605](https://arxiv.org/html/2607.06605v1) uses to localise
errors to molecular scaffolds:

| segment | share of traffic | error rate | share of ₹ lost | concentration |
|---|---|---|---|---|
| **ProductCD C** | 10.3% | **10.61%** | 19.4% | **1.9×** |
| **credit cards** | 23.2% | **6.65%** | 38.0% | **1.6×** |
| **₹270–5,367** (largest decile) | 10.0% | 5.48% | 20.8% | **2.1×** |
| ProductCD W *(for contrast)* | 79.1% | 2.42% | 68.5% | 0.9× |

**Product C carries 4.4× the error rate of product W. Credit is 2.6× debit.** Retrain there, add
features there, staff the queue there. You can act on this table tomorrow.

## The evidence

IEEE-CIS (Vesta), 590,540 transactions, 3.4% fraud, held out **temporally** with a 7-day
label-delay window. Net benefit vs a per-transaction cost-optimal Bayes threshold (₹3,752,646, no
queue), 5 seeds. **Every policy escalates the same volume** — only the choice of cases differs.

| queue policy | 1% capacity | 2% | 5% | 10% |
|---|---|---|---|---|
| **nearest the cost-optimal cut** *(this project)* | **+219,440** | **+405,514** | **+798,331** | **+1,072,836** |
| most suspicious first | **−89,329** | **−15,091** | +577,447 | +1,038,038 |
| biggest amount first | +1,899 | +108,327 | +128,600 | +63,451 |
| most rupees at stake | **−87,962** | **−75,921** | +117,620 | +101,915 |

Advantage over the **best rival at each capacity**: 5.8% · **7.9%** · 5.9% · 0.9%.

**It peaks at 2% and collapses by 10% — and I say so myself.** At a tenth of traffic under
review, sorting by score nearly catches up. No merchant reviews a tenth of their traffic, which is
why the left of that table is the one that matters. False-positive cost is priced per transaction
(`c_FP(x) = 0.25·amount + ₹250`), not as a flat constant.

## What I am not claiming

- **Not that escalation is new.** Every team escalates. The finding is that the usual way of
  choosing *what* to escalate loses money at realistic capacity.
- **Not novelty in the method.** The winning rule is one line. The contribution is the
  measurement, the negative result, and the blindness map.
- **Nothing about Vulcan.** I have never seen its scores and cannot get them. What I can show is
  that the effect *grows* as the underlying model gets better.
- **Not "28% of loss saved."** An earlier version of this claim compared against a baseline with
  no review queue at all — which nobody runs. I retired it myself and the number fell to 6–8%.

## The record

This project was designed around conformal prediction. I pre-registered a kill test that could
invalidate it, ran it, and **it fired** — a one-line rule beat conformal by 22× (p = 0.0020). I
reported that and changed the project rather than the test.

- Of five hypotheses: two supported, **two refuted**, one supported only in part.
- **One of my own headlines was retracted** after I found it was scoring itself on the cells it
  had calibrated on.
- **External validation failed.** Below ~0.1% fraud prevalence the method does not work at all.
- **My own baseline is 0.6% favourable to me** — I found that by sweeping the test set myself,
  and disclosed it.
- **Two claims once had no code behind them; both have since been measured.** `band`'s ±50% cost
  sweep was struck as unsupported, then run — no sign flips on any of the four constants,
  +₹513,576 to +₹1,409,008, landing on exactly the range that had been struck. Block 11's
  transfer table had no generating script; it was rewritten, and reproduced every field exactly.
  In both cases the number was right and the *evidence* was missing, and those are not the same
  thing. **Every block in the write-up now runs.**
- Every number here is an **offline replay**. A blocked transaction never acquires an outcome, so
  no offline study — mine included — can fully verify this in production.

The method the project was named after lost, and the headline shrank by a factor of three under
scrutiny. That record is the point, not a blemish on it.

## Run it

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -q        # 22 passed
```

Then open [`app/dashboard.html`](app/dashboard.html) — no server, just double-click it. Drag the
capacity slider to 2%.

| Read | Why |
|---|---|
| [`RESULTS.md`](RESULTS.md) §0 | the result on one page, with standard metrics up front |
| [`START_HERE.md`](START_HERE.md) | run it and present it, assuming no knowledge of the code |
| [`RUNBOOK.html`](RUNBOOK.html) | six-minute script, and the hard questions with answers |
| [`PROTOCOL.md`](PROTOCOL.md) | what was decided *before* any result existed |
| [`RESULTS.md`](RESULTS.md) §8 | threats to validity, stated rather than hidden |

**The tests need no data** — they run on synthetic fixtures, so `pytest` works the moment you
clone. For the experiments, `python scripts/fetch_data.py` pulls IEEE-CIS into `data/` (gitignored),
so a fresh clone needs no configuration. To keep the ~700 MB elsewhere, set `DHRUVA_DATA` rather
than editing `config.yaml`:

```bash
export DHRUVA_DATA=/path/to/dhruva-data
```

Full reproduction steps, **including the two blocks that do not reproduce**, are in
[`RESULTS.md`](RESULTS.md) §12.

---

Built for the Razorpay AI Buildathon, Track 02 — AI Risk Manager.
