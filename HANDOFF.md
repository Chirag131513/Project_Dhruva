# Dhruva — Handoff

**Read `RESULTS.md` §0 first. It is the result. Then this file.**

State: Blocks 0–12 complete on real IEEE-CIS. 22 tests pass. Deployable API exists
(`dhruva/gate.py`), latency measured, dashboard built. **The science is finished — do not run
more experiments.** The documentation debt is **cleared** (see the bottom). Two provenance gaps
were found while clearing it — claims the repo could not regenerate — and **both have since been
closed by measurement**, with the original numbers reproducing exactly. **Every block in the
write-up now runs.**

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
| **nearest the cost-optimal cut** *(this project)* | **+219,440** | **+405,514** | **+798,331** | **+1,072,836** |
| most suspicious first *(what most teams do)* | **−89,329** | **−15,091** | +577,447 | +1,038,038 |
| biggest amount first | +1,899 | +108,327 | +128,600 | +63,451 |
| most rupees at stake | **−87,962** | **−75,921** | +117,620 | +101,915 |

Advantage over the **best rival at each capacity**: 5.8% (1%) · **7.9% (2%)** · 5.9% (5%) ·
0.9% (10%). **Peaks at 2%, not monotone.**

### Where the model is blind — the half that needs none of my code

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

## What I am NOT claiming — enforce this

- **Not 28%.** That compared against a baseline with *no review queue*, which nobody runs. It is
  the retired framing. Any document still saying 28% is stale.
- **Not that escalation is new.** Every team escalates.
- **Not that conformal prediction is my method.** It finished second-worst of four signals.
- **Not novelty in the method.** `band` is one line. The contribution is the measurement, the
  negative result, and the blindness map.
- **Nothing about Vulcan.** I have no evidence about any production model and cannot get any.

---

## How the project got here (so you don't re-litigate it)

Designed around conformal prediction. A Stage-1 audit found the headline pre-empted four times in
July–August 2026. A kill test was **pre-registered**; K2, K3, K4 and K5 fired, and a one-line rule
beat conformal 22× (p = 0.0020). Reframed around what the data supported. Then the user asked the
right question — *"am I producing real value?"* — which exposed that my baseline had no queue
at all. Block 12 fixed that comparison and shrank the headline from 28% to 6–8%. **That shrinkage
was correct.** Do not try to grow it back.

**Hypotheses:** H1 refuted · H2 supported · H3a supported for ProductCD only · H3b, H5 never
tested · H4 refuted. One of my own headlines was retracted after it was found to be scoring
itself on the cells it had calibrated on.

---

## Known gaps — stated, never hidden

- **`band` was written as a strawman for the kill test and it won.** Signal space barely explored;
  a rejector trained on realised cost might beat it. Unrun.
- **Why conformal fails is a hypothesis, not a measurement.** My reading: it nominates cases
  where the *classes* are hard to separate, while the money sits near the *cost-optimal cut*.
- **Transfer evidence is n = 3 with two broken models** (logreg and rf run at 69% and 42% error
  because `class_weight="balanced"` pushes them past the cost cut). Directionally encouraging,
  not proof.
- **My baseline is 0.6% favourable to me** — a flat 0.10 threshold beats it by ₹22,709, found by
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
| `RESULTS.md` §10 | **Was itself contradicting §0** — the row `"I save ₹X" → "roughly cost-neutral"` was conformal-era discipline. Replaced |
| `RESULTS.md` §12 | Was missing Blocks 10–12 and still pointed at the retired Streamlit console |
| `results/figures/graph5_triage.png` | Rebuilt from `block12_policies.json`. `make_figures.py` rewritten — no experiment re-run |
| `IMPLEMENTATION.md` | Carries a HISTORICAL banner |

22 tests still pass.

### Two provenance gaps found while migrating — both now closed

Neither was on the list above. Both were claims the repo could not back, and both were sitting in
the presentation layer. Both have since been measured, and in both cases the original numbers
turned out to be right — what was missing was the evidence, which is not the same thing.

1. ~~**Band's ±50% cost sweep was never run.**~~ **CLOSED — run 23 August 2026.** The K5 loop
   hardcoded `ambiguity("conformal", ...)`, so every persisted sweep number was the conformal
   arm's while three documents asserted "Band: no flips" and the runbook carried a range
   (`+513,576 … +1,409,008`) that appeared nowhere in the repo. It was struck as unsupported.
   The loop now sweeps both arms and it has been re-run at 10 seeds.
   **Result: band has no sign flips on any of the four constants**, range
   **+₹513,576 … +₹1,409,008** — *exactly* the struck range. **The old number was right and its
   evidence was missing.** Striking it was still correct on the evidence available then; a
   correct number with nothing behind it is not a reportable one.
   K5 is still *scored* on conformal, the arm it was pre-registered against. Two edges remain,
   stated in §1: single seed at 10% capacity, and it sweeps the margin over the *no-queue*
   baseline rather than over the best rival **queue policy**, which is what §0 reports.
   The re-run also reproduced every other Block 9 figure **bit for bit** — `b1_mean`, K3's delta,
   CI and p-value, all sixteen net cells, and conformal's own sweep.
2. ~~**Block 11 has no script.**~~ **CLOSED — rewritten 24 August 2026.** Commit `881438b` added
   `results/block11_concentration.json` and the §0b prose and nothing else, so the transfer table
   (0.7× → 1.1× → 8.6×) could not be regenerated or audited. `scripts/block11_concentration.py`
   now rebuilds it, and regenerating **reproduced all six fields on all three scorers exactly** —
   every digit of PR-AUC, both error rates, the ratio, and both capture shares. The published
   numbers stand; only their provenance changed. It shares its `concentration()` definition with
   Block 10 part B so the two cannot silently disagree, and its new `n_wrong` /
   `err_value_total` fields independently corroborate §0b (lgbm: 3,847 errors, ₹3,718,531).
   The caveat is unchanged and still leads: n = 3, and two of the three are **broken** models.

Neither was run here: the standing instruction was **do not run more experiments**, and (1) is an
experiment. Both are recorded as gaps instead, which is what the rest of the project does.

---

## Environment

- Code: `OneDrive\ドキュメント\dhruva` (git)
- Data: `C:\Users\Chirag V Rao\dhruva-data` — outside OneDrive deliberately, gitignored.
  **`config.yaml` no longer hardcodes this.** It shipped an absolute path with the author's
  username in it, which made the public repo unrunnable for anyone else. The default is now the
  relative `data/`; set `DHRUVA_DATA` to override, once per terminal:
  `$env:DHRUVA_DATA = "C:\Users\Chirag V Rao\dhruva-data"`. `paths:` sits outside the hashed
  `frozen:` block, so this did not disturb `protocol.lock` — the hash is still `d38888c9d05d398c`.
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
