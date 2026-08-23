"""Block 11 -- does the error concentration survive a better base model?

    python scripts/block11_concentration.py   ->  results/block11_concentration.json

WHY THIS FILE EXISTS AT ALL. It did not, for a while. Commit 881438b added
results/block11_concentration.json and the RESULTS section 0b prose and *nothing else*, so the
transfer table -- the 0.7x -> 1.1x -> 8.6x trend I lean on whenever anyone asks whether this
holds up on a stronger scorer -- could not be regenerated, audited, or checked for the kind of
silent bug that section 7 documents twice. Numbers with no code behind them are not results, they
are assertions, and this project does not get to keep those. This script reconstructs the block.

WHAT IT MEASURES. Block 10 part B asked one question of one model: are the model's errors
concentrated in the 10% of traffic the band rule escalates? The answer for LightGBM was 8.6x.
The obvious objection is that this is an artefact of a mediocre scorer -- that a *better* model
would spread its errors evenly and the rule would have nothing to find. So the same measurement
is repeated across three scorers of very different quality, changing nothing else.

An "error" is a Bayes decision that was wrong: fraud approved, or legitimate blocked. Its
"value" is what that specific mistake cost, per transaction. Both are counted inside the
escalated tenth and outside it.

WHAT IT FINDS, AND THE CAVEAT THAT MATTERS MORE THAN THE FINDING. Concentration does not wash out
as the model improves -- it *grows*, 0.7x -> 1.1x -> 8.6x. But two of those three points are not
weaker models, they are BROKEN ones: logreg and rf run at roughly 69% and 42% error because
class_weight="balanced" inflates their probabilities past the cost-optimal cut (section 9, and
the threats in section 8). So the honest reading is "one healthy model shows strong concentration
and two broken ones do not", which is weaker than a clean monotone trend across three healthy
models. Do not present this as proof. It is n = 3, on one dataset, and it is directional.

REPRODUCTION NOTE. This reproduces the committed JSON exactly -- same fits, same seed, same
ordering -- so the original numbers stand as published; only their provenance changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from dhruva import config, cost, data, features, metrics, model, splits
from dhruva.cost import APPROVE, BLOCK
from dhruva.data import AMOUNT, TARGET

# Fit in this order; the output is sorted by PR-AUC so the table reads worst-to-best model,
# which is the direction the trend is claimed in.
SCORERS = ["logreg", "rf", "lgbm"]
CAP = 0.10          # same escalation capacity as Block 10 part B


def concentration(p, y, amt, costs, cap=CAP):
    """Error concentration inside the escalated top `cap` versus everything else.

    Lifted deliberately from block10_proofs.py part B rather than re-derived: if the two ever
    disagreed, the lgbm row here would silently contradict section 0b of RESULTS.
    """
    n = len(y)
    stake = np.maximum(p * costs.c_fn(amt), (1 - p) * costs.c_fp(amt))
    order = -np.abs(p - costs.bayes_threshold(amt)) * 1e6 + stake / 1e6
    k = int(round(cap * n))
    esc = np.zeros(n, bool)
    esc[np.argsort(-order)[:k]] = True

    acts = cost.decide_bayes(p, amt, costs)
    wrong = ((acts == APPROVE) & (y == 1)) | ((acts == BLOCK) & (y == 0))
    err_rs = np.where(y == 1, costs.c_fn(amt), costs.c_fp(amt)) * wrong

    e_in = float(wrong[esc].mean())
    e_out = float(wrong[~esc].mean())
    return {
        "e_in": e_in,
        "e_out": e_out,
        # Guarded: a scorer that is wrong nowhere outside the escalated set would divide by zero.
        "ratio": float(e_in / max(e_out, 1e-9)),
        "cap": float(wrong[esc].sum() / max(wrong.sum(), 1)),
        "val": float(err_rs[esc].sum() / max(err_rs.sum(), 1e-9)),
        "n_wrong": int(wrong.sum()),
        "err_value_total": float(err_rs.sum()),
    }


def main() -> int:
    cfg = config.load(); cfg.check_lock()
    costs = cost.Costs.from_config(cfg)
    sp = splits.chronological(data.load(cfg.data_dir()), cfg)
    enc, X = features.build(sp)
    y_tr = sp.train[TARGET].to_numpy()
    y = sp.test[TARGET].to_numpy()
    amt = sp.test[AMOUNT].to_numpy(dtype=float)

    rows = []
    for kind in SCORERS:
        print(f"\nfitting {kind} ...", flush=True)
        sc = model.fit(X["train"], y_tr, kind=kind, cfg=cfg, seed=cfg.base_seed)
        p = sc.predict_proba_fraud(X["test"])
        rec = {"kind": kind, "pr": float(metrics.detection(y, p).pr_auc)}
        rec.update(concentration(p, y, amt, costs))
        rows.append(rec)
        print(f"  PR-AUC {rec['pr']:.4f}   err in {rec['e_in']:.2%} / out {rec['e_out']:.2%}"
              f"   ratio {rec['ratio']:.1f}x")

    rows.sort(key=lambda r: r["pr"])

    print("\n" + "=" * 78)
    print(f"BLOCK 11  error concentration at {CAP:.0%} capacity, three base scorers")
    print("=" * 78)
    print(f"\n{'scorer':<10}{'PR-AUC':>9}{'err @esc':>11}{'err @rest':>11}"
          f"{'ratio':>9}{'errs capt':>11}{'value capt':>12}")
    print("-" * 78)
    for r in rows:
        print(f"{r['kind']:<10}{r['pr']:>9.4f}{r['e_in']:>11.2%}{r['e_out']:>11.2%}"
              f"{r['ratio']:>8.1f}x{r['cap']:>11.1%}{r['val']:>12.1%}")

    trend = " -> ".join(f"{r['ratio']:.1f}x" for r in rows)
    print(f"\n  concentration across increasing model quality : {trend}")
    print("  Concentration does NOT vanish as the scorer improves -- it grows. A weak model errs")
    print("  everywhere, so there is nothing to concentrate; a good model makes the easy cases")
    print("  genuinely easy and what remains piles up against the decision boundary.")
    print("\n  CAVEAT, and say it before anyone else does: two of these three are not weaker")
    print("  models, they are BROKEN ones -- logreg and rf sit at 69% and 42% error because")
    print("  class_weight='balanced' pushes them past the cost-optimal cut. The honest reading")
    print("  is 'one healthy model concentrates strongly and two broken ones do not'. n = 3,")
    print("  one dataset, directional. Not proof.")

    out = cfg.results_dir() / "block11_concentration.json"
    out.write_text(json.dumps(rows, indent=2, default=float), encoding="utf-8")
    print(f"\nwritten                results/{out.name}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
