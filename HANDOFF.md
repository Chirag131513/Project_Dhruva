# Dhruva — Handoff

**Read `RESULTS.md` §0 first. It is the result. Then this file.**

State: Blocks 0–12 complete on real IEEE-CIS. 22 tests pass. Deployable API exists
(`dhruva/gate.py`), latency measured, dashboard built. **The science is finished — do not run
more experiments.** The documentation debt is **cleared** (see the bottom); two provenance gaps
were found while clearing it, one of which is worth a single 25-minute re-run if you want the
strongest possible answer to the cost-assumptions question.

**Step one is still to read the submission form.** Nobody has.

Competition: Razorpay AI Buildathon, Track 02 (AI Risk Manager). Applications close
**5 September 2026**. Submission format unknown — nobody has read the form yet. That is step one.

---

## The claim, in its current and final form

> Every payments team already has a review queue and fills it by sorting on risk score or
> transaction size. **At the queue sizes real teams actually run, those policies lose money.**
> Choosing correctly is worth **6–8% of realised loss** — and the advantage disappears only at
> queue sizes nobody can staff.

Net benefit vs a per-transaction cost-optimal Bayes threshold (₹3,752,646, no queue), 5 seeds,
every policy escalating the **same volume**:

| queue policy | 1% | 2% | 5% | 10% |
|---|---|---|---|---|
| **nearest the cost-optimal cut** *(ours)* | **+219,440** | **+405,514** | **+798,331** | **+1,072,836** |
| most suspicious first *(what most teams do)* | **−89,329** | **−15,091** | +577,447 | +1,038,038 |
| biggest amount first | +1,899 | +108,327 | +128,600 | +63,451 |
| most rupees at stake | **−87,962** | **−75,921** | +117,620 | +101,915 |

Advantage over the **best rival at each capacity**: 5.8% (1%) · **7.9% (2%)** · 5.9% (5%) ·
0.9% (10%). **Peaks at 2%, not monotone.**

### Where the model is blind — the half that needs none of our code

| segment | share of traffic | error rate | share of ₹ lost | concentration |
|---|---|---|---|---|
| ProductCD **C** | 10.3% | **10.61%** | 19.4% | **1.9×** |
| **credit** cards | 23.2% | **6.65%** | 38.0% | **1.6×** |
| **₹270–5,367** (top decile) | 10.0% | 5.48% | 20.8% | **2.1×** |

Product C carries 4.4× the error rate of product W. Method borrowed from arXiv:2607.06605, which
localises confident errors to molecular scaffolds; the payments analogue is business segments.

### Deployable surface

`dhruva/gate.py` — three lines, no retraining, **no labels needed to fit** (the cutoff is a
quantile of an unlabelled ranking, so it refits on recent traffic without waiting for
chargebacks). Measured **p50 14.6 µs / p99 24.1 µs** per decision. Every decision returns an
audit record via `gate.explain()`.

---

## What we are NOT claiming — enforce this

- **Not 28%.** That compared against a baseline with *no review queue*, which nobody runs. It is
  the retired framing. Any document still saying 28% is stale.
- **Not that escalation is new.** Every team escalates.
- **Not that conformal prediction is our method.** It finished second-worst of four signals.
- **Not novelty in the method.** `band` is one line. The contribution is the measurement, the
  negative result, and the blindness map.
- **Nothing about Vulcan.** We have no evidence about any production model and cannot get any.

---

## How the project got here (so you don't re-litigate it)

Designed around conformal prediction. A Stage-1 audit found the headline pre-empted four times in
July–August 2026. A kill test was **pre-registered**; K2, K3, K4 and K5 fired, and a one-line rule
beat conformal 22× (p = 0.0020). Reframed around what the data supported. Then the user asked the
right question — *"are we producing real value?"* — which exposed that our baseline had no queue
at all. Block 12 fixed that comparison and shrank the headline from 28% to 6–8%. **That shrinkage
was correct.** Do not try to grow it back.

**Hypotheses:** H1 refuted · H2 supported · H3a supported for ProductCD only · H3b, H5 never
tested · H4 refuted. One of our own headlines was retracted after it was found to be scoring
itself on the cells it had calibrated on.

---

## Known gaps — stated, never hidden

- **`band` was written as a strawman for the kill test and it won.** Signal space barely explored;
  a rejector trained on realised cost might beat it. Unrun.
- **Why conformal fails is a hypothesis, not a measurement.** Our reading: it nominates cases
  where the *classes* are hard to separate, while the money sits near the *cost-optimal cut*.
- **Transfer evidence is n = 3 with two broken models** (logreg and rf run at 69% and 42% error
  because `class_weight="balanced"` pushes them past the cost cut). Directionally encouraging,
  not proof.
- **Our baseline is 0.6% favourable to us** — a flat 0.10 threshold beats it by ₹22,709, found by
  sweeping the test set. Disclosed in RESULTS §0b; 47× smaller than the effect.
- **One dataset for the positive result.** ULB fails entirely below ~0.1% prevalence.
- **`disagree` is a boosting-stage-spread proxy**, not a reimplementation of DAUNT.
- Two of five bugs (RESULTS §7) are script-level fixes with no regression test.

---

## DOCUMENTATION DEBT — CLEARED 23 August 2026

Every item below is migrated to the Block 12 framing. Nothing in the repo now says 28% except
the places that explicitly retire it.

| File | Done |
|---|---|
| **The Runbook** (artifact `3d4cfb2f-…`) | Rewritten. **Source now lives in the repo at `RUNBOOK.html`** — edit that and republish to the same URL, so artifact and repo cannot drift again. New beat at 0:35 concedes the queue; the slider parks at **2%**, not 10% |
| `START_HERE.md` Parts 1, 2, 3, 4, 5, 6, 7 | All migrated. Part 2 gains Blocks 10–12 |
| `RESULTS.md` §0b | Opener rewritten; notes Block 10 predates the reframe but still bears on §0 |
| `RESULTS.md` §10 | **Was itself contradicting §0** — the row `"we save ₹X" → "roughly cost-neutral"` was conformal-era discipline. Replaced |
| `RESULTS.md` §12 | Was missing Blocks 10–12 and still pointed at the retired Streamlit console |
| `results/figures/graph5_triage.png` | Rebuilt from `block12_policies.json`. `make_figures.py` rewritten — no experiment re-run |
| `IMPLEMENTATION.md` | Carries a HISTORICAL banner |

22 tests still pass.

### Two provenance gaps found while migrating — both unresolved

Neither was on the list above. Both are claims the repo cannot back, and both were sitting in
the presentation layer.

1. **Band's ±50% cost sweep was never run.** `scripts/block9_triage.py:220` hardcodes
   `ambiguity("conformal", ...)` inside the K5 loop, so every number in
   `block9_triage.json["sensitivity"]` is the *conformal* arm's. "Band: no flips" was asserted in
   `RESULTS.md` §1, `START_HERE` Parts 4 and 5, and the runbook — the runbook also carried a range
   (`+513,576 … +1,409,008`) that **appears nowhere in the repo**. All of it is struck. The docs
   now say "we did not measure that."
   **Fix: parameterise line 220 and re-run Block 9.** One line, ~25 min. This is the single
   highest-value experiment left, because it is the one a judge is most likely to probe.
2. **Block 11 has no script.** Commit `881438b` added `results/block11_concentration.json` and the
   §0b prose and nothing else. The transfer table (0.7× → 1.1× → 8.6×) cannot be regenerated or
   audited. Flagged in `RESULTS.md` §12, §10, `START_HERE` Part 2, and the runbook.

Neither was run here: the standing instruction was **do not run more experiments**, and (1) is an
experiment. Both are recorded as gaps instead, which is what the rest of the project does.

---

## Environment

- Code: `OneDrive\ドキュメント\dhruva` (git)
- Data: `C:\Users\Chirag V Rao\dhruva-data` — outside OneDrive deliberately, gitignored
  - `train_transaction.csv` 683 MB · `train_identity.csv` 27 MB · `ulb_creditcard.parquet` 72 MB
  - ULB must come from the **raw ARFF**: OpenML flags `Time` as `row_id_attribute`, so
    `fetch_openml` silently drops it and the chronological split has nothing to sort on.
- Kaggle: OAuth (`kaggle auth login`). Two API tokens were exposed during setup — both expired.

## Demo

`app\dashboard.html` already exists — **double-click it**. To rebuild:
`export_console.py` → `measure_gate.py` → `build_dashboard.py` (the middle one is required;
the build refuses without it).

Fallback if it won't open: the tables in `RESULTS.md` §0 carry the entire talk.

## Standing discipline

- Only `data_source: ieee-cis` is reportable.
- `results/protocol.lock` hashes the frozen constants; blocks refuse to run if one changed.
- `RESULTS.md` §10 governs slides and speech, not just the document.
- Two hypotheses died, a headline was retracted, external validation failed, the method the
  project was named after lost, and the headline number shrank from 28% to 7.9% under scrutiny.
  **That record is the credibility. Do not sand it off.**
