# Dhruva — Handoff (session 1, 20 Aug 2026)

**State: Blocks 0–5 complete on real IEEE-CIS data. All 22 tests pass. HEAD `e3fee68`.**

Run `git log --oneline` for the commit-by-commit record; each message states what was found and
what was wrong with it.

---

## Where the hypotheses stand

| | Verdict | Evidence |
|---|---|---|
| **H1** calibration degrades faster than discrimination | **REFUTED** | PR-AUC 0.5233 → 0.5109 at full masking (2.4%); ECE non-monotone 0.0036–0.0042. R is noise/noise. Underpowered by construction: only 24.4% of rows carry identity data, so τ is a no-op on three-quarters of the test set. |
| **H2** pooled calibration under-covers fraud | **SUPPORTED** | Marginal CP: 0.891 marginal coverage, **0.139 on fraud**. Class-conditional restores it to 0.868 for +5.7pp review volume. |
| **H3a** conditioning restores coverage | **PARTIAL** | True for **ProductCD** segments (worst cell deviation 0.083 vs 0.211 class-only). **False for the identity split** it was framed around — that arm scores 0.263, worse than doing nothing. |
| **H4** positive net rupees | **REFUTED** | D1 costs ₹1.53M *more* than the Bayes baseline. Sign stable across ±50% sweeps on all three cost constants. |

**Headline for the submission:** *conformal calibration conditioned on the right segment
substantially improves per-cell coverage, and at α = 0.10 it costs more money than a plain
cost-optimal threshold.* That is a coherent, honest, useful negative result — and it directly
answers the track's "honest metrics including false-positive cost" bar.

---

## Two corrections made to our own work

**Block 3's headline was circular.** It measured coverage on the same identity cells the arm had
calibrated on, so the arm was grading itself. On a neutral fine grid (ProductCD × identity ×
class) identity-conditioning is *worse* than class-only. Corrected in `e3fee68`.

**τ is not a pure identity ablation.** It also compresses block-D timing on every shifted row, so
76.7% of identity-*absent* rows also change score. Documented; matters for any τ claim.

---

## Bugs found and fixed (all have regression tests)

1. `aci_update` took target *coverage* where Gibbs–Candès takes target *miscoverage* — the
   controller ran backwards and drove coverage to ~10%. Silent in production.
2. `Encoder` detected categoricals via `dtype == object`, missing pandas 3.0's `str` dtype;
   numeric coercion then nulled ~15 columns including all of block M. Nothing raised.
3. `coverage()` applied the stop rule to the evaluation cell rather than the governing
   calibration cell.
4. `fetch_data.py` probed auth with `kaggle whoami`, which does not exist in CLI 2.x.
5. Block 5's first version let evaluation granularity follow calibration granularity.

---

## Next session — in priority order

1. **Amendment 1: cost-driven per-class α.** Tight on legit, loose on fraud, derived from the
   cost matrix rather than fixed at 0.10. Very likely flips the economics. **Must go through the
   amendment process** — append to `amendments` in `config.yaml` with timestamp and reason,
   re-run Block 0 to re-freeze, and report *both* the pre-registered α=0.10 result and the
   amended one side by side. Do not edit α in place.
2. **Reframe the narrative** to segment-conditional calibration. Drop agent framing from the
   headline; keep agentic commerce as motivation only. ProductCD is a real, interpretable,
   deployable segment — this is a strength, not a retreat.
3. **External validation:** run Block 4 on ULB (already downloaded, works for cost though not τ).
4. **Language fix:** "no retraining" → "no gradient-based refitting of the base model."
   Recalibration *is* learning and a sharp judge will say so.
5. Optional: Block 6 (ACI + γ sensitivity), Block 7 (model-agnosticism), Block 8 (console).

---

## Environment

- Code: `C:\Users\Chirag V Rao\OneDrive\ドキュメント\dhruva` (git, 6 commits)
- Data: `C:\Users\Chirag V Rao\dhruva-data` — outside OneDrive deliberately; gitignored
  - `train_transaction.csv` 683 MB, `train_identity.csv` 27 MB, `ulb_creditcard.parquet` 72 MB
  - ULB must come from the **raw ARFF** — OpenML flags `Time` as `row_id_attribute`, so
    `fetch_openml` silently drops it and the chronological split has nothing to sort on.
- Kaggle: OAuth via `kaggle auth login`. Two API tokens were exposed during setup and expired.
- `python -m pytest tests/ -q` → 22 passed.

---

## Standing discipline

- Every artefact records `data_source`; only `ieee-cis` is reportable.
- `results/protocol.lock` hashes the frozen constants; blocks refuse to run if one changed.
- Report refutations as prominently as confirmations. Four blocks in, two hypotheses are dead and
  one of our own headlines has been retracted — that record *is* the credibility.
