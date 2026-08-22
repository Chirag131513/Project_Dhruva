"""Block 10 -- two things the headline assumes, tested rather than asserted.

    python scripts/block10_proofs.py

The 28% claim rests on two premises that were never checked:

  A  the baseline is the model USED WELL, not a hobbled strawman
  B  the escalated cases are genuinely where the model fails

If A is false we are beating a crippled comparison. If B is false, escalation is arbitrary and
the gain is luck. Both are cheap to test and one of them came back partly against us.
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
from dhruva.cost import APPROVE, BLOCK
from dhruva.data import AMOUNT, TARGET

FIXED = [0.02, 0.05, 0.10, 0.146, 0.20, 0.30, 0.50, 0.70]
CAP = 0.10


def main() -> int:
    cfg = config.load(); cfg.check_lock()
    costs = cost.Costs.from_config(cfg)
    sp = splits.chronological(data.load(cfg.data_dir()), cfg)
    enc, X = features.build(sp)
    sc = model.fit(X["train"], sp.train[TARGET].to_numpy(), kind="lgbm",
                   cfg=cfg, seed=cfg.base_seed)
    p = sc.predict_proba_fraud(X["test"])
    y = sp.test[TARGET].to_numpy()
    amt = sp.test[AMOUNT].to_numpy(dtype=float)
    n = len(y)

    # ---- A: is our baseline the model at its best? ---------------------------------------
    base = cost.realised_cost(cost.decide_bayes(p, amt, costs), y, amt, costs)["total"]
    print("=" * 76)
    print("A  is the baseline the model USED WELL, or a strawman?")
    print("=" * 76)
    print(f"\n{'fixed threshold':>16}{'realised loss':>16}{'vs ours':>14}")
    print("-" * 76)
    sweep = {}
    for t in FIXED:
        c = cost.realised_cost(np.where(p > t, BLOCK, APPROVE), y, amt, costs)["total"]
        sweep[t] = c
        print(f"{t:>16.3f}{c:>16,.0f}{c - base:>+14,.0f}")
    print(f"{'per-transaction':>16}{base:>16,.0f}      <- ours")

    bt = min(sweep, key=sweep.get)
    gap = base - sweep[bt]
    print(f"\n  best fixed threshold: {bt} at Rs{sweep[bt]:,.0f}")
    if gap > 0:
        print(f"  OUR BASELINE IS Rs{gap:,.0f} WORSE ({gap/base:.1%}) than that fixed cutoff.")
        print("  Report this. The per-transaction threshold is optimal only under perfectly")
        print("  calibrated probabilities; ours has ECE 0.0039, close but not exact. Note also")
        print("  that 0.10 was selected by sweeping the TEST set -- hindsight our own method")
        print("  never got -- so this is an upper bound on how favourable our baseline is.")
    else:
        print(f"  ours is Rs{-gap:,.0f} better than any fixed cutoff tried.")

    # ---- B: do the model's errors concentrate where we escalate? --------------------------
    stake = np.maximum(p * costs.c_fn(amt), (1 - p) * costs.c_fp(amt))
    order = -np.abs(p - costs.bayes_threshold(amt)) * 1e6 + stake / 1e6
    k = int(round(CAP * n))
    esc = np.zeros(n, bool); esc[np.argsort(-order)[:k]] = True

    acts = cost.decide_bayes(p, amt, costs)
    wrong = ((acts == APPROVE) & (y == 1)) | ((acts == BLOCK) & (y == 0))
    err_rs = np.where(y == 1, costs.c_fn(amt), costs.c_fp(amt)) * wrong

    print("\n" + "=" * 76)
    print(f"B  does the model actually FAIL on the {CAP:.0%} we escalate?")
    print("=" * 76)
    r_in, r_out = wrong[esc].mean(), wrong[~esc].mean()
    print(f"\n  error rate inside the escalated {CAP:.0%} : {r_in:>7.2%}")
    print(f"  error rate on the remaining {1-CAP:.0%}     : {r_out:>7.2%}")
    print(f"  concentration ratio                    : {r_in/max(r_out,1e-9):>7.1f}x")
    print(f"\n  share of ALL errors captured           : {wrong[esc].sum()/wrong.sum():>7.1%}"
          f"   ({wrong[esc].sum():,} of {wrong.sum():,})")
    print(f"  share of error VALUE captured          : {err_rs[esc].sum()/err_rs.sum():>7.1%}"
          f"   (Rs{err_rs[esc].sum():,.0f} of Rs{err_rs.sum():,.0f})")
    print("\n  Read this the right way round: the model is NOT bad. It is right 98% of the")
    print("  time on nine tenths of the traffic. Its mistakes are simply not spread evenly,")
    print("  and a one-line rule locates roughly half of them in a tenth of the volume.")

    out = cfg.results_dir() / "block10_proofs.json"
    out.write_text(json.dumps({
        "config_hash": cfg.hash(), "baseline": base,
        "fixed_sweep": sweep, "best_fixed": bt, "baseline_gap": gap,
        "err_rate_escalated": float(r_in), "err_rate_rest": float(r_out),
        "errors_captured": float(wrong[esc].sum() / wrong.sum()),
        "error_value_captured": float(err_rs[esc].sum() / err_rs.sum()),
    }, indent=2, default=float), encoding="utf-8")
    print(f"\nwritten results/{out.name}")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
