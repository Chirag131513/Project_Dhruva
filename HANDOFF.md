# Dhruva — Handoff

**State: complete. Blocks 0–9 on real IEEE-CIS. HEAD is clean, 22 tests passing.**

Read `RESULTS.md §0` first — it is the result. `START_HERE.md` is how to run it.
`git log --oneline` is a demo artefact in its own right.

---

## The result

> Under a hard analyst-capacity limit, **choosing which cases a human sees is worth 28% of a
> merchant's realised fraud loss** — and the signal that wins is the simplest one tested, not the
> one the 2026 literature is built around.

Net benefit vs a per-transaction cost-optimal Bayes threshold, 10 seeds, identical escalation
volume per arm:

| signal | 1% | 2% | 5% | 10% |
|---|---|---|---|---|
| **band** — \|p − t(x)\| | +214,512 | +396,334 | +787,307 | **+1,061,079** |
| disagree (DAUNT-style proxy) | +65,215 | +169,446 | +458,320 | +788,055 |
| conformal | +38,995 | +72,319 | +87,058 | +47,755 |
| random | −24,344 | −50,752 | −131,542 | −261,883 |

Four claims, all verified against `block9_triage.json`:

1. **Monotone and robust** — 5.7 / 10.6 / 21.0 / 28.4% of loss, no sign flips under ±50% on any
   of the four cost constants (range +₹513,576 to +₹1,409,008).
2. **The signal is the whole value** — random escalation *loses* ₹261,883; band beats it by
   ₹1,322,962, p = 0.0020.
3. **A one-line rule beat conformal 22×** (p = 0.0020, the minimum achievable at n = 10).
4. **The operating point strictly dominates** — 72.4% recall vs 49.7% *while halving* FPR,
   1.85% → 0.88%.

---

## How the project got here

It was designed around conformal prediction. The Stage-1 audit found the headline
(*marginal CP under-covers the minority class*) pre-empted four times in July–August 2026, and a
positive result sitting unreported in `block4_ieee-cis.json`. A kill test was pre-registered;
**K2, K3, K4 and K5 all fired** and conformal finished second-worst. The project was reframed
around what the data actually supported.

**Hypotheses:** H1 refuted · H2 supported · H3a supported for ProductCD only · H3b and H5 never
tested · H4 refuted. One of our own headlines retracted after it was found to be measuring
itself.

---

## Still true, still ours

- **The exact two-term identity**, correcting the published one-term form. Residual 0.00000000;
  their version under-predicts our shortfall by 35.2%. `RESULTS.md §2`.
- **The failure scales with model quality** — PR-AUC 0.174 → gap 0.106; 0.523 → 0.752. `§9`.
- **The prevalence floor** — below ~0.1% fraud the method cannot run at all (ULB, 0/11 cells
  reportable). `§5`.

---

## Known gaps — stated, not hidden

- **`band` was written as a strawman for the kill test and it won.** The signal space is barely
  explored; a rejector trained directly on realised cost might beat it. Unrun.
- **Why conformal fails is a hypothesis, not a measurement.** Our reading: it nominates cases
  where the *classes* are hard to separate, while the money sits near the *cost-optimal cut* —
  different sets. Unmeasured.
- **`disagree` is a boosting-stage-spread proxy**, not a reimplementation of DAUNT.
- **Latency is never measured.** We cite the 2026 review for saying no fraud paper reports
  per-decision latency, and we don't either. Either instrument it or drop the criticism.
- **`IMPLEMENTATION.md` is stale** — it still describes the ρ-slider demo, which is dead. It is
  a historical design document now; `START_HERE.md` supersedes it.
- Two of five bugs (Section 7) are script-level fixes with no regression test.

---

## Environment

- Code: `OneDrive\ドキュメント\dhruva` — git
- Data: `C:\Users\Chirag V Rao\dhruva-data` — outside OneDrive deliberately, gitignored
  - `train_transaction.csv` 683 MB · `train_identity.csv` 27 MB · `ulb_creditcard.parquet` 72 MB
  - ULB must come from the **raw ARFF**: OpenML flags `Time` as `row_id_attribute`, so
    `fetch_openml` silently drops it and the chronological split has nothing to sort on.
- Kaggle: OAuth (`kaggle auth login`). Two API tokens exposed during setup — both expired.

## Demo

```
python scripts/export_console.py
python scripts/build_dashboard.py
```
then double-click `app\dashboard.html`. Capacity slider is the demo. Fallback if it fails:
`results\figures\graph5_triage.png` carries the entire talk.

The Streamlit console (`app/console.py`) still exists but is built around the α slider and the
losing method. **Do not demo it.**

## Standing discipline

- Only `data_source: ieee-cis` is reportable.
- `results/protocol.lock` hashes the frozen constants; blocks refuse to run if one changed.
- `RESULTS.md §10` governs slides and speech, not just the document.
- Two hypotheses died, a headline was retracted, external validation failed, and the method the
  project was named after lost. **That record is the credibility.**
