# Dhruva — Results

**What we set out to test, what the data said, and what we are entitled to claim.**

Dataset: IEEE-CIS Fraud Detection (Vesta), 590,540 card-not-present transactions over ~6 months,
3.4% fraud. External validation: ULB/Worldline, 284,807 transactions (0.172% fraud overall;
**0.126% in the held-out test window**, which is the figure the calibration cells actually see).
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
| **H4** coverage restoration yields positive net rupees | **REFUTED** | At **α=0.10, identity-segmented**, the gate costs **₹1.53M more** than a plain Bayes threshold (5,248,665 vs 3,718,531). Sign stable across ±50% sweeps. |
| **H5** calibration approaches oracle retraining | **NOT TESTED** | Superseded: the method did not clear its own baseline, so the gap-to-oracle question never became live. |

**Two of five tested hypotheses survived. One of our own published results was retracted.**

---

## 2. The headline finding

> Marginal conformal prediction (arm **B2**) reports **89.1% *marginal* coverage** on held-out
> IEEE-CIS while covering **13.9% of the fraud class.** A monitoring dashboard reading the
> marginal number would call that system healthy.

*(The 0.891 here is B2's marginal coverage — averaged over all transactions. A different 0.891
appears in §3 as the legit-class coverage of the ProductCD-segmented α=0.10 arm. Same digits,
different quantity.)*

Conditioning the quantile on the class restores fraud coverage to 0.868 for 5.7 points of extra
review volume. Conditioning on the *segment* as well brings worst-cell deviation from 0.211 to
0.083.

This result needs no τ, no agent modelling, and no contested assumption. It is a property of the
real data.

**Prior art, stated up front.** That marginal coverage can hold while a class is badly
under-covered is not our discovery — it is the motivation for class-conditional conformal
prediction, established by Sadinle, Lei & Wasserman, *Least Ambiguous Set-Valued Classifiers with
Bounded Error Levels*, JASA 114(525):223–234, 2019 ([arXiv:1609.00451](https://arxiv.org/abs/1609.00451)).
**Our contribution is the operational measurement, not the mechanism**: how far the gap opens on
real payments data, what closing it costs in rupees and analyst capacity, and the prevalence
below which it cannot be closed at all.

---

## 3. What the method costs

At the pre-registered α = 0.10, on 110,377 held-out transactions:

| arm | cost ₹ | vs B1 | recall | FPR | legit cov | fraud cov |
|---|---|---|---|---|---|---|
| B1 per-transaction Bayes threshold | 3,718,531 | baseline | 49.7% | 1.85% | — | — |
| α = 0.10, **identity-segmented** | 5,248,665 | **−1,530,135** | 74.4% | 11.15% | — | — |
| α = 0.10, **ProductCD-segmented** | 5,417,737 | **−1,699,207** | 73.8% | 11.49% | 0.891 | 0.878 |
| Amendment 1, per-class α, ProductCD | 3,691,394 | +27,137 | 58.7% | 3.19% | 0.976 | 0.878 |

*(The 0.891 in the `legit cov` column is the legit-class coverage of the ProductCD-segmented
α=0.10 arm — not the marginal coverage of §2's B2 arm, which happens to share the digits.
The two α=0.10 rows differ only in segmentation; §1's "₹1.53M" refers to the identity-segmented
one.)*

**Why α = 0.10 fails, structurally.** Promising 90% coverage of the *legitimate* class excludes
10% of legitimate traffic by construction. At 96.3% legitimate traffic that is ~9.7% of all
volume pushed toward block-or-review, against 2% analyst capacity — 89% of escalations were
truncated. A symmetric miscoverage budget on a 28:1 imbalanced, cost-asymmetric problem hands
almost the whole budget to the class that can least afford it.

**Amendment 1** derives the budget instead of choosing it:
`α_legit = review_cap / P(legit) = 0.02 / 0.96292 = **0.02077**`, with α_fraud unchanged at 0.10.
Recorded in `config.yaml` with a prediction written **before** the run.

> **On α precision.** The method uses the exact derivation **0.02077**. The §4 sweep evaluates a
> fixed grid whose nearest point is **0.0208**, giving 3,689,340 against the exact value's
> 3,691,394 — a difference of **₹2,054 (0.06%)**, consistent with how flat the cost surface is
> around the optimum. Where the two appear side by side, 0.02077 is the method and 0.0208 is the
> grid point.

Counter-intuitive and worth stating: fraud is the expensive error per case, but legitimate
traffic is ~28× more common, so **in aggregate the miscoverage budget belongs mostly to the
fraud class.**

The arithmetic makes it concrete: α_legit = 0.02077 applied to ~96% of volume is ≈2% of all
transactions — **the entire review capacity, consumed before the fraud class spends anything.**
That is why the symmetric α=0.10 could not work: it was writing a cheque for ~9.7% of volume
against a 2% account.

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

**Why more capacity makes it worse.** Not the obvious reason. The baseline runs **no review queue
at all** (0 reviewed), so this is not a comparison of queue composition. The gate escalates far
more than it can staff — at 2% capacity **89% of its escalations are truncated** — and truncated
cases fall back to the cost-optimal Bayes decision. **Truncation is therefore a rescue, not a
penalty**: the capacity cap silently substitutes cost-optimal decisions for coverage-mandated
ones. Raising capacity removes that rescue. And because the escalation queue is overwhelmingly
legitimate traffic, each extra review slot mostly buys a needless charge — reviewing a legitimate
transaction costs ₹40 + 5%·c_FP (≈₹53–59), where Bayes would have approved it for ₹0. The
persisted capacity sweep in `block4_ieee-cis.json` shows the same direction on the α=0.10 arms
(1%→5%: B3 +42,412, D1 +99,384 — cost *rises*), while B2, which escalates far fewer and
better-targeted cases, moves −570,142 in the opposite direction.

> **The defensible claim:** segment-conditional conformal abstention with a capacity-derived
> per-class α is roughly **cost-neutral** against a plain per-transaction Bayes threshold, while
> additionally delivering a **stated per-segment coverage level** — 97.6% on legitimate traffic,
> 87.8% on fraud — that a bare threshold cannot state at all.

**The operational upside, stated with its caveat.** At roughly zero net cost the gate also buys
**fraud recall 58.7% against the baseline's 49.7%** — nearly nine points — for **+1.34 points of
false-positive rate** (3.19% vs 1.85%). That is a real operating improvement and it is the most
saleable number here. The margin caveat above applies unchanged: the *net cost* advantage is not
robust, so present the recall gain as bought at approximately break-even, never as bought at a
profit.

You buy auditability at approximately zero cost. Not profit.

---

## 5. External validation — failed

ULB — 0.172% fraud overall, **0.126% in the held-out test window** — segmented by amount quartile
(no ProductCD available):

- The method **loses at every α in the grid.** Best net −₹31,637; −₹161,111 at the **nearest grid
  point (0.0208)**, which is 82% of baseline cost. ULB's exact derived value is **0.02002** and is
  not on the grid; the conclusion is unchanged, since every grid point loses.
- **Fraud coverage is unreportable at all 11 α values.** The calibration split holds ~40 fraud
  rows against the n≥100 floor, so no fraud quantile can be estimated and the gate effectively
  runs on one class.

**Why the floor is 100.** A quantile at α=0.1 is the ⌈(n+1)·0.9⌉-th order statistic, so it needs
on the order of 1/α = 10 samples merely to *exist*, and an order of magnitude more before its own
sampling interval is narrower than the effect being measured. At ~40 fraud rows the quantile's
confidence interval is wider than the coverage gaps under discussion — the number could be
printed, but not honestly defended. Refusing to report it is the stop rule working.

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

## 7. Bugs found (three of five have regression tests)

1. `aci_update` took target *coverage* where Gibbs–Candès takes target *miscoverage* — the
   controller ran backwards and drove coverage to ~10%. **Silent in production**: the prediction
   sets still look plausible.
2. `Encoder` detected categoricals via `dtype == object`, missing pandas 3.0's `str` dtype;
   numeric coercion then nulled ~15 columns including all of block M. Nothing raised.
3. `coverage()` applied the stop rule to the evaluation cell rather than the governing
   calibration cell.
4. Block 5 let evaluation granularity follow calibration granularity.
5. `fetch_data.py` probed auth with a `whoami` subcommand that does not exist in Kaggle CLI 2.x.

**Test coverage is not uniform, and the difference matters.** Bugs 1–3 are library defects and
each has a regression test that has been *mutation-verified*: reverting the fix makes a named test
fail (bug 1 → `test_aci_tracks_target_coverage_under_drift_where_static_fails`; bug 2 → three
tests in `test_pipeline.py`; bug 3 → `test_population_conditioning_restores_coverage_under_signal_loss`).
**Bugs 4 and 5 are script-level fixes with no automated test.** Both were found by inspection and
would not be caught again automatically. Do not claim the suite covers them.

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
- **A single base learner.** Every reported number comes from one LightGBM configuration. The
  layer is model-agnostic by construction and was designed to be demonstrated across three
  scorers (the E7 ablation), but that ablation was never run on real data. The *direction* of the
  coverage gap should hold for any miscalibrated scorer; its *magnitude* — and therefore every
  rupee figure — is unverified beyond this one model.
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
