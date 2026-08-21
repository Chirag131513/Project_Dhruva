"""Precompute everything the console needs, so the console itself never trains or scores.

    python scripts/export_console.py

Writes results/console_data.json: the alpha sweep for both datasets, per-cell coverage at each
alpha, and a sample of scored TEST decisions. The console is then a lookup table with a slider
on top -- nothing it displays is computed while a judge is watching, and nothing it shows is
live. It is a replay of held-out data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from dhruva import config, conformal, cost, data, features, model, splits
from dhruva.conformal import FRAUD, LEGIT
from dhruva.data import AMOUNT, TARGET

GRID = [0.002, 0.005, 0.01, 0.0208, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30]
SAMPLE = 400


def main() -> int:
    cfg = config.load()
    cfg.check_lock()
    f = cfg.frozen
    cap = float(f["review_cap_headline"])
    a_fraud = float(f["amendment1_alpha_fraud"])
    costs = cost.Costs.from_config(cfg)

    print("exporting console data ...")
    df = data.load(cfg.data_dir())
    sp = splits.chronological(df, cfg)
    enc, X = features.build(sp)
    y_cal, y_test = sp.cal[TARGET].to_numpy(), sp.test[TARGET].to_numpy()
    amt = sp.test[AMOUNT].to_numpy(dtype=float)
    seg_cal = sp.cal["ProductCD"].astype(str).to_numpy()
    seg_test = sp.test["ProductCD"].astype(str).to_numpy()

    sc = model.fit(X["train"], sp.train[TARGET].to_numpy(),
                   kind="lgbm", cfg=cfg, seed=cfg.base_seed)
    p_test = sc.predict_proba_fraud(X["test"])
    s_cal = conformal.nonconformity(sc.predict_proba_fraud(X["cal"]))
    s_test = conformal.nonconformity(p_test)

    b1_acts = cost.decide_bayes(p_test, amt, costs)
    b1 = cost.realised_cost(b1_acts, y_test, amt, costs)

    rng = np.random.default_rng(cfg.base_seed)
    idx = rng.choice(len(y_test), size=min(SAMPLE, len(y_test)), replace=False)
    idx = idx[np.argsort(sp.test["TransactionDT"].to_numpy()[idx])]

    out = {
        "config_hash": cfg.hash(),
        "data_source": df.attrs["data_source"],
        "capacity": cap,
        "alpha_fraud": a_fraud,
        "alpha_derived": cap / float((y_cal == 0).mean()),
        "b1": b1,
        "test_n": int(len(y_test)),
        "test_fraud": int(y_test.sum()),
        "test_volume": float(amt.sum()),
        "grid": [],
        "sample_index": [int(i) for i in idx],
        "sample_amount": [float(a) for a in amt[idx]],
        "sample_segment": [str(s) for s in seg_test[idx]],
        "sample_label": [int(v) for v in y_test[idx]],
        "sample_p": [float(v) for v in p_test[idx]],
        "sample_actions": {},
    }

    for a_l in GRID:
        a = {LEGIT: a_l, FRAUD: a_fraud}
        cal = conformal.calibrate(s_cal, y_cal, seg_cal, a, min_cell_n=cfg.min_cell_n,
                                  class_conditional=True, population_conditional=True)
        sets = conformal.predict_set(s_test, seg_test, cal)
        cov = conformal.coverage(sets, y_test, seg_test, cal)
        acts = cost.decide_conformal(sets, p_test, amt, costs)
        acts, trunc = cost.apply_capacity(acts, p_test, amt, costs, cap)
        c = cost.realised_cost(acts, y_test, amt, costs)

        out["grid"].append({
            "alpha_legit": a_l,
            "cost": c["total"], "net": b1["total"] - c["total"],
            "recall": c["fraud_recall"], "fpr": c["fpr"],
            "review_rate": c["review_rate"], "truncated": trunc,
            "missed_fraud": c["missed_fraud"], "blocked_legit": c["blocked_legit"],
            "review_cost": c["review"],
            "cells": {f"{k[0]}|{k[1]}": (None if np.isnan(v) else float(v))
                      for k, v in cov.items()},
            "cell_n": {f"{k[0]}|{k[1]}": int(cal.n.get(k, 0)) for k in cal.q},
        })
        out["sample_actions"][f"{a_l}"] = [int(v) for v in acts[idx]]
        print(f"  alpha_legit={a_l:<7} cost={c['total']:>12,.0f}  fpr={c['fpr']:.2%}")

    path = cfg.results_dir() / "console_data.json"
    path.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(f"\nwritten {path}  ({path.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
