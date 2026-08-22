# Dhruva — Results

**What we set out to test, what the data said, and what we are entitled to claim.**

Dataset: IEEE-CIS Fraud Detection (Vesta), 590,540 card-not-present transactions over ~6 months,
3.4% fraud. External validation: ULB/Worldline, 284,807 transactions (0.172% fraud overall;
**0.126% in the held-out test window**, which is the figure the calibration cells actually see).
Protocol pre-registered and hashed before any result existed — `results/protocol.lock`, commit
`559c8fa`.

---

## 0. The result

> **Under a hard analyst-capacity limit, choosing which cases a human sees is worth 28% of a
> merchant's realised fraud loss — and the signal that wins is the simplest one we tested, not
> the one the 2026 literature is built around.**

Net benefit against a per-transaction cost-optimal Bayes threshold, 10 seeds, every arm
escalating the **same volume** so only the *choice* of escalated cases differs:

| escalation signal | 1% | 2% | 5% | 10% |
|---|---|---|---|---|
| **band** — rank by \|p − t(x)\| | **+214,512** | **+396,334** | **+787,307** | **+1,061,079** |
| disagreement (DAUNT-style proxy) | +65,215 | +169,446 | +458,320 | +788,055 |
| conformal prediction sets | +38,995 | +72,319 | +87,058 | +47,755 |
| random | −24,344 | −50,752 | −131,542 | −261,883 |

Three things follow, and the second and third are the interesting ones.

**1. Escalation under capacity pays, and it scales.** Band cuts realised loss 5.7% → 10.6% →
21.0% → **28.4%** as capacity rises 1% → 10%. Monotone, and the sign holds under ±50% sweeps on
**all four** cost constants (range +₹513,576 to +₹1,409,008).

**2. The signal is the entire value.** Random escalation *loses* ₹261,883. Band beats random by
₹1,322,962 (p = 0.0020). Giving analysts more cases does nothing; giving them the *right* cases
is worth 28% of the loss.

**3. Conformal prediction — the technical core we built this project around — is the
second-worst signal tested.** A one-line rule beats it **22×** at 10% capacity (p = 0.0020, the
minimum achievable at n = 10). It is also the only signal that is non-monotone in capacity: it
peaks at 5% and falls at 10%, the behaviour of a signal that has run out of genuinely ambiguous
cases and is padding the queue.

**4. The operating point strictly dominates the baseline.** At 10% capacity, band reaches
**72.4% fraud recall against the threshold's 49.7% — while *halving* the false-positive rate,
1.85% → 0.88%.** Normally these trade against each other; here both improve, because the escalated
cases are resolved correctly 95% of the time instead of being forced into a binary call. That is
the sentence a merchant cares about: *more fraud caught, fewer good customers blocked, same
analyst headcount.*

We implemented the July–August 2026 conformal literature faithfully, pre-registered a kill test
that could invalidate it, ran the test, and it fired. That is reported here as the finding rather
than buried.

---

## 0b. Two premises, tested rather than asserted

The 28% claim assumes the baseline is the model *used well* and that escalated cases are
genuinely where it fails. Block 10 tested both. One came back against us.

**A — the baseline is very slightly favourable to us.** Sweeping fixed thresholds, a flat cutoff
at 0.10 costs ₹3,695,822 against our per-transaction Bayes threshold's ₹3,718,531 — **our
baseline is ₹22,709 (0.6%) worse.** The per-transaction rule is optimal only under perfectly
calibrated probabilities; ours has ECE 0.0039, close but not exact.

Two things keep this honest rather than fatal: 0.10 was found by sweeping the **test set**, which
is hindsight our own method never received, so 0.6% is an *upper bound* on the advantage. And the
escalation gain is **47× larger** than the gap. Report the number; don't let anyone find it first.

**B — the model's errors are strongly concentrated, and the rule finds them.**

| | escalated 10% | remaining 90% |
|---|---|---|
| model error rate | **17.05%** | 1.98% |
| concentration | **8.6×** | — |
| share of all errors captured | **48.9%** (1,882 of 3,847) | |
| share of error *value* captured | **46.8%** (₹1,738,832 of ₹3,718,531) | |

**Read this the right way round: the model is not bad.** It is right 98% of the time across nine
tenths of the traffic — that is a good model. Its mistakes simply are not spread evenly, and a
one-line rule locates about half of them in a tenth of the volume. That is why a human helps: not
because the model is weak, but because its failures are findable.

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

### Kill conditions (declared in the Stage-1 verdict, run in Block 9)

| | Condition | Outcome |
|---|---|---|
| **K1** | net ≤ 0 at every capacity | **passed** — best +₹87,058 (conformal), +₹1,061,079 (band) |
| **K2** | benefit not monotone in capacity | **FIRED for conformal** (+38,995 → +72,319 → +87,058 → +47,755). Band is monotone. |
| **K3** | a plain score-band rule ≥ conformal | **FIRED — band *beats* conformal**, Δ = −₹1,013,324, 95% CI [−1,034,124, −990,935], p = 0.0020 |
| **K4** | ensemble disagreement beats conformal | **FIRED** (+788,055 vs +47,755) |
| **K5** | sign flips under ±50% cost sweep | **FIRED for conformal** (3 of 4 constants). **Band: no flips.** |

K3's own test logic was wrong on first write — it checked only for a *tie* and would have
reported "passed" in exactly the case where conformal is worse. Corrected before the 10-seed run.

---

## 2. Why conformal loses — the mechanism, which is still worth knowing

Section 0 shows conformal losing. This section explains why, and the explanation is the part of
the original project worth keeping — it is also *why the coverage framing was never going to
produce a business result*.

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

### Prior art, stated up front

That marginal coverage can hold while a class is badly under-covered is not our discovery. The
mechanism is Sadinle, Lei & Wasserman, *Least Ambiguous Set-Valued Classifiers with Bounded Error
Levels*, JASA 114(525):223–234, 2019 ([arXiv:1609.00451](https://arxiv.org/abs/1609.00451)) — and
2026 has been a busy year for the empirical version of it:

| Work | Domain | Reported |
|---|---|---|
| [Cost-Sensitive CP & HITL Abstention](https://arxiv.org/abs/2607.27143) (Jul 2026) | 15 imbalanced datasets incl. fraud | marginal → 0.5% minority coverage; Mondrian **+61.7 pp** |
| [A Quiet Failure in Calibrated Virtual Screening](https://arxiv.org/html/2607.06605v1) (Jul 2026) | drug discovery | 90.2% marginal / **64.8% minority**; Mondrian restores; utility model favours the fix |
| [Class-Conditional CP for Anomaly Detection](https://doi.org/10.3390/make8070190) (Jul 2026) | Azure KPI, Yahoo, NAB | **52.94% → 90.59%** at 1:345 imbalance; agnostic across XGBoost/RF/NN |
| [arXiv:2607.18088](https://arxiv.org/html/2607.18088v2) (Jul 2026) | action recognition | "marginal coverage hides a per-class collapse" |

**We claim none of that.** Our contribution is operational and, in one respect, contrarian:

- **The economics run the other way.** Those papers report the fix winning. On real payments with
  a finite analyst queue it *loses* ₹1.53M at the conventional α, and only reaches break-even
  after the capacity derivation in §3. None of them models a review capacity.
- **The prevalence floor** (§5): below ~0.1% fraud there is not enough minority calibration data
  to run the method at all.
- **The failure scales with model quality** (§9), which is invisible to a single-model study.

### Why the gap is that large — an exact identity

The collapse is not incidental to imbalance; it is *determined* by it. Writing π_F for fraud
prevalence, R = π_L/π_F for the imbalance ratio, T for the target and s = cov_legit − T for the
majority's surplus, the definition of marginal coverage rearranges to:

```
T − cov_fraud  =  (T − marginal)/π_F  +  s·R
                   └── marginal deficit ──┘   └─ surplus × ratio ─┘
```

On our data (π_F = 0.033811, R = 28.58, marginal = 0.890928, cov_legit = 0.917249):

```
term 1   (0.900 − 0.890928)/0.033811   =  0.268301
term 2    0.017249 × 28.5758           =  0.492899
                              predicted =  0.761200
                               observed =  0.761200      residual 0.00000000
```

**A 1.7-point surplus on the majority class becomes a 76-point shortfall on the minority.** That
is the whole failure mode in one line, and it is exact rather than approximate.

The "Quiet Failure" paper states this as *shortfall = surplus × ratio* — **term 2 only**. That
form assumes marginal coverage lands exactly on target. Ours undershoots by 0.009, and at
π_F = 0.034 that deficit contributes another 0.268. **Term 2 alone under-predicts our observed
shortfall by 35.2%.** Their 3.26:1 setting was too mild for the omission to show; at 28.6:1 it is
a third of the effect. Anyone using the one-term version to size the risk on a heavily imbalanced
problem will under-state it.

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

> **On α precision.** The method uses the exact derivation **0.02077**. The Block 7 α sweep
> (`results/block7_alpha_sweep.json`) evaluates a fixed grid whose nearest point is **0.0208**,
> giving 3,689,340 against the exact value's
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

> **Superseded by §0.** This paragraph described the *conformal* arm, which Block 9 showed is
> the second-worst escalation signal available. It is kept because the ±₹27,137 margin and its
> four sign flips are the contrast that makes the band result meaningful: **+₹1,061,079 with no
> sign flips at all.** Do not present the sentence below as the claim.

> ~~Segment-conditional conformal abstention with a capacity-derived per-class α is roughly
> cost-neutral against a plain per-transaction Bayes threshold, while additionally delivering a
> stated per-segment coverage level — 97.6% on legitimate traffic, 87.8% on fraud — that a bare
> threshold cannot state at all.~~

**The operational upside, stated with its caveat.** At roughly zero net cost the gate also buys
**fraud recall 58.7% against the baseline's 49.7%** — nearly nine points — for **+1.34 points of
false-positive rate** (3.19% vs 1.85%). That is a real operating improvement and it is the most
saleable number here. The margin caveat above applies unchanged: the *net cost* advantage is not
robust, so present the recall gain as bought at approximately break-even, never as bought at a
profit.

**The two values move in opposite directions.** §9 measures the layer across three base scorers
and finds that its *coverage* value grows with model quality — the better the model, the larger
the gap that class-conditional calibration closes — while its *economic* value shrinks, because a
good model's threshold baseline is already cheap. On the weakest scorer the layer is worth
₹2.78M; on the best it is worth ₹27,137.

The consequence is worth saying before anyone works it out: **for a production system with a
strong model, the honest pitch is the guarantee, not the money.** A team already running a
well-calibrated scorer is exactly the team for whom the under-coverage is most severe and the
rupee saving is most negligible.

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
- **Base-learner dependence — now measured, and the answer is split** (§9). The *fix* is
  model-agnostic: class-conditional calibration restores fraud coverage to 0.868–0.894 on all
  three scorers. The *failure* is not: the under-coverage gap ranges 0.106 to 0.752 and scales
  with model quality. And the *economics* do not transfer at all — the apparent gains on the
  weaker scorers are artefacts of broken baselines.
- **The weaker arms are not like-for-like.** Logistic regression and random forest cannot accept
  NaN, so they impute (median) where LightGBM handles missingness natively; both also use
  `class_weight="balanced"`, which inflates predicted probabilities past the cost-optimal
  threshold. Those are properties of the models and of choices in `model.py`, not of the
  calibration layer, but they mean the three arms are not strictly comparable.
- **Amendment 1 is post-hoc.** Derived rather than tuned, prediction pre-recorded, and the
  pre-registered result reported alongside it every time — but post-hoc nonetheless.
- **Multiple looks.** Seven blocks, four arms, two amendable constants. Every result is reported,
  including the ones that killed hypotheses.

---

## 9. Base-learner dependence (E7)

*Post-hoc. Same conformal arms, three different base scorers, everything else held fixed.*

| scorer | PR-AUC | ECE | marginal | B2 fraud | **gap** | B3 fraud | net vs B1 |
|---|---|---|---|---|---|---|---|
| logistic regression | 0.1739 | 0.2829 | 0.875 | 0.769 | **0.106** | 0.894 | +2,783,903 |
| random forest | 0.4729 | 0.1474 | 0.889 | 0.417 | **0.472** | 0.872 | +2,635,767 |
| LightGBM | 0.5233 | 0.0039 | 0.891 | 0.139 | **0.752** | 0.868 | +27,137 |

**The fix is model-agnostic.** Class-conditional calibration restores fraud coverage to
0.868–0.894 on every scorer. That is the claim §4 depends on, and it now has evidence.

**The failure is not — and it runs the wrong way.** The under-coverage gap scales monotonically
with model quality, and inversely with calibration error:

```
PR-AUC 0.174  →  gap 0.106      ECE 0.2829
PR-AUC 0.473  →  gap 0.472      ECE 0.1474
PR-AUC 0.523  →  gap 0.752      ECE 0.0039
```

The mechanism: a well-separated scorer pushes fraud nonconformity far from legitimate
nonconformity, so the pooled quantile — set by the 96% legitimate majority — excludes nearly all
of it. A weak, overlapping scorer covers the fraud class *by accident*. **The failure mode is
therefore most severe exactly where the best models are deployed**, which is the opposite of the
intuition that better models need less scaffolding.

**The economics do not generalise, and the apparent gains are artefacts.** The +₹2.78M and
+₹2.64M figures come from broken baselines: logistic regression's cost-optimal threshold runs at
**69.08% FPR** and random forest's at **43.38%**, costing 5.81× and 3.69× the LightGBM baseline.
Those are not baselines, they are models nobody would deploy, and the layer is merely rescuing
them. Both arms additionally impute missing values and use `class_weight="balanced"` — choices in
`model.py` that inflate predicted probabilities past the threshold. **Do not cite the ₹2.78M
figure as evidence the method works.** The only economically meaningful row is LightGBM's
+₹27,137, and §4 already says what that is worth.

---

## 10. What not to say

| Don't | Do |
|---|---|
| "we built a conformal risk gate" | "we measured what escalation is worth under a capacity limit — conformal lost" |
| "conformal prediction is our method" | conformal is a **baseline we tested and it came second-worst** |
| "AI-agent traffic" | "segment-conditional calibration"; agentic commerce is motivation only |
| "error guarantee" | "target empirical coverage under stated assumptions" |
| "we save ₹X" | "roughly cost-neutral, with a stated coverage level" |
| "nobody has done this" | "we found no public work measuring this failure mode" |
| "LIVE" | "TEST REPLAY" |
| "no retraining" | "no gradient-based refitting of the base model" |

---

## 11. What we would do next

The band result is strong but the *signal* is barely explored. `band` ranks by distance to the
Bayes threshold; it was written as a strawman for the kill test and it won. Obvious next steps,
none of them run:

- **A learned rejector** trained directly on realised rupee cost, which is what DAUNT's framing
  implies and what would test whether hand-built ranking is leaving money on the table.
- **Why conformal fails specifically.** Our reading is that conformal nominates cases where the
  *classes* are hard to separate, while the money is in cases near the *cost-optimal cut* — two
  different sets. That is a hypothesis we state, not a result we measured.
- **Capacity beyond 10%**, to find where the curve saturates.

---

## 12. Reproducing

```bash
python scripts/block0_audit.py          # freeze + identity audit
python scripts/block1_baseline.py       # PR-AUC 0.523, Precision@2% 0.68
python scripts/block2_conformal.py      # the 0.891 / 0.139 result
python scripts/block3_shift.py --seeds 3
python scripts/block4_cost.py           # H4 refuted
python scripts/block5_segments.py       # Block 3 retracted
python scripts/block6_amendment.py      # Amendment 1
python scripts/block7_alpha_sweep.py    # curve + ULB failure
python scripts/block8_agnostic.py       # E7: fix is agnostic, failure scales with model quality
python scripts/block9_triage.py --seeds 10   # THE RESULT: kill test, band beats conformal 22x
python scripts/export_console.py && streamlit run app/console.py
python -m pytest tests/ -q              # 22 passed
```
