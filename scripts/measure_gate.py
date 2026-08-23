"""Measure the deployable Gate: economics, per-decision latency, and a real audit record.

    python scripts/measure_gate.py   ->  results/gate_integration.json

Everything the dashboard's integration panel displays comes from here, computed on held-out
data. Nothing is illustrative and nothing is hand-written -- an invented example on a page whose
whole argument is honest measurement would be the worst possible detail to get wrong.

Latency is measured because we criticise the field for not reporting it (arXiv:2607.13078 found
0 of 18 fraud papers report per-decision latency). Criticising a gap we also had would be a
stone thrown from inside.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from dhruva import config, data, features, model, splits
from dhruva.data import AMOUNT, TARGET
from dhruva.gate import REVIEW, Gate

CAPACITY = 0.10
N_TIMED = 20_000


def main() -> int:
    cfg = config.load(); cfg.check_lock()
    df = data.load(cfg.data_dir())
    sp = splits.chronological(df, cfg)
    enc, X = features.build(sp)

    sc = model.fit(X["train"], sp.train[TARGET].to_numpy(), kind="lgbm",
                   cfg=cfg, seed=cfg.base_seed)
    p_cal = sc.predict_proba_fraud(X["cal"])
    p = sc.predict_proba_fraud(X["test"])
    a_cal = sp.cal[AMOUNT].to_numpy(dtype=float)
    amt = sp.test[AMOUNT].to_numpy(dtype=float)
    y = sp.test[TARGET].to_numpy()

    print("=" * 74)
    print("THE DEPLOYABLE GATE")
    print("=" * 74)

    gate = Gate.fit(p_cal, a_cal, capacity=CAPACITY)
    r = gate.evaluate(p, amt, y)
    print(f"\n  fitted on {gate.n_calibration:,} calibration rows (no labels used)")
    print(f"  baseline    Rs{r['baseline']['total']:>12,.0f}   "
          f"recall {r['baseline']['recall']:.1%}  FPR {r['baseline']['fpr']:.2%}")
    print(f"  with gate   Rs{r['gated']['total']:>12,.0f}   "
          f"recall {r['gated']['recall']:.1%}  FPR {r['gated']['fpr']:.2%}")
    print(f"  saved       Rs{r['saved']:>12,.0f}   = {r['saved_share']:.1%}")
    print(f"  escalated   {r['gated']['review_rate']:.1%}   "
          f"(target {CAPACITY:.0%}; the cutoff is a CAL quantile applied to TEST, so it "
          f"drifts a little -- that is real deployment behaviour, not an error)")

    # ---- latency -------------------------------------------------------------------------
    ns = np.empty(N_TIMED)
    for i in range(N_TIMED):
        t0 = time.perf_counter_ns()
        gate.decide(float(p[i]), float(amt[i]))
        ns[i] = time.perf_counter_ns() - t0
    us = ns / 1000.0
    t0 = time.perf_counter()
    gate.decide_batch(p, amt)
    batch_us = (time.perf_counter() - t0) * 1e6 / len(p)

    print(f"\n  latency     p50 {np.percentile(us,50):.2f} us   p99 {np.percentile(us,99):.2f} us"
          f"   batch {batch_us:.3f} us/txn")

    # ---- a REAL audit record, taken from an actually-escalated transaction -----------------
    acts = gate.decide_batch(p, amt)
    idx = int(np.flatnonzero(acts == REVIEW)[0])
    example = gate.explain(float(p[idx]), float(amt[idx]))
    print(f"\n  audit example: TEST row {idx}, actually escalated, label="
          f"{'fraud' if y[idx] else 'legit'}")
    for k, v in example.items():
        print(f"    {k:<24} {v if isinstance(v, str) else round(v, 6)}")

    out = cfg.results_dir() / "gate_integration.json"
    out.write_text(json.dumps({
        "config_hash": cfg.hash(), "data_source": df.attrs["data_source"],
        "capacity": CAPACITY, "cutoff": gate.cutoff, "n_cal": gate.n_calibration,
        "saved": r["saved"], "saved_share": r["saved_share"],
        "baseline": r["baseline"], "gated": r["gated"],
        "p50_us": float(np.percentile(us, 50)), "p99_us": float(np.percentile(us, 99)),
        "batch_us_per_txn": float(batch_us),
        "example": example, "example_row": idx,
        "example_label": "fraud" if y[idx] else "legit",
    }, indent=2, default=float), encoding="utf-8")
    print(f"\nwritten results/{out.name}")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
