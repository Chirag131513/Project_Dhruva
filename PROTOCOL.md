# Dhruva — Pre-Registered Protocol v1.0

**Committed before any experimental result was produced. Sections 02, 05, 07, 10 and 12 are
amendment-only:** to change one, append to `amendments` in `config.yaml` with a timestamp and
reason and re-freeze via Block 0. Do not edit in place. Numeric constants live in `config.yaml`
and are hashed into `results/protocol.lock`.

---

## 01 · Research question

> When human-specific behavioural and device signals progressively disappear from a payment
> stream, does a deployed fraud model's **calibration** degrade faster than its
> **discrimination** — and if so, can population-conditional conformal calibration restore target
> empirical coverage without retraining the base model, at a measurable rupee benefit?

Three phrasings are deliberate. **"Behavioural signal loss"**, not "AI-agent traffic": the shift
is what I manipulate, agentic commerce is why it matters. **Calibration vs discrimination**:
"does removing features hurt?" is trivially yes. **"Target empirical coverage"**, not "error
guarantee": conformal validity holds under exchangeability, drift violates it, and that is why
ACI is in the design.

---

## 02 · Hypotheses *(frozen)*

| ID | Hypothesis | Refuted if |
|----|-----------|-----------|
| **H1** | Calibration degrades faster than discrimination. R(λ) = [ΔECE/ECE₀] ÷ [ΔPR-AUC/PR-AUC₀] > 1 and rising in λ. | R(λ) ≤ 1 across the sweep → report that signal loss is a model problem, not a calibration problem. |
| **H1b** | FPR on legitimate traffic rises faster, in ₹, than fraud recall falls. | ₹ loss dominated by missed fraud at every λ. |
| **H2** | Pooled calibration under-covers the fraud class within the degraded sub-population, beyond bootstrap CI. | Pooled coverage stays within CI of nominal on both populations. |
| **H3a** | Per-(population × class) quantiles restore nominal coverage on both, without retraining. | Coverage still misses nominal, or cells too sparse (§12). |
| **H3b** | With ρ ramping, ACI-updated per-cell quantiles track nominal where static ones drift off. | Static per-cell quantiles hold under ramping ρ → the online machinery is unnecessary; say so. |
| **H4** | Coverage restoration yields positive net ₹ after review costs, increasing in ρ. | Net ≤ 0 once review cost is charged. |
| **H5** | Dhruva recovers a substantial fraction of oracle-retrain performance **without labels from the shifted population**. | Oracle dominates widely → recommend retraining; Dhruva's value confined to the label-delay window. |

H5 is **not optional**. "Why not just retrain?" is the first question a judge asks.

---

## 03 · Dataset

**Primary:** IEEE-CIS Fraud Detection (Vesta). 590,540 CNP transactions, ~6 months, 3.5% fraud,
431 features. **Secondary:** Fraud Detection Handbook simulator, controlled-drift validation only.
**Excluded:** ULB (PCA features cannot be ablated meaningfully), PaySim/BankSim (weak realism),
Elliptic (Bitcoin), **any learned synthetic generator** (arXiv:2604.13125 shows they fail to
preserve temporal, velocity and multi-account fraud patterns).

**Dev fixture** (`data.load(dev=True)`) is deterministic plumbing for pipeline development.
Every frame carries `attrs["data_source"]`; every artefact records it. **No result from a source
other than `ieee-cis` may be reported.**

---

## 04 · Feature blocks *(frozen)*

| Block | Columns | Ablated |
|-------|---------|---------|
| T | `TransactionAmt`, `ProductCD`, `card1–6`, `addr1–2`, `dist1–2`, `P_/R_emaildomain` | No |
| C | `C1–C14` — counting / velocity | No |
| D | `D1–D15` — timedeltas | Partial (timing compression) |
| M | `M1–M9` — match flags | No |
| V | `V1–V339` — Vesta engineered | No |
| **I** | `id_01–id_38`, `DeviceType`, `DeviceInfo` | **Primary target** |

Block V is not ablated despite plausibly containing behavioural derivatives, because its
provenance is undocumented and ablating opaque features would make the manipulation
unfalsifiable. Consequence: some behavioural signal survives τ, so **measured degradation is a
lower bound**. State this.

---

## 05 · The τ transform *(frozen)*

```
τ(x, λ):
  1. mask each block-I column with probability λ        (LightGBM handles NaN natively;
                                                          no imputation artefact)
  2. compress block-D inter-event deltas by (1 − λ·κ),  κ = 0.5 fixed a priori
  3. nothing else. Amounts, labels, card/merchant identity, C/M/V untouched.
     No transaction created, deleted or relabelled.
```

ρ ∈ {0, .1, .2, .4, .6, .8} · λ ∈ {0, .25, .5, .75, 1.0} · headline λ = 0.75.
Assignment is random within TEST and **independent of `isFraud`** — correlating the shift with
the label would manufacture the result. Seeded and logged.

**Claim discipline.** May not say: *"this is what AI-agent payments look like."* May say: *"τ is
a controlled proxy for the progressive loss of human-specific behavioural and device signal that
industry reports under agent-initiated transactions. I manipulate signal availability, not
agent-ness. Transactions and labels are real."*

**Independent validation, required.** Every headline result must also reproduce on two shifts I
did not construct: (a) the natural identity-absent sub-population (E0), (b) IEEE-CIS's genuine
six-month temporal drift with τ off (E1). Run these **first**.

---

## 06 · Splits

```
|------- TRAIN 60% -------|-- DELAY 7d --|--- CAL 15% ---|------- TEST 25% -------|
     fit base scorer          dropped       fit CP quantiles    evaluate ONCE
```

Fractions are of the **time span**, not row count. TEST is read once. ACI may consume a TEST
label only after δ has elapsed from its timestamp (`splits.releasable_at`). No resampling —
imbalance is handled by the cost model. Encoding fitted on TRAIN only; unseen levels → `UNSEEN`.

---

## 07 · Conformal method *(frozen)*

Nonconformity `s(x,y) = 1 − p̂(y|x)`. Cells `g = (population, class)`, population ∈
{BASE, SHIFTED} from **signal availability alone** — the router does not read the assignment
flag. Quantile `q[g]` = k-th smallest score, `k = ⌈(n_g+1)(1−α)⌉`. α = 0.10.

`|C(x)| = 1` → act; otherwise → REVIEW.

ACI: `α[g] ← clip(α[g] + γ(α − err), 0.001, 0.5)`, **γ = 0.01 declared a priori**, sensitivity
reported over {0.005, 0.01, 0.05} as a band — never as a substitute headline.

> **Units.** `α` here is target *miscoverage* (0.10), not target coverage (0.90). Passing 0.90
> inverts the controller and drives coverage to ~10% while the sets still look plausible.

---

## 08 · Baselines

| Arm | Definition |
|-----|-----------|
| B0 | Fixed threshold 0.5 — naive floor |
| **B1** | Cost-tuned Bayes threshold on pooled CAL — **the real baseline** |
| B2 | Marginal split conformal |
| B3 | Static Mondrian, class-only |
| **D1** | Dhruva-static: per (population × class) |
| **D2** | Dhruva-online: D1 + ACI |
| **B4** | Oracle retrain — refit on shifted data *with labels*. Unavailable in practice during the label-delay window; that is the point. |

Model-agnosticism: rerun {B1, D1} over LightGBM, logistic regression, random forest.

---

## 09 · Metrics

Detection: PR-AUC, Precision@k (k = review capacity), recall@fixed-FPR.
Calibration: ECE (15 equal-mass bins), Brier, reliability curve.
Coverage: empirical per cell vs 1−α; rolling over test time.
Cost: expected ₹ loss, ₹/1,000 txns, net vs B1. Operations: review rate, queue depth, p50/p99.

**Never report accuracy** (96.5% for an all-legitimate predictor). **ROC-AUC is never a headline**
— under extreme imbalance the FP axis is dominated by the negative class.

Statistics: 10 seeds; paired two-sided Wilcoxon across seeds; effect size + bootstrap CI, not
p-values alone. Print the underpowered case explicitly (min achievable two-sided p ≈ 0.002 at
n=10). Comparison code must be symmetric and unable to express a preference.

---

## 10 · Cost model *(frozen)*

```
c_FN(x) = amount + ₹1,500          c_FP(x) = 0.25·amount + ₹250
c_REV   = ₹40                      ε_hum   = 0.05
```

Decision minimises expected cost. Review volume ≤ capacity ∈ {1%, 2%, 5%}; excess ranked by
expected ₹ loss and truncated, with the truncation rate reported. **Sensitivity is mandatory:**
±50% sweep on `fee_chargeback`, `margin`, `review_cost`. If the sign of the conclusion flips
anywhere in that range, say so on the slide.

---

## 11 · Experiments

`E0` natural identity-absent population · `E1` real temporal drift, τ off · **`E2` degradation
curve → Graph 1** · **`E3` coverage restoration → Graph 2** · **`E4` economics → Graph 3** ·
`E5` online maintenance · `E6` why-not-retrain · `E7` model-agnosticism · `E8` cost sensitivity.

E0–E4 are the submission. **Run E0 and E1 before E2** — they make everything after them credible.

---

## 12 · Success & failure criteria *(frozen)*

| Outcome | Condition | Present |
|---------|-----------|---------|
| Full | H1 ∧ H2 ∧ H3a ∧ H4 net > 0, surviving the seed-paired test | Three graphs, ₹ table, non-claims slide |
| Partial | H1 ∧ H2 ∧ H3a hold; H4 ≈ 0 or sign-unstable | Reliability result stands; name the constant that decides it |
| **Negative-informative** | H1 refuted | **Present it.** "Signal loss is a model problem, not a calibration problem — here is the evidence." |
| Underpowered | Direction right, CIs span zero | Report direction, CI, required n. Do not upgrade the language. |
| **Stop** | Any fraud cell has n < 100 in CAL | **Do not report per-cell coverage for it.** Collapse cells and say why. |

---

## 13 · Language

| Don't say | Say |
|-----------|-----|
| "AI-agent traffic" | "agent-induced behavioural signal shift" (method) / "agent-initiated payments" (motivation) |
| "error guarantee" | "target empirical coverage under stated assumptions" |
| "nobody has done this" | "I found no public work measuring this failure mode" |
| "I solve RBI compliance" | "emits model-risk evidence relevant to emerging governance expectations" |
| "LIVE" | "TEST REPLAY" — it is precomputed held-out data |
| "I built a fraud detector" | "I built the layer that tells you when your detector can still be trusted" |

RBI framing is one supporting sentence, late. The primary story is technical reliability plus
merchant economics.
