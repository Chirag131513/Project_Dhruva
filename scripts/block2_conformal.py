"""Block 2 -- conformal calibration on the real pipeline.

    python scripts/block2_conformal.py [--dev] [--ulb]

Reproduces, on payment data rather than a synthetic toy, the failure the whole project turns on:

    B2  marginal split conformal   -> hits its target overall, misses the fraud class
    B3  class-conditional Mondrian -> restores it

If B2 does NOT under-cover here, that is worth knowing immediately: it would mean the base
scorer is not differentially worse on fraud, and the mechanism has less room than assumed.

--ulb runs against the ULB creditcard dataset (0.172% fraud) as an extreme-imbalance stress test.
tau cannot be applied there -- its features are PCA-anonymised, so no device block exists to
ablate -- so this is machinery validation only. No H1/H3 result may come from it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from dhruva import config, conformal, data, features, model, splits
from dhruva.conformal import FRAUD, LEGIT
from dhruva.data import TARGET


ARMS = [
    ("B2  marginal", False, False),
    ("B3  class-conditional", True, False),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--ulb", action="store_true", help="ULB stress test (machinery only)")
    ap.add_argument("--kind", default="lgbm", choices=["lgbm", "logreg", "rf"])
    args = ap.parse_args()

    cfg = config.load()
    cfg.check_lock()
    alpha, target = cfg.alpha, 1.0 - cfg.alpha

    print("=" * 78)
    print("BLOCK 2  --  conformal calibration")
    print("=" * 78)

    if args.ulb:
        df = data.load_ulb(cfg.data_dir())
    else:
        df = data.load(cfg.data_dir(), dev=args.dev, seed=cfg.base_seed)
    source = df.attrs["data_source"]
    print(f"\nsource                 {source}")
    if source != "ieee-cis":
        print("  [not reportable -- IEEE-CIS is the only source for a headline result]")

    sp = splits.chronological(df, cfg)
    print(f"\nsplit"); print(sp)

    enc, X = features.build(sp)
    y_cal, y_test = sp.cal[TARGET].to_numpy(), sp.test[TARGET].to_numpy()

    print(f"\nfitting {args.kind} ...")
    scorer = model.fit(X["train"], sp.train[TARGET].to_numpy(),
                       kind=args.kind, cfg=cfg, seed=cfg.base_seed)
    s_cal = conformal.nonconformity(scorer.predict_proba_fraud(X["cal"]))
    s_test = conformal.nonconformity(scorer.predict_proba_fraud(X["test"]))

    pop_cal = np.full(len(y_cal), "ALL")
    pop_test = np.full(len(y_test), "ALL")

    print(f"\ncoverage at target {target:.0%}   (NaN = cell below the n>={cfg.min_cell_n} "
          f"stop rule)")
    print(f"{'arm':<26}{'marginal':>11}{'legit':>10}{'fraud':>10}{'|C|=1':>9}{'review':>9}")
    print("-" * 78)

    records = []
    for name, cc, pc in ARMS:
        cal = conformal.calibrate(s_cal, y_cal, pop_cal, alpha,
                                  min_cell_n=cfg.min_cell_n,
                                  class_conditional=cc, population_conditional=pc)
        sets = conformal.predict_set(s_test, pop_test, cal)
        cov = conformal.coverage(sets, y_test, pop_test, cal)

        marg = float(sets[np.arange(y_test.size), y_test].mean())
        singleton = float((sets.sum(axis=1) == 1).mean())
        review = 1.0 - singleton

        cl, cf = cov[("ALL", LEGIT)], cov[("ALL", FRAUD)]
        print(f"{name:<26}{marg:>11.3f}{cl:>10.3f}{cf:>10.3f}"
              f"{singleton:>9.1%}{review:>9.1%}")

        records.append({"arm": name.split()[0], "marginal": marg,
                        "legit": cl, "fraud": cf,
                        "singleton_rate": singleton, "review_rate": review,
                        "cells": {f"{k[0]}|{k[1]}": {"n": cal.n[k], "q": cal.q[k]}
                                  for k in cal.q},
                        "thin_cells": [f"{c[0]}|{c[1]}" for c in cal.thin_cells()]})

    # ---- verdict ---------------------------------------------------------------------------
    b2, b3 = records[0], records[1]
    print("\nverdict")
    gap = target - b2["fraud"]
    if np.isnan(b2["fraud"]):
        print("  B2's fraud cell is below the stop rule -- coverage not reportable there.")
    elif gap > 0.05:
        print(f"  B2 under-covers the fraud class by {gap:.1%} while its marginal coverage reads "
              f"{b2['marginal']:.3f}.")
        print("  A dashboard showing only marginal coverage would report this system as healthy.")
        if not np.isnan(b3["fraud"]):
            print(f"  B3 restores fraud coverage to {b3['fraud']:.3f}.")
    else:
        print(f"  B2 did NOT materially under-cover fraud (gap {gap:+.1%}).")
        print("  Worth understanding before Block 3: the scorer may not be differentially worse")
        print("  on fraud in this data, which leaves the mechanism less room than assumed.")
        print("  Report this rather than tuning until the expected pattern appears.")

    print(f"\n  review rate is the cost of the promise: B2 {b2['review_rate']:.1%} -> "
          f"B3 {b3['review_rate']:.1%} of volume escalated.")

    out = cfg.results_dir() / f"block2_{'ulb' if args.ulb else source}.json"
    out.write_text(json.dumps(
        {"config_hash": cfg.hash(), "data_source": source, "scorer": args.kind,
         "alpha": alpha, "arms": records}, indent=2, default=float), encoding="utf-8")
    print(f"\nwritten                {out.relative_to(config.REPO_ROOT)}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
