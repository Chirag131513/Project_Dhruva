# Dhruva — Results

**What we set out to test, what the data said, and what we are entitled to claim.**

Dataset: IEEE-CIS Fraud Detection (Vesta), 590,540 card-not-present transactions over ~6 months,
3.4% fraud. External validation: ULB/Worldline, 284,807 transactions, 0.172% fraud.
Protocol pre-registered and hashed before any result existed — `results/protocol.lock`, commit
`559c8fa`.

---

## 1. Standing of the pre-registered hypotheses

| | Verdict | Evidence |
|---|---|---|
| **H1** calibration degrades faster than discrimination under signal loss | **REFUTED** | PR-AUC 0.5233 → 0.5109 at full masking (2.4% relative); ECE non-monotone 0.0036–0.0042. R is a ratio of noise to noise. |
| **H2** pooled conformal under-covers the fraud class | **SUPPORTED** | Marginal CP: **0.891 marginal coverage, 0.139 on fraud.** Class-conditional restores it to 0.868. |
| **H3a** conditioning restores per-cell coverage | **SUPPORTED, but not as framed** | True for **ProductCD** segments (worst cell deviation 0.083 vs 0.211 class-only). **False for the identity split** the project was built around — that arm scores 0.263, worse than doing nothing. |
| **H3b** online ACI maintains coverage under drift | **NOT TESTED** | Out of scope after H1 fell; the drift τ was meant to create proved negligible. |
| **H4** coverage restoration yields positive net rupees | **REFUTED** | At the pre-registered α=0.10 the gate costs **₹1.53M more** than a plain Bayes threshold. Sign stable across ±50% sweeps. |
| **H5** calibration approaches oracle retraining | **NOT TESTED** | Superseded: the method did not clear its own baseline, so the gap-to-oracle question never became live. |

**Two of five tested hypotheses survived. One of our own published results was retracted.**

---

## 2. The headline finding

> Marginal conformal prediction reports **89.1% coverage** on held-out IEEE-CIS while covering
> **13.9% of the fraud class.** A monitoring dashboard reading the marginal number would call
> that system healthy.

Conditioning the quantile on the class restores fraud coverage to 0.868 for 5.7 points of extra
review volume. Conditioning on the *segment* as well brings worst-cell deviation from 0.211 to
0.083.

This result needs no τ, no agent modelling, and no contested assumption. It is a property of the
real data.

---

## 3. What the method costs

At the pre-registered α = 0.10, on 110,377 held-out transactions:

| arm | cost ₹ | vs B1 | recall | FPR | legit cov | fraud cov |
|---|---|---|---|---|---|---|
| B1 per-transaction Bayes threshold | 3,718,531 | baseline | 49.7% | 1.85% | — | — |
| Pre-registered α = 0.10 | 5,417,737 | **−1,699,207** | 73.8% | 11.49% | 0.891 | 0.878 |
| Amendment 1, per-class α | 3,691,394 | +27,137 | 58.7% | 3.19% | 0.976 | 0.878 |

**Why α = 0.10 fails, structurally.** Promising 90% coverage of the *legitimate* class excludes
10% of legitimate traffic by construction. At 96.3% legitimate traffic that is ~9.7% of all
volume pushed toward block-or-review, against 2% analyst capacity — 89% of escalations were
truncated. A symmetric miscoverage budget on a 28:1 imbalanced, cost-asymmetric problem hands
almost the whole budget to the class that can least afford it.

**Amendment 1** derives the budget instead of choosing it:
`α_legit = review_cap / P(legit) = 0.02 / 0.9629 = 0.0208`, with α_fraud unchanged at 0.10.
Recorded in `config.yaml` with a prediction written **before** the run.

Counter-intuitive and worth stating: fraud is the expensive error per case, but legitimate
traffic is ~28× more common, so **in aggregate the miscoverage budget belongs mostly to the
fraud class.**

---

## 4. The claim we are entitled to make

**Not** *"this saves money."* The +₹27,137 margin is 0.73%, and its sign flips on **all four**
cost constants under ±50%:

```
fee_chargeback  -326,694 / +27,137 / +209,088
margin           +96,493 / +27,137 /  -47,204
review_cost      +71,297 / +27,137 /  -17,023
goodwill        +114,539 / +27,137 / -224,700
```

It is also capacity-sensitive by construction: +₹41k at 1% capacity, +₹27k at 2%, **−₹769k at 5%**.

> **The defensible claim:** segment-conditional conformal abstention with a capacity-derived
> per-class α is roughly **cost-neutral** against a plain per-transaction Bayes threshold, while
> additionally delivering a **stated per-segment coverage level** — 97.6% on legitimate traffic,
> 87.8% on fraud — that a bare threshold cannot state at all.

You buy auditability at approximately zero cost. Not profit.

---

## 5. External validation — failed

ULB, 0.126% fraud in TEST, segmented by amount quartile (no ProductCD available):

- The method **loses at every α in the grid.** Best net −₹31,637; −₹161,111 at the derived α,
  which is 82% of baseline cost.
- **Fraud coverage is unreportable at all 11 α values.** The calibration split holds ~40 fraud
  rows against the n≥100 floor, so no fraud quantile can be estimated and the gate effectively
  runs on one class.

**This is a boundary on applicability, not an inconvenience.** The approach needs sufficient
minority calibration data; below some prevalence it has none. The stop rule firing is the system
working, not obstructing.

---

## 6. Corrections made to our own work

**Block 3's headline was circular.** It measured coverage on the same identity cells the arm had
calibrated on — the arm was grading itself. On a neutral fine grid (ProductCD × identity × class)
identity-conditioning scores **0.263, worse than class-only's 0.211**. Retracted in `e3fee68`.

**The identity/agent framing does not survive audit.** Identity-absent rows are 98.5% ProductCD
`W`; identity-present rows are 43% `C`, 26% `R`, 23% `H`. Fraud rate differs 7.85% vs 2.09%. The
split is a product-mix and base-rate confound, not a behavioural-signal one.

**A replication check that flattered the result.** Block 7 initially declared "genuine
replication" because two argmins were within 0.03, while every ULB configuration was losing to
its own baseline. Comparing argmins is not a test of replication.

---

## 7. Bugs found (all now have regression tests)

1. `aci_update` took target *coverage* where Gibbs–Candès takes target *miscoverage* — the
   controller ran backwards and drove coverage to ~10%. **Silent in production**: the prediction
   sets still look plausible.
2. `Encoder` detected categoricals via `dtype == object`, missing pandas 3.0's `str` dtype;
   numeric coercion then nulled ~15 columns including all of block M. Nothing raised.
3. `coverage()` applied the stop rule to the evaluation cell rather than the governing
   calibration cell.
4. Block 5 let evaluation granularity follow calibration granularity.
5. `fetch_data.py` probed auth with a `whoami` subcommand that does not exist in Kaggle CLI 2.x.

---

## 8. Threats to validity

- **Single primary dataset.** IEEE-CIS is 2018–2019 US e-commerce. ULB refutes transfer to low
  prevalence; nothing tests transfer to Indian payments, which is the motivating context.
- **Cost constants are assumptions.** ₹1,500 chargeback fee, 25% margin, ₹250 goodwill, ₹40
  review, 5% analyst error. All declared, all swept, none measured from real merchant data.
- **τ is a proxy that did not bite.** Only 24.4% of rows carry identity data, so masking it is a
  no-op on three-quarters of the test set. The λ sweep was underpowered by construction.
- **"No retraining" is imprecise.** Recalibration *is* learning. The accurate statement is *no
  gradient-based refitting of the base model.*
- **Static review queue.** No backlog, no time-of-day effects, constant analyst error rate.
- **Amendment 1 is post-hoc.** Derived rather than tuned, prediction pre-recorded, and the
  pre-registered result reported alongside it every time — but post-hoc nonetheless.
- **Multiple looks.** Seven blocks, four arms, two amendable constants. Every result is reported,
  including the ones that killed hypotheses.

---

## 9. What not to say

| Don't | Do |
|---|---|
| "AI-agent traffic" | "segment-conditional calibration"; agentic commerce is motivation only |
| "error guarantee" | "target empirical coverage under stated assumptions" |
| "we save ₹X" | "roughly cost-neutral, with a stated coverage level" |
| "nobody has done this" | "we found no public work measuring this failure mode" |
| "LIVE" | "TEST REPLAY" |
| "no retraining" | "no gradient-based refitting of the base model" |

---

## 10. Reproducing

```bash
python scripts/block0_audit.py          # freeze + identity audit
python scripts/block1_baseline.py       # PR-AUC 0.523, Precision@2% 0.68
python scripts/block2_conformal.py      # the 0.891 / 0.139 result
python scripts/block3_shift.py --seeds 3
python scripts/block4_cost.py           # H4 refuted
python scripts/block5_segments.py       # Block 3 retracted
python scripts/block6_amendment.py      # Amendment 1
python scripts/block7_alpha_sweep.py    # curve + ULB failure
python scripts/export_console.py && streamlit run app/console.py
python -m pytest tests/ -q              # 22 passed
```
