# Project Dhruva

**A routing layer that decides which transactions your analysts should review — and a measurement showing that the two most common ways of choosing lose money at the queue sizes real teams actually staff.**

Built for the **Razorpay AI Buildathon, Track 02 — AI Risk Manager**.

---

## TL;DR for judges

> **1. The queue policy you already run loses money.**
> Every payments team has a review queue and fills it by sorting on risk score or transaction size. At 2% capacity, sorting by risk score returns **−₹15,091** and sorting by rupees at stake **−₹75,921**. Sorting by distance to the cost-optimal cut returns **+₹405,514** — an advantage of **5.8–7.9% of realised loss** over the best rival policy at 1–5% capacity. Every policy escalates the *same volume*; only the choice differs.
>
> **2. A map of where the model is blind — needs none of my code.**
> ProductCD **C** carries **4.4× the error rate** of product W (10.61% vs 2.42%) on 10.3% of traffic. **Credit** cards carry **1.6×** their share of losses; the **largest amount decile** carries **2.1×**. Retrain there, add features there, staff the queue there.
>
> **3. I pre-registered a test that could kill my own project, and it fired.**
> This was designed around conformal prediction — the method the 2026 literature is built on. A one-line rule beat it **22×** (p = 0.0020), so I abandoned it and reported the result. Conformal finished **second-worst of four** escalation signals.

**Held-out test set:** 110,377 transactions · 3,732 fraud · read once.

| base scorer (LightGBM) | PR-AUC | ROC-AUC | Precision@2% | Recall@2% | ECE |
|---|---|---|---|---|---|
| | **0.5233** | 0.8964 | **0.6803** | 0.4025 | 0.0039 |

| operating point | fraud recall | false-positive rate | review rate |
|---|---|---|---|
| cost-optimal Bayes threshold *(baseline, no queue)* | 49.68% | 1.846% | 0% |
| **deployed gate @ 10% capacity** *(at the declared 95% analyst accuracy)* | **73.45%** | **0.862%** | 10.9% |

**Both improve at once** — recall +23.8 points while false positives *halve* — because a human resolves the case instead of the system guessing. A threshold can only trade one against the other.

> **That pair is conditional, and I would rather you heard it from me.** Those figures assume analysts are right **95%** of the time — a constant I declared and never measured. Sweeping it ([§9b](RESULTS.md)): the dominance **holds at 95% and 90% and inverts below that** — at 80% accuracy the false-positive rate rises to **2.74%** against the baseline's 1.85%. The *rupee* advantage survives all the way down to 70% and in fact **grows**, but the "both improve" claim does not. **Measure your analysts before quoting this pair.**

False-positive cost is priced **per transaction**, not as a flat constant: `c_FP(x) = 0.25·amount + ₹250`.

---

## Quick start

```bash
git clone https://github.com/Chirag131513/Project_Dhruva.git && cd Project_Dhruva
python -m pip install -r requirements.txt
python -m pytest tests/ -q                 # 22 passed — needs no data
```

Then **double-click `app/dashboard.html`**. No server, no build step. Drag the capacity slider to **2%** and watch two of the four policies sit below zero.

> The tests run on synthetic fixtures, so they pass on a fresh clone with no data download. The experiments need IEEE-CIS: `python scripts/fetch_data.py` pulls it into `data/` (gitignored). To keep the ~700 MB elsewhere, set `DHRUVA_DATA` rather than editing `config.yaml`.

---

## The deployable surface

```python
from dhruva.gate import Gate

gate   = Gate.fit(scores, amounts, capacity=0.02)   # no labels required
action = gate.decide(score, amount)                 # APPROVE / REVIEW / BLOCK
record = gate.explain(score, amount)                # full audit trail
```

| | |
|---|---|
| **Latency** | p50 **14.6 µs**, p99 24.1 µs per decision (0.082 µs batched) |
| **Retraining** | none — it consumes your existing scores |
| **Labels needed to fit** | **none.** The cutoff is a quantile of an *unlabelled* ranking |
| **Tuning** | one number: how many cases your team can review |

The "no labels" property is the operationally important one. Chargeback labels arrive weeks late, so anything needing them cannot respond during the window that matters. This re-fits on last week's traffic without waiting for a single dispute.

*(That latency is the gate's own, on top of whatever the base scorer costs — which I did not measure and which dominates.)*

---

## The result

IEEE-CIS (Vesta), 590,540 transactions, 3.4% fraud, held out **temporally** with a 7-day label-delay window. Net benefit vs a per-transaction cost-optimal Bayes threshold (₹3,752,646, no queue), 5 seeds.

| queue policy | 1% capacity | 2% | 5% | 10% |
|---|---|---|---|---|
| **nearest the cost-optimal cut** *(this project)* | **+219,440** | **+405,514** | **+798,331** | **+1,072,836** |
| most suspicious first — *the obvious policy* | **−89,329** | **−15,091** | +577,447 | +1,038,038 |
| biggest amount first | +1,899 | +108,327 | +128,600 | +63,451 |
| most rupees at stake | **−87,962** | **−75,921** | +117,620 | +101,915 |

Advantage over the **best rival at each capacity**: 5.8% · **7.9%** · 5.9% · 0.9%.

**It peaks at 2% and collapses by 10% — and I say so myself.** At a tenth of traffic under review, sorting by score nearly catches up. No merchant reviews a tenth of their traffic, which is why the left of that table is the one that matters.

---

## Project structure

Fourteen numbered blocks. **Every one has a script, and every result in `RESULTS.md` comes from one of them.**

| # | Script | What it establishes |
|---|---|---|
| 0 | `block0_audit.py` | The data is real: 590,540 transactions, 24.4% carry device data |
| 1 | `block1_baseline.py` | The base model works — PR-AUC 0.5233 |
| 2 | `block2_conformal.py` | **The illusion:** 89.1% marginal coverage, **13.9% on fraud** |
| 3 | `block3_shift.py` | Hypothesis 1 **refuted** — calibration does not decay faster than ranking |
| 4 | `block4_cost.py` | The money model. Hypothesis 4 **refuted** |
| 5 | `block5_segments.py` | Which grouping works — and the **retraction** of Block 3's headline |
| 6 | `block6_amendment.py` | Amendment 1: deriving α from capacity instead of choosing it |
| 7 | `block7_alpha_sweep.py` | The α curve, and the **failed** external validation on ULB |
| 8 | `block8_agnostic.py` | The failure gets *worse* as the model gets better |
| 9 | `block9_triage.py` | **The kill test that fired** — a one-line rule beats conformal 22× |
| 10 | `block10_proofs.py` | Two premises tested. One comes back **against me** |
| 11 | `block11_concentration.py` | Error concentration across three scorers: 0.7× → 1.1× → 8.6× |
| 12 | `block12_policies.py` | **THE RESULT** — the queue-policy race above |
| 13 | `block13_rejector.py` | A **learned** rejector does not beat the one-line rule; plus the analyst-accuracy sweep |

| Support | Purpose |
|---|---|
| `fetch_data.py` | Downloads IEEE-CIS |
| `export_console.py` → `measure_gate.py` → `build_dashboard.py` | Rebuilds the dashboard (all three, in order) |
| `make_figures.py` | Rebuilds `results/figures/graph5_triage.png` |

| Module | Purpose |
|---|---|
| `dhruva/gate.py` | The deployable gate — three-line API, audit records |
| `dhruva/cost.py` | Example-dependent cost model and the Bayes decision layer |
| `dhruva/conformal.py` | Conformal calibration (the arm that lost, kept for the record) |
| `dhruva/splits.py` | Chronological split with the 7-day label-delay window |

---

## What this project is **NOT**

| Not claimed | The honest version |
|---|---|
| ❌ "28% of loss saved" | **Retired.** That measured against a baseline with *no review queue*, which nobody runs. I cut it myself. The claim is **6–8% over the policy a team already has**. |
| ❌ Algorithmic novelty | The winning rule is **one line**, and I tested that against a real opponent: a learned rejector trained on realised rupee value, using the same inputs. It **did not beat it** — landing 0.0165 points from a statistical tie, so the honest reading is *level, never ahead*. The contribution is the *measurement*, the *negative result*, and the *blindness map*. |
| ❌ "This works on Vulcan" | **I have never seen Vulcan's scores and cannot get them.** What I can show is that the effect *grows* as the scorer improves — but that is n = 3, and two of the three are broken models. |
| ❌ Conformal prediction is my method | It is a **baseline I tested and it came second-worst.** |
| ❌ A production guarantee | Every number is an **offline replay**. A blocked transaction never acquires an outcome — the *selective labels* problem. No offline study escapes it, mine included. |
| ❌ General applicability | **Below ~0.1% fraud prevalence it does not work at all.** External validation on ULB failed and that failure is written up, not buried. |

**The full boundaries are in [`RESULTS.md`](RESULTS.md) §8 (threats to validity) and §10 (the "never say this" table).**

---

## Reproducibility

| | |
|---|---|
| **Protocol** | Pre-registered and hashed **before any result existed** — `results/protocol.lock`, frozen at commit `559c8fa` |
| **Config hash** | `d38888c9d05d398c`. Scripts **refuse to run** if a frozen constant changed |
| **Amendments** | One, recorded in `config.yaml` with its prediction written down *beforehand* |
| **Tests** | 22, passing. Three of the five known bugs have **mutation-verified** regression tests; two do not, and `RESULTS.md` §7 says which |
| **Every result** | Traceable to a numbered block script and a JSON in `results/` |

Two claims once had no code behind them — `band`'s ±50% cost sweep and Block 11's transfer table. **Both have since been measured**, and in both cases the original numbers reproduced exactly. The lesson is recorded rather than tidied away: the number was right and the *evidence* was missing, and those are not the same thing.

---

## Read next

| Document | Why |
|---|---|
| [`RESULTS.md`](RESULTS.md) §0 | The result on one page, with standard metrics up front |
| [`START_HERE.md`](START_HERE.md) | Run it and present it, assuming no knowledge of the code |
| [`RAZORPAY_ACTION_MEMO.md`](RAZORPAY_ACTION_MEMO.md) | **Three things a risk team can do on Monday** — two need none of this code |
| [`RUNBOOK.html`](RUNBOOK.html) | Six-minute demo script and the hard questions, with answers |
| [`PROTOCOL.md`](PROTOCOL.md) | What was decided *before* any result existed |

---

*Two hypotheses were refuted, one of my own headlines was retracted for circularity, external validation failed, and the method this project is named after lost its own pre-registered kill test. That record is the submission, not a blemish on it.*
