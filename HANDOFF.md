# Dhruva — Handoff

**State: complete and audited. HEAD `f2df785`. 22 tests passing.**

Blocks 0–7 run on real IEEE-CIS. Amendment 1 applied and reported alongside the pre-registered
arm. Console built. `RESULTS.md` written, audited against a clean re-run, and corrected.

Read `RESULTS.md` first — it is the authoritative record. `PROTOCOL.md` is the pre-registration.
`git log --oneline` is a demo artefact in its own right.

---

## Hypothesis standing

| | Verdict |
|---|---|
| **H1** calibration degrades faster than discrimination | **REFUTED** — PR-AUC 0.5233 → 0.5109 at full masking; ECE non-monotone. Underpowered by construction: only 24.4% of rows carry identity data. |
| **H2** pooled conformal under-covers fraud | **SUPPORTED** — 0.891 marginal / **0.139 fraud** |
| **H3a** conditioning restores coverage | **SUPPORTED for ProductCD** (0.083 vs 0.211 worst-cell); **FALSE for the identity split** (0.263) |
| **H3b** online ACI under drift | **NOT TESTED** — scope closed when H1 fell |
| **H4** positive net rupees | **REFUTED** — α=0.10 identity-segmented costs ₹1.53M more |
| **H5** calibration approaches oracle retraining | **NOT TESTED** — oracle arm designed, never run |

**Defensible claim:** segment-conditional conformal abstention with a capacity-derived per-class
α (0.02077) is roughly **cost-neutral** against a per-transaction Bayes threshold, while
delivering a stated per-segment coverage level a bare threshold cannot state. It buys recall
58.7% vs 49.7% for +1.34pp FPR at break-even. **Not** "it saves money" — the +₹27,137 margin's
sign flips on all four cost constants.

---

## Audit result (clean re-run, `f2df785`)

Every headline number reproduced **exactly** — 18 checked, zero mismatches. Determinism confirmed
(block1 and block4 artefacts byte-identical across runs). Leakage clean: 0 shared TransactionIDs,
7.00d delay gap, `dhruva/` never touches test labels. Bugs 1–3 mutation-verified — reverting each
fix makes a named test fail.

**Known, unactioned:** committed artefacts carry `config_hash 17917c76a46ada55` (pre-Amendment 1);
current config hashes to `d38888c9d05d398c`. Numbers are identical — only the provenance stamp
differs. A fresh `check_lock()` on those files would flag them. Re-stamping is a metadata
refresh, not a result change; left as a decision.

---

## What is left, in priority order

1. **Nothing is required.** The submission is complete. Everything below is optional.
2. **Prune fixture leftovers.** `results/block2_dev-fixture.json` and `block3_dev-fixture.json`
   are labelled but sit beside real ones. Delete before handing the repo over.
3. **Run the E7 three-scorer ablation** — the single-base-learner threat in RESULTS §8 is the
   most substantive gap a reviewer can name. Cheap: `block1_baseline.py --kind logreg|rf`.
4. **Run the oracle-retrain arm (H5).** Answers "why not just retrain" with a number instead of
   an argument.
5. **Regression tests for bugs 4 and 5** — currently script-level fixes with no coverage, and
   RESULTS §7 says so explicitly.

**Do not** add graph/GNN features, per-agent cells, ACI, or KYA. They were cut deliberately and
the write-up does not depend on them.

---

## Demo

`streamlit run app/console.py` after `python scripts/export_console.py`.

The α_legit slider is the demo — drag it and fraud coverage holds at 0.878 while FPR and cost
climb. The ρ slider planned in `IMPLEMENTATION.md` is dead; τ moved almost nothing.

Runbook (six-minute script + the ten hardest questions with measured answers):
<https://claude.ai/code/artifact/3d4cfb2f-f0ce-4aa1-ad81-1a5cbb4d060d>

---

## Environment

- Code: `OneDrive\ドキュメント\dhruva` — git, 11 commits
- Data: `C:\Users\Chirag V Rao\dhruva-data` — outside OneDrive deliberately, gitignored
  - `train_transaction.csv` 683 MB · `train_identity.csv` 27 MB · `ulb_creditcard.parquet` 72 MB
  - ULB must come from the **raw ARFF**: OpenML flags `Time` as `row_id_attribute`, so
    `fetch_openml` silently drops it and the chronological split has nothing to sort on.
- Kaggle: OAuth (`kaggle auth login`). Two API tokens were exposed during setup — both expired.

---

## Standing discipline

- Only `data_source: ieee-cis` is reportable. The fixture is plumbing.
- `results/protocol.lock` hashes the frozen constants; blocks refuse to run if one changed.
- The §9 "what not to say" table in `RESULTS.md` governs slides and speech, not just the document.
- Report refutations as prominently as confirmations. Two hypotheses died, one headline was
  retracted, and external validation failed — that record is the credibility.
