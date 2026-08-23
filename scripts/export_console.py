"""Export console data for the dashboard.

    python scripts/export_console.py

Precomputes the queue-policy comparison so the dashboard is a lookup table with a capacity
slider on top -- nothing is computed while a judge is watching, and nothing is live.

The exported shape follows what Block 12 measured, because that is the headline: net benefit
per (policy, capacity), the blindness map, and a decision sample. Block 9's kill test rides
along under `kill_test` as provenance -- the dashboard does not render it, but the evidence
that conformal lost should travel with the demo rather than being a separate errand.

SEED COUNTS ARE NOT INTERCHANGEABLE HERE. Block 12 ran 5 seeds and Block 9 ran 10, and both
recompute their own baseline because the model is refit per seed. Every seed-dependent figure
is therefore namespaced to the experiment that produced it: `policy_seeds` at top level for
what is on screen, `kill_test.seeds` for Block 9. Do not add a bare `seeds` key back.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from dhruva import config, cost, data, features, model, splits
from dhruva.cost import REVIEW
from dhruva.data import AMOUNT, TARGET

SAMPLE = 400


def main() -> int:
    cfg = config.load(); cfg.check_lock()
    costs = cost.Costs.from_config(cfg)
    b9 = json.loads((cfg.results_dir() / "block9_triage.json").read_text(encoding="utf-8"))
    b12p = cfg.results_dir() / "block12_policies.json"
    if not b12p.exists():
        print("results/block12_policies.json missing — run scripts/block12_policies.py first")
        raise SystemExit(1)
    b12 = json.loads(b12p.read_text(encoding="utf-8"))

    df = data.load(cfg.data_dir())
    sp = splits.chronological(df, cfg)
    enc, X = features.build(sp)
    y = sp.test[TARGET].to_numpy()
    amt = sp.test[AMOUNT].to_numpy(dtype=float)
    n = len(y)

    sc = model.fit(X["train"], sp.train[TARGET].to_numpy(), kind="lgbm",
                   cfg=cfg, seed=cfg.base_seed)
    p = sc.predict_proba_fraud(X["test"])
    b1 = cost.realised_cost(cost.decide_bayes(p, amt, costs), y, amt, costs)

    stake = np.maximum(p * costs.c_fn(amt), (1 - p) * costs.c_fp(amt))
    order = -np.abs(p - costs.bayes_threshold(amt)) * 1e6 + stake / 1e6

    rng = np.random.default_rng(cfg.base_seed)
    idx = rng.choice(n, size=min(SAMPLE, n), replace=False)
    idx = idx[np.argsort(sp.test["TransactionDT"].to_numpy()[idx])]

    out = {
        "config_hash": cfg.hash(), "data_source": df.attrs["data_source"],
        "test_n": int(n), "test_fraud": int(y.sum()), "test_volume": float(amt.sum()),
        "b1": b1,
        "caps": b12["caps"],
        # Block 12 -- what the dashboard actually renders. ONE seed count at top level.
        "policy_seeds": b12["seeds"],
        "policies": b12["policies"], "advantage": b12["advantage"],
        "blind": b12["blind"], "total_error_cost": b12["total_error_cost"],
        # Block 9's kill test, namespaced. It used to travel here under bare names --
        # `seeds` (10) sat directly beside `policy_seeds` (5) with nothing on either to
        # say which experiment it described, and `b1_mean` (10-seed) beside `b1` (single
        # seed). Nothing read the bare keys; they were only ever a trap for whoever
        # touched this next. Namespacing makes picking the wrong one impossible.
        "kill_test": {
            "seeds": b9["seeds"], "b1_mean": b9["b1_mean"],
            "net": b9["net"], "kill": b9["kill"], "k3": b9["k3_detail"],
        },
        "sample_amount": [float(a) for a in amt[idx]],
        "sample_segment": [str(s) for s in sp.test["ProductCD"].astype(str).to_numpy()[idx]],
        "sample_label": [int(v) for v in y[idx]],
        "sample_p": [float(v) for v in p[idx]],
        "grid": [],
    }

    for c in b12["caps"]:
        k = int(round(c * n))
        acts = cost.decide_bayes(p, amt, costs)
        if k:
            acts[np.argsort(-order)[:k]] = REVIEW
        r = cost.realised_cost(acts, y, amt, costs)
        out["grid"].append({
            "cap": c, "cost": r["total"], "net": b1["total"] - r["total"],
            "recall": r["fraud_recall"], "fpr": r["fpr"],
            "review_rate": r["review_rate"],
            "missed_fraud": r["missed_fraud"], "blocked_legit": r["blocked_legit"],
            "review_cost": r["review"],
            "net_by_policy": {k: float(np.mean(v[str(c)])) for k, v in b12["policies"].items()},
        })
        out.setdefault("sample_actions", {})[str(c)] = [int(v) for v in acts[idx]]
        print(f"  cap {c:.0%}  cost {r['total']:>12,.0f}  net {b1['total']-r['total']:>+12,.0f}"
              f"  fpr {r['fpr']:.2%}")

    path = cfg.results_dir() / "console_data.json"
    path.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(f"\nwritten results/{path.name}  ({path.stat().st_size/1e3:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
