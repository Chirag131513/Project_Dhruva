# Project Dhruva — Implementation Plan

> ## ⚠️ HISTORICAL DOCUMENT — do not present from this file
>
> This is the plan the project was designed against in August 2026, **before the evidence came
> in**. It describes a conformal-prediction risk gate and a ρ-slider demo. Both are dead:
> conformal finished **second-worst of four escalation signals** in the pre-registered kill test,
> and the ρ-slider console was replaced by `app/dashboard.html`.
>
> It is kept because the reasoning that led here is part of the record, and because §§ on data
> handling and module layout are still accurate.
>
> **For what the project actually found, read `RESULTS.md` §0.**
> **For how to run and present it, read `START_HERE.md`.** Both supersede this file.

**A risk gate that stays calibrated when human behavioural signal disappears from the payment stream.**

Companion to the [strategy brief](https://claude.ai/code/artifact/9d1331b5-60b6-40d0-9db1-d40016f4357a) and the
[pre-registered protocol](https://claude.ai/code/artifact/b6b651f4-d182-4f5b-9299-d2b3d9b89b87).
Where this file and the protocol disagree, **the protocol governs**. Where this file and
`RESULTS.md` disagree, **RESULTS governs** — it has the measurements.

---

## 0. What this actually is, in one paragraph

We take a normal fraud model (LightGBM on IEEE-CIS). We wrap it in a layer that, instead of
emitting a score, emits a **decision with a stated coverage level**: approve, review, or block.
We then progressively remove the human-specific device/behavioural signals from the incoming
stream — the thing industry says happens when an AI agent transacts on a customer's behalf —
and measure what breaks. The claim we are testing is that **calibration breaks before
discrimination does**: the model still ranks transactions correctly but no longer knows where to
cut. If true, recalibrating per population fixes it without retraining anything, and we can price
the difference in rupees.

Everything below exists to produce three graphs and one table honestly.

---

## 1. Repository layout

```
dhruva/
├── IMPLEMENTATION.md          ← this file
├── PROTOCOL.md                ← pre-registered spec, amendment-only
├── config.yaml                ← every constant. Frozen + hashed at Block 0.
├── requirements.txt
│
├── dhruva/                    ← library. No scripts, no side effects on import.
│   ├── config.py              load + freeze + hash config
│   ├── data.py                load IEEE-CIS or dev fixture; identity-coverage audit
│   ├── features.py            feature blocks T/C/D/M/V/I; causal encoding
│   ├── splits.py              chronological train/delay/cal/test
│   ├── shift.py               τ(x,λ) transform + population router
│   ├── model.py               base scorers (lgbm | logreg | rf)
│   ├── conformal.py           split CP · Mondrian cells · ACI
│   ├── cost.py                instance-dependent ₹ cost · decision · capacity queue
│   ├── metrics.py             PR-AUC · P@k · ECE · coverage · ₹ loss
│   ├── stats.py               paired Wilcoxon · bootstrap CI · underpowered flag
│   └── experiments.py         E0–E8 runners
│
├── app/console.py             Streamlit demo console
├── scripts/                   thin CLI wrappers, one per block
├── tests/                     property tests (coverage, leakage, determinism)
├── results/                   generated. artefacts/*.parquet + figures/*.png
└── data/                      raw IEEE-CIS csvs (gitignored)
```

**Rule:** `dhruva/` is importable and pure. Anything that writes to disk lives in `scripts/` or
`experiments.py`. This is what makes the tests meaningful.

---

## 2. Data flow, end to end

```
  data/train_transaction.csv ─┐
  data/train_identity.csv   ─┴─► data.load()
                                    │  left join on TransactionID
                                    │  ► AUDIT: identity coverage %      ◄── Block 0 finding
                                    ▼
                               features.build()
                                    │  block assignment T/C/D/M/V/I
                                    │  causal categorical encoding (TRAIN-fitted only)
                                    ▼
                               splits.chronological()
                                    │  TRAIN 60% │ DELAY 7d (dropped) │ CAL 15% │ TEST 25%
                                    ▼
              ┌─────────────────────┴──────────────────────┐
              ▼                                            ▼
        model.fit(TRAIN)                            shift.apply(CAL, TEST, ρ, λ)
              │  LightGBM                                  │  mask block I w.p. λ
              │  never sees CAL/TEST                       │  compress block D timing
              ▼                                            │  assign population label
        p̂ = model.predict(·)  ◄────────────────────────────┘
              │
              ▼
        conformal.calibrate(CAL)          ► q[(population, class)]
              │
              ▼
        conformal.predict_set(TEST)       ► C(x) ⊆ {legit, fraud}
              │
              ▼
        cost.decide(C(x), amount)         ► APPROVE | REVIEW | BLOCK
              │                              capacity-constrained, ranked by E[₹ loss]
              ▼
        metrics.evaluate()                ► coverage/cell · PR-AUC · ECE · ₹
              │
              ▼
        results/artefacts/*.parquet ──► app/console.py  (reads precomputed, never trains)
```

**One-way rule:** TEST is read once, at the end. Nothing upstream of `metrics.evaluate()` may
observe a TEST label. `conformal.aci_update()` is the sole exception, and only for rows whose
timestamp is more than δ=7 days old — that is the verification-latency simulation, and it is
enforced in code, not by convention.

---

## 3. Module contracts

Written before the code, so the code has something to satisfy.

### `config.py`
```python
Config.load(path) -> Config      # frozen dataclass; raises if unknown key
Config.hash() -> str             # sha256 of the resolved config
```
Every experiment writes its config hash into its artefact. If the hash changed between runs, the
results are not comparable and the loader says so loudly.

### `data.py`
```python
load(dev: bool) -> DataFrame                # dev=True → deterministic fixture, 40k rows
identity_coverage(df) -> IdentityAudit      # Block 0. n, pct, fraud rate by presence
```
`IdentityAudit` is the E0 evidence: fraud rate and calibration compared between
identity-present and identity-absent rows, **with no ablation applied**.

### `features.py`
```python
BLOCKS: dict[str, list[str]]                # T C D M V I — fixed, from PROTOCOL §04
build(df, fit_on: DataFrame) -> DataFrame   # categorical encoding fitted on TRAIN only
```
No target encoding. No full-timeline aggregates. Categorical columns are label-encoded from
TRAIN-observed values; unseen categories at CAL/TEST map to a reserved `UNSEEN` code.

### `splits.py`
```python
chronological(df, cfg) -> Splits            # .train .cal .test  (delay window dropped)
assert_no_leakage(splits) -> None           # raises on any timestamp overlap
```

### `shift.py`
```python
tau(df, lam, rng) -> DataFrame              # mask block I w.p. λ; compress block D by (1-λκ)
assign(df, rho, rng) -> Series[bool]        # which rows are shifted — independent of isFraud
route(df) -> Series[str]                    # BASE | SHIFTED, from signal availability alone
```
`route()` deliberately does **not** read the assignment flag. It infers population from what
signal is actually present, exactly as a deployed router would. If routing accuracy is imperfect,
that is a real-world property worth reporting, not a bug to paper over.

### `conformal.py`
```python
calibrate(scores, labels, cells, alpha) -> dict[cell, float]   # q per cell
predict_set(scores, cells, q) -> ndarray[bool, (n,2)]          # membership per class
aci_update(alpha, covered, gamma) -> float                     # α + γ(target − err)
coverage(sets, labels, cells) -> dict[cell, float]
```
Pure functions. No state, no I/O. This is the file the property tests hammer.

### `cost.py`
```python
expected_costs(p, amount, cfg) -> dict[action, float]
decide(pred_set, p, amount, cfg) -> Action
apply_capacity(decisions, expected_loss, cap) -> decisions      # rank, truncate, report rate
```

### `stats.py`
```python
paired_test(a, b) -> TestResult   # Wilcoxon, two-sided, + bootstrap CI + underpowered flag
```
`TestResult.__str__` prints `"not significant (n=10, underpowered — min achievable p≈0.002)"`
when applicable. The honesty is in the library, not in the write-up.

---

## 4. The console (this is what judges actually see)

`app/console.py` — Streamlit, reads precomputed artefacts, **never trains live**.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  DHRUVA     risk gate · coverage monitor   ◧ TEST REPLAY · 90% tgt  │
├──────────────┬───────────────────────────────────────────────────────┤
│              │                                                       │
│  CONTROLS    │   ┌─ COVERAGE MONITOR ──────────────────────────────┐ │
│              │   │  1.0 ┤                                          │ │
│  Agent share │   │      │ ────────────────── target 90% ─────────  │ │
│  ρ  ▓▓▓▓░░░░ │   │  0.9 ┤━━━━━━━━━━━━━━╗          ┏━━━━━━━━━━━━━━  │ │
│     40%      │   │      │   dhruva     ║  pooled  ┃                │ │
│              │   │  0.8 ┤              ╚━━━━━━━━━━┛                │ │
│  Signal loss │   │      └──────────────────────────────────────────│ │
│  λ  ▓▓▓▓▓▓░░ │   │        BASE·legit  BASE·fraud  SHIFT·legit  ⚠   │ │
│     75%      │   └──────────────────────────────────────────────────┘ │
│              │                                                       │
│  ┌────────┐  │   ┌─ CELLS ──────────────┐ ┌─ MONEY ────────────────┐ │
│  │ DHRUVA │  │   │ cell      n   cov    │ │  baseline    ₹8.50L    │ │
│  │  ON ●  │  │   │ BASE·lgt 8.4k 0.90 ✓ │ │  dhruva      ₹6.66L    │ │
│  └────────┘  │   │ BASE·frd  294 0.89 ✓ │ │  ─────────────────────  │ │
│              │   │ SHFT·lgt 5.6k 0.91 ✓ │ │  net        +₹1.84L /mo │ │
│  Review cap  │   │ SHFT·frd  196 0.88 ✓ │ │  of which FP  ₹1.40L    │ │
│  ○1% ●2% ○5% │   └──────────────────────┘ └────────────────────────┘ │
│              │                                                       │
│              │   ┌─ DECISION STREAM ───────────────────────────────┐ │
│              │   │ ₹2,340  BASE   {legit}        APPROVE           │ │
│              │   │ ₹18,900 SHIFT  {legit,fraud}  REVIEW   E₹1,240  │ │
│              │   │ ₹840    BASE   {fraud}        BLOCK             │ │
│              │   └─────────────────────────────────────────────────┘ │
└──────────────┴───────────────────────────────────────────────────────┘
```

### The one interaction that matters

**The ρ slider is the demo.** Judge drags it from 0% to 60%. With `DHRUVA OFF`, the pooled
coverage line peels away from the 90% target and the SHIFTED·fraud cell flips to a red ⚠. Judge
toggles `DHRUVA ON`. The line snaps back. Nothing retrained; only the quantiles changed.

That single gesture is the entire thesis, and it is more persuasive than any slide. Build the
slider before you build anything else in the UI.

### Design rules
- Precompute every (ρ, λ, arm) combination to parquet. The slider is a **lookup**, not a
  computation. Nothing may block for more than ~50 ms.
- Coverage chart: target line always visible, cells coloured by in/out of band, bootstrap CI as
  a shaded ribbon. A cell below n=100 renders greyed with "insufficient calibration data" — the
  protocol's stop rule, enforced visually.
- Money panel leads with the **false-positive** component. That is Razorpay's stated pain.
- Decision stream is a real sample of scored TEST rows, not mock data.
- **Never label anything `LIVE`.** The header reads `TEST REPLAY`, because that is what it is —
  precomputed held-out rows replayed in timestamp order. Calling it live invites the question
  *"live from what?"*, and the honest answer costs you more credibility than the word bought.
  The same rule governs the whole submission: label every artefact by what it actually is.
- Dark by default (it reads as an ops console), single accent, semantic colour reserved for
  in-band / out-of-band / insufficient-data.

---

## 5. Build order

Each block ends in something you could show. Stop wherever time runs out.

| # | Block | Exit condition |
|---|-------|----------------|
| **0** | Scaffold · config freeze · data load · **identity-coverage audit** | Coverage % measured and committed. E0 evidence exists. |
| **1** | Chronological split · LightGBM · PR-AUC + P@k | **Valid submission exists.** |
| **2** | Split CP · marginal vs class-conditional · property tests | Reproduce marginal under-coverage of the fraud class. |
| **3** | τ transform · population router · (pop×class) cells | **Graph 1 + Graph 2** |
| **4** | Cost model · capacity queue | **Graph 3.** Core complete. |
| **5** | Oracle-retrain arm | Answer to *"why not just retrain?"* |
| **6** | ACI online update | Rolling-coverage chart |
| **7** | Model-agnosticism + cost sensitivity | Two tables |
| **8** | Console · FastAPI latency · limitations write-up | Polish |

**Hard rules.** No graph/GNN code before Block 7. No console before Block 8 *except* the ρ slider
prototype, which may be built early because it drives the experiment design. No amendment to
PROTOCOL §02/§05/§07/§10/§12 after Block 0 is committed.

---

## 6. Validating the idea before trusting it

Four checks, in order. Each can kill or rescue the project, and all four run before the real data
is needed.

**V1 — Does the conformal core actually work?** *(Block 2, synthetic, runs in seconds)*
Property test on data with a known imbalance: marginal CP must under-cover the minority class,
Mondrian must restore it to within CI of nominal. If this fails, the implementation is wrong, not
the idea. **This is the single most valuable early test** — it validates the mechanism with no
Kaggle download and no domain assumptions.

**V2 — Is there real-data support for the premise?** *(Block 0, E0)*
Compare calibration between identity-present and identity-absent IEEE-CIS rows, **no ablation**.
If they differ measurably, the premise has real-data backing before you manipulate anything. If
they do not differ, that is important and you must say so — it weakens H1 and you report it.

**V3 — Does the machinery survive drift you did not construct?** *(Block 2–3, E1)*
Run the calibration layer across IEEE-CIS's genuine six-month drift with τ switched off entirely.
If coverage holds without Dhruva and breaks without it, the method is validated independently of
your agent model. This is the answer to *"you invented your test distribution."*

**V4 — Is the effect asymmetric?** *(Block 3, E2)*
R(λ) = relative ECE degradation ÷ relative PR-AUC degradation. **R > 1 and rising is the whole
project.** R ≤ 1 refutes H1 and the honest conclusion becomes "this needs a better model, not a
calibration layer" — which you present, with the curve.

> If V1 passes and V4 fails, you still have a rigorous, well-measured negative result and a
> working measurement apparatus. That is a legitimate submission on a track judged on honest
> metrics. Plan for it rather than fearing it.

---

## 7. Data acquisition

IEEE-CIS is a Kaggle competition dataset (~600 MB), requires a Kaggle account and accepting the
competition rules.

```bash
pip install kaggle
# place kaggle.json in ~/.kaggle/
kaggle competitions download -c ieee-fraud-detection -p data/
unzip data/ieee-fraud-detection.zip -d data/
```

**Until then, everything runs on `--dev`.** `data.load(dev=True)` returns a deterministic fixture
with the same schema, column blocks, temporal ordering and class imbalance. It exists so the
pipeline, the tests and the console can be built and validated today.

> **The fixture is plumbing-only.** It is a hand-specified deterministic generator, not a learned
> synthetic model, and **no reported result may come from it**. Every artefact records
> `data_source` and the console shows a `DEV DATA` banner when that field is not `ieee-cis`.
> This is the discipline that keeps us on the right side of the synthetic-data critique.

---

## 8. Stack

| Layer | Choice | Why not more |
|---|---|---|
| Core | Python 3.12, numpy, pandas, scipy | — |
| Model | LightGBM, scikit-learn | Native missing-value handling matters — we mask features deliberately |
| Conformal | hand-rolled, ~80 lines | Short enough to write, and you can defend every line under questioning |
| Charts | matplotlib | Three charts decide this. Make them excellent. |
| Console | Streamlit | Fastest path to the ρ slider |
| API | FastAPI | Only to produce a real p50/p99 latency number |
| **Not used** | Kafka · Docker · Postgres · Redis · MLflow · React · PyTorch | None changes a measured result in the time available |

---

## 9. Commands

```bash
python scripts/block0_audit.py --dev        # identity-coverage audit + config freeze
python scripts/block1_baseline.py --dev     # split, train, PR-AUC / P@k
python scripts/block2_conformal.py --dev    # marginal vs Mondrian coverage
python scripts/block3_shift.py --dev        # τ sweep → Graph 1 + Graph 2
python scripts/block4_cost.py --dev         # ₹ model → Graph 3
python -m pytest tests/ -v                  # property + leakage tests
streamlit run app/console.py                # console
```

Drop `--dev` once `data/train_transaction.csv` exists.

---

## 10. What is deliberately not here

Graph/GNN features. Per-agent-operator cells. KYA integration. Razorpay API integration.
Multi-merchant segmentation. Transformer base models. These are the V2–V5 roadmap in the strategy
brief and **none of them belongs in this build**. The danger to this project is not that it is too
simple — it is that it becomes so elaborate that it fails to produce one clean experimental result.

---

*Status: Block 0 in progress.*
