"""Block 6 -- Amendment 1: capacity-derived per-class alpha.

    python scripts/block6_amendment.py

STATUS: post-hoc. Added after Block 4 refuted H4. The pre-registered alpha = 0.10 result is NOT
replaced -- it is reported in the same table, every time. See config.yaml `amendments[0]`, which
also records the prediction made BEFORE this was run.

THE DERIVATION

Miscovering a legitimate row pushes it toward block-or-review. So the miscoverage budget on the
majority class is not a free parameter -- it is bounded by the review capacity that can actually
be staffed:

    alpha_legit = review_cap / P(legit)

alpha_fraud stays at the pre-registered 0.10: the fraud-side promise is the one we wanted, and
nothing observed justifies loosening it.

The direction is counter-intuitive and worth saying out loud. Fraud is the expensive error per
case. But legitimate traffic is ~28x more common, so in AGGREGATE the miscoverage budget belongs
mostly to the fraud class -- the opposite of what "be strict about fraud" suggests.

Segmentation is ProductCD, following Block 5: identity-presence was a proxy for it, and a worse
one when scored on a neutral grid.
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


def main() -> int:
    cfg = config.load()
    cfg.check_lock()
    f = cfg.frozen
    cap = float(f["review_cap_headline"])
    target_band = float(f["target_coverage_band"])

    print("=" * 78)
    print("BLOCK 6  --  Amendment 1: capacity-derived per-class alpha  (POST-HOC)")
    print("=" * 78)

    df = data.load(cfg.data_dir())
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

    seg_cal = sp.cal["ProductCD"].astype(str).to_numpy()
    seg_test = sp.test["ProductCD"].astype(str).to_numpy()

    # ---- the derivation, computed on CAL only ----------------------------------------------
    p_legit = float((y_cal == 0).mean())
    alpha_legit = cap / p_legit
    alpha_fraud = float(f["amendment1_alpha_fraud"])
    amended = {LEGIT: alpha_legit, FRAUD: alpha_fraud}

    print(f"\nderivation             P(legit) on CAL = {p_legit:.4f}, review capacity = {cap:.0%}")
    print(f"  alpha_legit          = {cap:.2f} / {p_legit:.4f} = {alpha_legit:.4f}"
          f"   -> {1 - alpha_legit:.2%} coverage promised on legitimate traffic")
    print(f"  alpha_fraud          = {alpha_fraud:.2f} (pre-registered, unchanged)"
          f"   -> {1 - alpha_fraud:.0%} on fraud")
    print("  Neither number was chosen by looking at a result.")

    b1 = cost.realised_cost(cost.decide_bayes(p_test, amt, costs), y_test, amt, costs)

    arms = {
        "B1 bayes": None,
        "PRE alpha=0.10": float(f["alpha"]),
        "AMD per-class": amended,
    }

    print(f"\n{'arm':<17}{'cost Rs':>12}{'vs B1':>12}{'recall':>9}{'FPR':>8}"
          f"{'review':>9}{'legit cov':>11}{'fraud cov':>11}")
    print("-" * 78)

    out = {}
    for name, a in arms.items():
        if a is None:
            acts = cost.decide_bayes(p_test, amt, costs)
            c = cost.realised_cost(acts, y_test, amt, costs)
            cov_l = cov_f = float("nan")
        else:
            cal = conformal.calibrate(s_cal, y_cal, seg_cal, a, min_cell_n=cfg.min_cell_n,
                                      class_conditional=True, population_conditional=True)
            sets = conformal.predict_set(s_test, seg_test, cal)
            cov = conformal.coverage(sets, y_test, seg_test, cal)
            vals_l = [v for k, v in cov.items() if k[1] == LEGIT and not np.isnan(v)]
            vals_f = [v for k, v in cov.items() if k[1] == FRAUD and not np.isnan(v)]
            cov_l = float(np.mean(vals_l)) if vals_l else float("nan")
            cov_f = float(np.mean(vals_f)) if vals_f else float("nan")
            acts = cost.decide_conformal(sets, p_test, amt, costs)
            acts, _ = cost.apply_capacity(acts, p_test, amt, costs, cap)
            c = cost.realised_cost(acts, y_test, amt, costs)

        delta = b1["total"] - c["total"]
        mark = "baseline" if a is None else f"{delta:+,.0f}"
        print(f"{name:<17}{c['total']:>12,.0f}{mark:>12}{c['fraud_recall']:>9.1%}"
              f"{c['fpr']:>8.2%}{c['review_rate']:>9.1%}{cov_l:>11.3f}{cov_f:>11.3f}")
        out[name] = c | {"legit_coverage": cov_l, "fraud_coverage": cov_f,
                         "net_vs_b1": delta}

    # ---- verdict ---------------------------------------------------------------------------
    pre, amd = out["PRE alpha=0.10"], out["AMD per-class"]
    print("\nverdict")
    print(f"  pre-registered arm   Rs{pre['total']:,.0f}  ({pre['net_vs_b1']:+,.0f} vs B1)")
    print(f"  amended arm          Rs{amd['total']:,.0f}  ({amd['net_vs_b1']:+,.0f} vs B1)")
    print(f"  amendment moved cost by Rs{pre['total'] - amd['total']:+,.0f}")

    if amd["net_vs_b1"] > 0:
        print("\n  The amended arm BEATS the plain Bayes baseline. The prediction recorded in")
        print("  config.yaml before this ran is confirmed: the pre-registered failure was")
        print("  about the symmetric alpha, not about conformal abstention as such.")
        print(f"  Fraud coverage held at {amd['fraud_coverage']:.3f} while FPR fell from "
              f"{pre['fpr']:.2%} to {amd['fpr']:.2%}.")
    else:
        print("\n  The amended arm STILL loses to the plain Bayes baseline. The prediction")
        print("  recorded before running is refuted, and the stronger conclusion follows:")
        print("  conformal abstention is the wrong tool for this problem at any alpha, not")
        print("  merely at 0.10. Report it that way.")

    lost = pre["fraud_coverage"] - amd["fraud_coverage"]
    if not np.isnan(lost) and abs(lost) > target_band:
        print(f"\n  NOTE: fraud coverage moved {lost:+.3f} between arms. The amendment is not")
        print("  free -- state what the tighter legit budget cost on the fraud side.")

    path = cfg.results_dir() / "block6_amendment1.json"
    path.write_text(json.dumps({"config_hash": cfg.hash(), "post_hoc": True,
                                "alpha_legit": alpha_legit, "alpha_fraud": alpha_fraud,
                                "p_legit_cal": p_legit, "arms": out},
                               indent=2, default=float), encoding="utf-8")
    print(f"\nwritten                {path.relative_to(config.REPO_ROOT)}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
