"""Block 7 -- alpha_legit sweep, on IEEE-CIS and ULB.

    python scripts/block7_alpha_sweep.py

Closes the two real gaps left after Amendment 1:

  1. EXTERNAL VALIDATION. Everything so far rests on one dataset. ULB (Worldline/ULB, 284,807
     transactions, 0.172% fraud) is an independent source with a 20x harsher imbalance. It has
     no ProductCD, so the segment is amount quartile -- also a real, merchant-visible field, and
     the substitution is stated rather than hidden.

  2. THE CURVE. Amendment 1 derived alpha_legit = review_cap / P(legit) and evaluated it at one
     point. Sweeping alpha_legit turns a derivation plus an anecdote into a shape, and answers
     the question a reviewer will actually ask: was the derived value anywhere near optimal, or
     did it just happen to land somewhere tolerable?

alpha_fraud is held at the pre-registered 0.10 throughout. Only the legitimate-class budget moves.

STATUS: post-hoc, exploratory. The sweep is a diagnostic, NOT a procedure for picking alpha on
test data -- reading the argmin off this curve and reporting it as "my method" would be fitting
a hyperparameter to the test set. The capacity-derived value is the one the method uses; the
sweep exists to show where it sits relative to the optimum.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from dhruva import config, conformal, cost, data, features, model, splits
from dhruva.conformal import FRAUD, LEGIT
from dhruva.data import AMOUNT, TARGET

ALPHA_GRID = [0.002, 0.005, 0.01, 0.0208, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30]


def amount_quartile(train_amt: np.ndarray, amt: np.ndarray) -> np.ndarray:
    """Segment by amount quartile, with edges fitted on TRAIN only."""
    edges = np.quantile(train_amt, [0.25, 0.5, 0.75])
    return np.array([f"Q{i}" for i in np.digitize(amt, edges)])


def prepare(cfg, which: str):
    if which == "ieee-cis":
        df = data.load(cfg.data_dir())
        seg = lambda d, _t: d["ProductCD"].astype(str).to_numpy()
        seg_name = "ProductCD"
    else:
        df = data.load_ulb(cfg.data_dir())
        seg = lambda d, t: amount_quartile(t, d[AMOUNT].to_numpy(dtype=float))
        seg_name = "amount quartile"

    sp = splits.chronological(df, cfg)
    enc, X = features.build(sp)
    y_cal, y_test = sp.cal[TARGET].to_numpy(), sp.test[TARGET].to_numpy()
    amt = sp.test[AMOUNT].to_numpy(dtype=float)
    train_amt = sp.train[AMOUNT].to_numpy(dtype=float)

    sc = model.fit(X["train"], sp.train[TARGET].to_numpy(),
                   kind="lgbm", cfg=cfg, seed=cfg.base_seed)
    return {
        "name": which, "seg_name": seg_name,
        "s_cal": conformal.nonconformity(sc.predict_proba_fraud(X["cal"])),
        "s_test": conformal.nonconformity(sc.predict_proba_fraud(X["test"])),
        "p_test": sc.predict_proba_fraud(X["test"]),
        "y_cal": y_cal, "y_test": y_test, "amt": amt,
        "seg_cal": seg(sp.cal, train_amt), "seg_test": seg(sp.test, train_amt),
    }


def main() -> int:
    cfg = config.load()
    cfg.check_lock()
    f = cfg.frozen
    cap = float(f["review_cap_headline"])
    a_fraud = float(f["amendment1_alpha_fraud"])
    costs = cost.Costs.from_config(cfg)

    print("=" * 78)
    print("BLOCK 7  --  alpha_legit sweep + ULB external validation  (POST-HOC)")
    print("=" * 78)

    results = {}
    for which in ("ieee-cis", "ulb-creditcard"):
        try:
            D = prepare(cfg, which)
        except Exception as e:
            print(f"\n{which}: unavailable ({type(e).__name__}: {e})")
            continue

        p_legit = float((D["y_cal"] == 0).mean())
        a_derived = cap / p_legit
        b1 = cost.realised_cost(cost.decide_bayes(D["p_test"], D["amt"], costs),
                                D["y_test"], D["amt"], costs)

        print(f"\n{'='*78}\n{which}   segment: {D['seg_name']}")
        print(f"  TEST {len(D['y_test']):,} rows, fraud {D['y_test'].mean():.3%}, "
              f"P(legit) on CAL {p_legit:.4f}")
        print(f"  capacity-derived alpha_legit = {cap:.2f}/{p_legit:.4f} = {a_derived:.4f}")
        print(f"  B1 baseline Rs{b1['total']:,.0f}   recall {b1['fraud_recall']:.1%}   "
              f"FPR {b1['fpr']:.2%}")
        print(f"\n{'a_legit':>9}{'cost Rs':>13}{'vs B1':>12}{'recall':>9}{'FPR':>8}"
              f"{'review':>9}{'legit cov':>11}{'fraud cov':>11}")
        print("-" * 78)

        rows = []
        for a_l in ALPHA_GRID:
            a = {LEGIT: a_l, FRAUD: a_fraud}
            cal = conformal.calibrate(D["s_cal"], D["y_cal"], D["seg_cal"], a,
                                      min_cell_n=cfg.min_cell_n,
                                      class_conditional=True, population_conditional=True)
            sets = conformal.predict_set(D["s_test"], D["seg_test"], cal)
            cov = conformal.coverage(sets, D["y_test"], D["seg_test"], cal)
            cl = [v for k, v in cov.items() if k[1] == LEGIT and not np.isnan(v)]
            cf = [v for k, v in cov.items() if k[1] == FRAUD and not np.isnan(v)]

            acts = cost.decide_conformal(sets, D["p_test"], D["amt"], costs)
            acts, _ = cost.apply_capacity(acts, D["p_test"], D["amt"], costs, cap)
            c = cost.realised_cost(acts, D["y_test"], D["amt"], costs)

            mark = "  <-- derived" if abs(a_l - a_derived) < 0.002 else ""
            rows.append({"alpha_legit": a_l, "cost": c["total"],
                         "net": b1["total"] - c["total"], "recall": c["fraud_recall"],
                         "fpr": c["fpr"], "review": c["review_rate"],
                         "legit_cov": float(np.mean(cl)) if cl else float("nan"),
                         "fraud_cov": float(np.mean(cf)) if cf else float("nan")})
            r = rows[-1]
            print(f"{a_l:>9.4f}{r['cost']:>13,.0f}{r['net']:>+12,.0f}{r['recall']:>9.1%}"
                  f"{r['fpr']:>8.2%}{r['review']:>9.1%}{r['legit_cov']:>11.3f}"
                  f"{r['fraud_cov']:>11.3f}{mark}")

        best = min(rows, key=lambda r: r["cost"])
        nearest = min(rows, key=lambda r: abs(r["alpha_legit"] - a_derived))
        gap = nearest["cost"] - best["cost"]
        print(f"\n  cost-minimising alpha_legit  {best['alpha_legit']:.4f}  "
              f"(Rs{best['cost']:,.0f}, net {best['net']:+,.0f})")
        print(f"  capacity-derived             {nearest['alpha_legit']:.4f}  "
              f"(Rs{nearest['cost']:,.0f}, net {nearest['net']:+,.0f})")
        print(f"  cost of using the derived value instead of the optimum: Rs{gap:,.0f} "
              f"({gap / max(b1['total'],1):.2%} of baseline)")

        results[which] = {"p_legit": p_legit, "alpha_derived": a_derived,
                          "b1": b1["total"], "rows": rows,
                          "best_alpha": best["alpha_legit"], "seg": D["seg_name"]}

    if len(results) == 2:
        a, b = results["ieee-cis"], results["ulb-creditcard"]
        print(f"\n{'='*78}\nEXTERNAL VALIDATION")
        print(f"  cost-minimising alpha_legit:  IEEE-CIS {a['best_alpha']:.4f}   "
              f"ULB {b['best_alpha']:.4f}")

        # Replication means the METHOD transfers, not that two argmins are numerically close.
        # A tolerance on the argmin alone would call agreement even when every configuration
        # on one dataset loses to its own baseline -- which is the opposite of replication.
        # The first version of this check did exactly that, so the test is now: does the method
        # beat its baseline anywhere on this dataset at all?
        for name, r in (("IEEE-CIS", a), ("ULB", b)):
            best_net = max(q["net"] for q in r["rows"])
            usable = [q for q in r["rows"] if not np.isnan(q["fraud_cov"])]
            print(f"    {name:<9} best net vs baseline {best_net:>+12,.0f}   "
                  f"fraud cells reportable at {len(usable)}/{len(r['rows'])} alphas")

        a_wins = max(q["net"] for q in a["rows"]) > 0
        b_wins = max(q["net"] for q in b["rows"]) > 0
        if a_wins and b_wins:
            print("\n  The method beats its baseline on BOTH datasets. That is replication.")
        elif a_wins and not b_wins:
            print("\n  REPLICATION FAILED. The method beats its baseline on IEEE-CIS and loses")
            print("  at EVERY alpha on ULB. This is not a tuning problem: at 0.126% fraud the")
            print("  calibration split holds too few fraud rows to estimate a fraud quantile,")
            print("  so the stop rule voids every fraud cell and the method runs on one class.")
            print("  The honest conclusion is a BOUNDARY on applicability -- the approach needs")
            print("  enough minority calibration data, and below some prevalence it has none.")
            print("  Report ULB as a negative external validation, not as an inconvenience.")
        else:
            print("\n  The method does not beat its baseline on IEEE-CIS. Report that first.")

    _plot(cfg, results, cap)
    out = cfg.results_dir() / "block7_alpha_sweep.json"
    out.write_text(json.dumps({"config_hash": cfg.hash(), "post_hoc": True,
                               "alpha_fraud": a_fraud, "results": results},
                              indent=2, default=float), encoding="utf-8")
    print(f"\nwritten                {out.relative_to(config.REPO_ROOT)}")
    print("=" * 78)
    return 0


def _plot(cfg, results, cap):
    if not results:
        return
    fig_dir = cfg.results_dir() / "figures"
    fig_dir.mkdir(exist_ok=True)
    n = len(results)
    fig, axes = plt.subplots(1, n, figsize=(6.2 * n, 4.4), squeeze=False)

    for ax, (name, r) in zip(axes[0], results.items()):
        xs = [q["alpha_legit"] for q in r["rows"]]
        ax.plot(xs, [q["cost"] for q in r["rows"]], "o-", label="conformal + review")
        ax.axhline(r["b1"], ls="--", c="k", lw=1, label="B1 Bayes threshold")
        ax.axvline(r["alpha_derived"], ls=":", c="crimson", lw=1.5,
                   label=f"capacity-derived α={r['alpha_derived']:.3f}")
        ax.set_xscale("log")
        ax.set_xlabel("α_legit  (miscoverage budget on legitimate traffic)")
        ax.set_ylabel("realised cost (₹)")
        ax.set_title(f"{name} — segment: {r['seg']}", fontsize=10)
        ax.legend(fontsize=8); ax.grid(alpha=.3)

    fig.suptitle("Cost against the legitimate-class miscoverage budget "
                 f"(α_fraud fixed at 0.10, review capacity {cap:.0%})", fontsize=10)
    fig.tight_layout(); fig.savefig(fig_dir / "graph4_alpha_sweep.png", dpi=150); plt.close(fig)
    print("\nfigure                 figures/graph4_alpha_sweep.png")


if __name__ == "__main__":
    raise SystemExit(main())
