"""Block 8 -- E7: is the coverage gap a property of the layer, or of LightGBM?

    python scripts/block8_agnostic.py

The single-base-learner threat in RESULTS section 8 is the most substantive gap a reviewer can
name, and the competing 2026 papers all demonstrate model-agnosticism. This runs the same
conformal arms over three very different scorers and asks one question:

    Does marginal conformal under-cover the fraud class regardless of which model produced
    the scores, and does conditioning fix it regardless?

STATUS: post-hoc, exploratory. It changes no pre-registered constant. It can come back
UNFAVOURABLE -- if the gap is small on a weaker scorer, the generality claim weakens and that is
what gets reported. The point of running it is to find out, not to confirm.

A caveat that must travel with the result: logistic regression and random forest cannot accept
NaN, so those arms impute (median) where LightGBM handles missingness natively. Imputation
partially conceals absent-signal structure, so those two arms are not strictly like-for-like.
That is a property of the models, not of the calibration layer, and it is reported not hidden.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from dhruva import config, conformal, cost, data, features, metrics, model, splits
from dhruva.conformal import FRAUD, LEGIT
from dhruva.data import AMOUNT, TARGET

SCORERS = ["lgbm", "logreg", "rf"]


def main() -> int:
    cfg = config.load()
    cfg.check_lock()
    f = cfg.frozen
    alpha = cfg.alpha
    cap = float(f["review_cap_headline"])
    a_fraud = float(f["amendment1_alpha_fraud"])
    costs = cost.Costs.from_config(cfg)

    print("=" * 78)
    print("BLOCK 8  --  E7 model-agnosticism  (POST-HOC)")
    print("=" * 78)

    df = data.load(cfg.data_dir())
    print(f"\nsource                 {df.attrs['data_source']}")
    sp = splits.chronological(df, cfg)
    enc, X = features.build(sp)
    y_train = sp.train[TARGET].to_numpy()
    y_cal, y_test = sp.cal[TARGET].to_numpy(), sp.test[TARGET].to_numpy()
    amt = sp.test[AMOUNT].to_numpy(dtype=float)
    seg_cal = sp.cal["ProductCD"].astype(str).to_numpy()
    seg_test = sp.test["ProductCD"].astype(str).to_numpy()

    p_legit = float((y_cal == 0).mean())
    a_legit = cap / p_legit
    amended = {LEGIT: a_legit, FRAUD: a_fraud}
    print(f"derived alpha_legit    {a_legit:.5f}   (unchanged across scorers by construction)")

    out = {}
    for kind in SCORERS:
        t0 = time.time()
        print(f"\n{'='*78}\nfitting {kind} ...", flush=True)
        try:
            sc = model.fit(X["train"], y_train, kind=kind, cfg=cfg, seed=cfg.base_seed)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            out[kind] = {"failed": f"{type(e).__name__}: {e}"}
            continue

        p_cal = sc.predict_proba_fraud(X["cal"])
        p_test = sc.predict_proba_fraud(X["test"])
        s_cal, s_test = conformal.nonconformity(p_cal), conformal.nonconformity(p_test)
        det = metrics.summarise(y_test, p_test, cap)
        print(f"  fitted in {time.time()-t0:.0f}s   PR-AUC {det['pr_auc']:.4f}   "
              f"ECE {det['ece']:.4f}")

        rec = {"pr_auc": det["pr_auc"], "ece": det["ece"], "roc_auc": det["roc_auc"],
               "fit_seconds": round(time.time() - t0, 1)}

        pool_cal = np.full(len(y_cal), "ALL")
        pool_test = np.full(len(y_test), "ALL")

        cal_m = conformal.calibrate(s_cal, y_cal, pool_cal, alpha, min_cell_n=cfg.min_cell_n,
                                    class_conditional=False, population_conditional=False)
        sets_m = conformal.predict_set(s_test, pool_test, cal_m)
        cov_m = conformal.coverage(sets_m, y_test, pool_test, cal_m)
        rec["marginal"] = float(sets_m[np.arange(y_test.size), y_test].mean())
        rec["b2_legit"] = cov_m[("ALL", LEGIT)]
        rec["b2_fraud"] = cov_m[("ALL", FRAUD)]
        rec["gap"] = rec["marginal"] - rec["b2_fraud"]

        cal_c = conformal.calibrate(s_cal, y_cal, pool_cal, alpha, min_cell_n=cfg.min_cell_n,
                                    class_conditional=True, population_conditional=False)
        cov_c = conformal.coverage(conformal.predict_set(s_test, pool_test, cal_c),
                                   y_test, pool_test, cal_c)
        rec["b3_fraud"] = cov_c[("ALL", FRAUD)]

        b1 = cost.realised_cost(cost.decide_bayes(p_test, amt, costs), y_test, amt, costs)
        cal_a = conformal.calibrate(s_cal, y_cal, seg_cal, amended, min_cell_n=cfg.min_cell_n,
                                    class_conditional=True, population_conditional=True)
        sets_a = conformal.predict_set(s_test, seg_test, cal_a)
        acts = cost.decide_conformal(sets_a, p_test, amt, costs)
        acts, _ = cost.apply_capacity(acts, p_test, amt, costs, cap)
        c = cost.realised_cost(acts, y_test, amt, costs)
        rec.update(b1_cost=b1["total"], amd_cost=c["total"],
                   amd_net=b1["total"] - c["total"],
                   amd_recall=c["fraud_recall"], b1_recall=b1["fraud_recall"],
                   amd_fpr=c["fpr"], b1_fpr=b1["fpr"])

        print(f"  marginal {rec['marginal']:.3f}  ->  fraud {rec['b2_fraud']:.3f}   "
              f"gap {rec['gap']:.3f}")
        print(f"  class-conditional fraud coverage {rec['b3_fraud']:.3f}")
        print(f"  amended arm net vs B1  {rec['amd_net']:+,.0f}")
        out[kind] = rec

    ok = {k: v for k, v in out.items() if "failed" not in v}
    print(f"\n{'='*78}\nSUMMARY   target coverage {1-alpha:.0%}")
    print(f"{'scorer':<9}{'PR-AUC':>9}{'marginal':>10}{'B2 fraud':>10}{'gap':>8}"
          f"{'B3 fraud':>10}{'net vs B1':>12}")
    print("-" * 78)
    for k, v in ok.items():
        print(f"{k:<9}{v['pr_auc']:>9.4f}{v['marginal']:>10.3f}{v['b2_fraud']:>10.3f}"
              f"{v['gap']:>8.3f}{v['b3_fraud']:>10.3f}{v['amd_net']:>+12,.0f}")

    print("\nverdict")
    if len(ok) < 2:
        print("  Too few scorers completed to say anything about agnosticism.")
    else:
        gaps = {k: v["gap"] for k, v in ok.items()}
        fixed = {k: v["b3_fraud"] for k, v in ok.items()}
        print(f"  under-coverage gap ranges {min(gaps.values()):.3f} to {max(gaps.values()):.3f} "
              f"across {len(ok)} scorers")
        if min(gaps.values()) > 0.3:
            print("  The gap is LARGE for every scorer. Marginal conformal under-covers the fraud")
            print("  class regardless of which model produced the scores -- a property of the")
            print("  calibration procedure under imbalance, not of LightGBM.")
        elif max(gaps.values()) - min(gaps.values()) > 0.3:
            print("  The gap varies WIDELY across scorers. It is not purely a property of the")
            print("  calibration procedure; the base model's error profile matters materially.")
            print("  The generality claim in RESULTS section 8 must be weakened accordingly.")
        else:
            print("  The gap is modest for every scorer. Report the range, not the LightGBM")
            print("  figure alone.")

        if min(fixed.values()) > 1 - alpha - 0.05:
            print("  Class-conditional calibration restores fraud coverage to within 5 points of")
            print(f"  target on ALL scorers ({min(fixed.values()):.3f}-{max(fixed.values()):.3f}). "
                  "The fix is model-agnostic.")
        else:
            print(f"  The fix does NOT restore coverage uniformly "
                  f"({min(fixed.values()):.3f}-{max(fixed.values()):.3f}). Report per scorer.")

        signs = {np.sign(v["amd_net"]) for v in ok.values()}
        if len(signs) > 1:
            print("  ECONOMICS DO NOT TRANSFER: the sign of the amended arm's net benefit differs")
            print("  across base models. The cost conclusion is LightGBM-specific and must say so.")
        else:
            print("  The sign of the amended arm's net benefit is the same on every scorer.")

    print("\n  CAVEAT: logreg and rf impute missing values (median); lgbm handles NaN natively.")
    print("  Those arms are not strictly like-for-like, and that is a property of the models.")

    path = cfg.results_dir() / "block8_agnostic.json"
    path.write_text(json.dumps({"config_hash": cfg.hash(), "post_hoc": True,
                                "alpha": alpha, "alpha_legit_derived": a_legit,
                                "scorers": out}, indent=2, default=float), encoding="utf-8")
    print(f"\nwritten                results/{path.name}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
