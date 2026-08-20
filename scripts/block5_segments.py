"""Block 5 -- EXPLORATORY: which segmentation is actually doing the work?

    python scripts/block5_segments.py

STATUS: post-hoc and exploratory. Not pre-registered, not confirmatory. It was written after
seeing Block 3 and Block 4, to diagnose a confound found while auditing them, and it must be
reported under that label. Nothing here may be presented as a test of H1-H5.

THE QUESTION

Block 3 found that conditioning conformal calibration on identity-presence brings all four cells
near target. Block 0 then found the two populations differ in base rate (7.85% vs 2.09%), and an
audit found they differ almost totally in product mix: identity-absent rows are 98.5% ProductCD
'W', while identity-present rows are 43% 'C', 26% 'R', 23% 'H'.

So "identity present vs absent" may be a proxy for "which product". If ProductCD alone recovers
the effect, then the real variable is the product segment -- which is better news, not worse:
ProductCD is an interpretable field a payments team already has, rather than a property inferred
from missingness.

ARMS

  NONE        one pooled quantile per class            (= B3)
  IDENTITY    identity present / absent                (= D1, Block 3's arm)
  PRODUCT     ProductCD level
  BOTH        ProductCD x identity presence

Judged on: worst per-cell deviation from target, review rate, and realised rupees.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from dhruva import config, conformal, cost, data, features, model, shift, splits
from dhruva.data import AMOUNT, TARGET


def segments(df, kind: str) -> np.ndarray:
    if kind == "NONE":
        return np.full(len(df), "ALL")
    if kind == "IDENTITY":
        return shift.route(df)
    prod = df["ProductCD"].astype(str).to_numpy()
    if kind == "PRODUCT":
        return prod
    if kind == "BOTH":
        return np.char.add(np.char.add(prod, "/"), shift.route(df))
    raise ValueError(kind)



def _enough(eval_pop, y, cell, min_n: int) -> bool:
    """Is this EVALUATION cell large enough for its empirical coverage to mean anything?

    Distinct from the calibration stop rule: that one asks whether a quantile was estimated from
    enough points, this asks whether the measurement of coverage has enough points. Both matter
    and they are not the same cell.
    """
    import numpy as np
    pop, cls = cell
    return int(((np.asarray(eval_pop) == pop) & (np.asarray(y).astype(int) == int(cls))).sum()) >= min_n


def main() -> int:
    cfg = config.load()
    cfg.check_lock()
    alpha, target = cfg.alpha, 1.0 - cfg.alpha
    cap = float(cfg.frozen["review_cap_headline"])

    print("=" * 78)
    print("BLOCK 5  --  EXPLORATORY segmentation diagnostic  (post-hoc, not confirmatory)")
    print("=" * 78)

    df = data.load(cfg.data_dir())
    print(f"\nsource                 {df.attrs['data_source']}")

    sp = splits.chronological(df, cfg)
    enc, X = features.build(sp)
    y_cal, y_test = sp.cal[TARGET].to_numpy(), sp.test[TARGET].to_numpy()
    amt = sp.test[AMOUNT].to_numpy(dtype=float)

    scorer = model.fit(X["train"], sp.train[TARGET].to_numpy(),
                       kind="lgbm", cfg=cfg, seed=cfg.base_seed)
    p_test = scorer.predict_proba_fraud(X["test"])
    s_cal = conformal.nonconformity(scorer.predict_proba_fraud(X["cal"]))
    s_test = conformal.nonconformity(p_test)
    costs = cost.Costs.from_config(cfg)

    b1 = cost.realised_cost(cost.decide_bayes(p_test, amt, costs), y_test, amt, costs)
    print(f"B1 reference           Rs{b1['total']:,.0f}   "
          f"recall {b1['fraud_recall']:.1%}  FPR {b1['fpr']:.2%}")

    print(f"\n{'segmentation':<12}{'cells':>7}{'thin':>6}{'worst dev':>11}{'mean dev':>10}"
          f"{'review':>9}{'cost Rs':>13}{'vs B1':>12}")
    print("-" * 78)

    out = {}
    # THE YARDSTICK IS FIXED. Every arm is SCORED on the same fine cell definition
    # (ProductCD x identity x class); only the CALIBRATION granularity varies. Letting the
    # evaluation cells follow the calibration cells is not a fair comparison -- a coarsely
    # calibrated arm would be graded on coarse cells, where it trivially looks well covered,
    # while a finer arm is graded on cells that can individually miss. That is how the first
    # version of this script made the do-nothing arm appear best.
    eval_test = segments(sp.test, "BOTH")

    for kind in ("NONE", "IDENTITY", "PRODUCT", "BOTH"):
        pc, pt = segments(sp.cal, kind), segments(sp.test, kind)
        cal = conformal.calibrate(s_cal, y_cal, pc, alpha, min_cell_n=cfg.min_cell_n,
                                  class_conditional=True, population_conditional=True)
        sets = conformal.predict_set(s_test, pt, cal)
        # Scored on the fixed yardstick, with no calibration passed: the stop rule here would
        # be about this arm's own cells, which are not the cells being reported.
        cov = conformal.coverage(sets, y_test, eval_test, None)
        cov = {k: (v if _enough(eval_test, y_test, k, cfg.min_cell_n) else float("nan"))
               for k, v in cov.items()}

        devs = [abs(v - target) for v in cov.values() if not np.isnan(v)]
        acts = cost.decide_conformal(sets, p_test, amt, costs)
        acts, _ = cost.apply_capacity(acts, p_test, amt, costs, cap)
        c = cost.realised_cost(acts, y_test, amt, costs)

        out[kind] = {"cells": len(cal.q), "thin": len(cal.thin_cells()),
                     "worst_dev": max(devs) if devs else float("nan"),
                     "mean_dev": float(np.mean(devs)) if devs else float("nan"),
                     "review_rate": c["review_rate"], "cost": c["total"],
                     "recall": c["fraud_recall"], "fpr": c["fpr"],
                     "coverage": {f"{k[0]}|{k[1]}": v for k, v in cov.items()}}
        o = out[kind]
        print(f"{kind:<12}{o['cells']:>7}{o['thin']:>6}{o['worst_dev']:>11.3f}"
              f"{o['mean_dev']:>10.3f}{o['review_rate']:>9.1%}{o['cost']:>13,.0f}"
              f"{b1['total'] - o['cost']:>+12,.0f}")

    # ---- does identity add anything beyond product? -----------------------------------------
    print("\ndiagnosis")
    p_dev, i_dev, b_dev = out["PRODUCT"]["worst_dev"], out["IDENTITY"]["worst_dev"], out["BOTH"]["worst_dev"]
    print(f"  worst per-cell deviation:  IDENTITY {i_dev:.3f}   PRODUCT {p_dev:.3f}   "
          f"BOTH {b_dev:.3f}")
    if p_dev <= i_dev + 0.01:
        print("  ProductCD alone matches or beats identity-presence. The identity split was")
        print("  very likely acting as a proxy for the product segment, and the honest")
        print("  framing is segment-conditional calibration on a field the merchant already has.")
    else:
        print("  Identity-presence outperforms ProductCD, so it carries information the product")
        print("  field does not. The confound is real but not the whole story.")
    if b_dev < min(p_dev, i_dev) - 0.01:
        print("  Combining both is better than either, so they carry partly distinct signal.")
    else:
        print("  Combining adds nothing over the better single split -- they are largely")
        print("  redundant, which is what a proxy relationship looks like.")

    cheapest = min(out, key=lambda k: out[k]["cost"])
    print(f"\n  cheapest arm: {cheapest} at Rs{out[cheapest]['cost']:,.0f} "
          f"(B1 = Rs{b1['total']:,.0f})")
    if out[cheapest]["cost"] > b1["total"]:
        print("  Every conformal segmentation still loses money to the plain Bayes threshold")
        print("  at alpha=0.10. Block 4's conclusion is unchanged by re-segmenting.")

    # ---- per-cell detail for the two interesting arms ---------------------------------------
    for kind in ("IDENTITY", "PRODUCT"):
        print(f"\n  {kind} coverage per cell (target {target:.0%}, NaN = below n>={cfg.min_cell_n})")
        for k, v in sorted(out[kind]["coverage"].items()):
            lbl = k.replace("|0", "·legit").replace("|1", "·fraud")
            print(f"    {lbl:<26}{v:>8.3f}" if not np.isnan(v) else f"    {lbl:<26}{'thin':>8}")

    path = cfg.results_dir() / "block5_segments.json"
    path.write_text(json.dumps({"config_hash": cfg.hash(), "exploratory": True,
                                "b1": b1, "arms": out}, indent=2, default=float),
                    encoding="utf-8")
    print(f"\nwritten                {path.relative_to(config.REPO_ROOT)}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
