"""Block 4 -- the rupee cost model. Produces Graph 3.

    python scripts/block4_cost.py [--dev]

Turns coverage into money. Four arms, priced on the same held-out TEST period:

    B1  cost-optimal two-way Bayes threshold (per-transaction)   -- the real baseline
    B2  marginal conformal      + capacity-constrained review
    B3  class-conditional       + capacity-constrained review
    D1  population x class      + capacity-constrained review

Everything runs on the NATURAL population split with tau switched off, because that is where
Block 3 found the result. No modelling assumption enters this table.

The decomposition is the point. A method that only reduces missed fraud is not answering the
question Razorpay's own engineering writing asks -- they name false positives as a trust problem.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from dhruva import config, conformal, cost, data, features, model, shift, splits
from dhruva.data import AMOUNT, TARGET

ARMS = {"B2": (False, False), "B3": (True, False), "D1": (True, True)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    args = ap.parse_args()

    cfg = config.load()
    cfg.check_lock()
    alpha = cfg.alpha
    f = cfg.frozen

    print("=" * 78)
    print("BLOCK 4  --  cost model  (Graph 3)")
    print("=" * 78)

    df = data.load(cfg.data_dir(), dev=args.dev, seed=cfg.base_seed)
    source = df.attrs["data_source"]
    print(f"\nsource                 {source}")
    if source != "ieee-cis":
        print("  [not reportable]")

    sp = splits.chronological(df, cfg)
    enc, X = features.build(sp)
    y_cal, y_test = sp.cal[TARGET].to_numpy(), sp.test[TARGET].to_numpy()
    amt_test = sp.test[AMOUNT].to_numpy(dtype=float)

    scorer = model.fit(X["train"], sp.train[TARGET].to_numpy(),
                       kind="lgbm", cfg=cfg, seed=cfg.base_seed)
    p_test = scorer.predict_proba_fraud(X["test"])
    s_cal = conformal.nonconformity(scorer.predict_proba_fraud(X["cal"]))
    s_test = conformal.nonconformity(p_test)

    pop_cal, pop_test = shift.route(sp.cal), shift.route(sp.test)
    costs = cost.Costs.from_config(cfg)

    t = costs.bayes_threshold(amt_test)
    print(f"\ncost model             c_FN = amount + Rs{costs.fee_chargeback:,.0f}   "
          f"c_FP = {costs.margin:.2f}*amount + Rs{costs.goodwill:,.0f}   "
          f"review Rs{costs.review_cost:,.0f}")
    print(f"Bayes threshold        per-transaction, not tuned: "
          f"p50={np.median(t):.3f}  range {t.min():.3f}-{t.max():.3f}")
    print(f"TEST                   {len(y_test):,} txns, {int(y_test.sum()):,} fraud, "
          f"Rs{amt_test.sum():,.0f} volume")

    cap = float(f["review_cap_headline"])

    # ---- arms -----------------------------------------------------------------------------
    rows = {}
    a_b1 = cost.decide_bayes(p_test, amt_test, costs)
    rows["B1"] = cost.realised_cost(a_b1, y_test, amt_test, costs) | {"truncated": 0.0}

    for arm, (cc, pc) in ARMS.items():
        cal = conformal.calibrate(s_cal, y_cal, pop_cal, alpha,
                                  min_cell_n=cfg.min_cell_n,
                                  class_conditional=cc, population_conditional=pc)
        sets = conformal.predict_set(s_test, pop_test, cal)
        acts = cost.decide_conformal(sets, p_test, amt_test, costs)
        acts, trunc = cost.apply_capacity(acts, p_test, amt_test, costs, cap)
        rows[arm] = cost.realised_cost(acts, y_test, amt_test, costs) | {"truncated": trunc}

    base = rows["B1"]["total"]
    print(f"\nrealised cost on TEST  (review capacity {cap:.0%})")
    print(f"{'arm':<5}{'total Rs':>13}{'per 1k':>10}{'missed':>12}{'blockedOK':>12}"
          f"{'review':>10}{'recall':>8}{'FPR':>7}{'vs B1':>11}")
    print("-" * 78)
    for arm, r in rows.items():
        delta = base - r["total"]
        mark = f"{delta:+,.0f}" if arm != "B1" else "baseline"
        print(f"{arm:<5}{r['total']:>13,.0f}{r['per_1000']:>10,.0f}"
              f"{r['missed_fraud']:>12,.0f}{r['blocked_legit']:>12,.0f}"
              f"{r['review']:>10,.0f}{r['fraud_recall']:>8.1%}{r['fpr']:>7.2%}{mark:>11}")

    best = min(rows, key=lambda a: rows[a]["total"])
    print(f"\n  lowest realised cost: {best}")
    d1, b1 = rows["D1"], rows["B1"]
    fp_share = (b1["blocked_legit"] - d1["blocked_legit"]) / max(base - d1["total"], 1e-9)
    if base > d1["total"]:
        print(f"  D1 saves Rs{base - d1['total']:,.0f} against B1, of which "
              f"{fp_share:.0%} comes from fewer false positives.")
    else:
        print(f"  D1 costs Rs{d1['total'] - base:,.0f} MORE than B1. Report that plainly --")
        print("  coverage is not free, and on this data the abstention may not pay for itself.")
    if d1["truncated"] > 0:
        print(f"  {d1['truncated']:.0%} of D1's escalations were truncated by the "
              f"{cap:.0%} capacity cap and fell back to the Bayes decision.")

    # ---- capacity sweep --------------------------------------------------------------------
    print(f"\ncapacity sweep         total cost (Rs) by review capacity")
    caps = [float(c) for c in f["review_cap_sweep"]]
    print(f"{'arm':<5}" + "".join(f"{c:>14.0%}" for c in caps))
    print("-" * 78)
    sweep = {}
    for arm, (cc, pc) in ARMS.items():
        cal = conformal.calibrate(s_cal, y_cal, pop_cal, alpha, min_cell_n=cfg.min_cell_n,
                                  class_conditional=cc, population_conditional=pc)
        sets = conformal.predict_set(s_test, pop_test, cal)
        line = []
        for c in caps:
            acts = cost.decide_conformal(sets, p_test, amt_test, costs)
            acts, _ = cost.apply_capacity(acts, p_test, amt_test, costs, c)
            line.append(cost.realised_cost(acts, y_test, amt_test, costs)["total"])
        sweep[arm] = line
        print(f"{arm:<5}" + "".join(f"{v:>14,.0f}" for v in line))
    print(f"{'B1':<5}" + "".join(f"{base:>14,.0f}" for _ in caps) + "   (no review queue)")

    # ---- sensitivity ------------------------------------------------------------------------
    pct = float(f["cost_sensitivity_pct"])
    print(f"\nsensitivity            does the sign of (B1 - D1) survive +/-{pct:.0%}?")
    print(f"{'constant':<18}{'low':>16}{'base':>16}{'high':>16}")
    print("-" * 78)
    cal_d1 = conformal.calibrate(s_cal, y_cal, pop_cal, alpha, min_cell_n=cfg.min_cell_n,
                                 class_conditional=True, population_conditional=True)
    sets_d1 = conformal.predict_set(s_test, pop_test, cal_d1)
    flips, sens = [], {}
    for name in ("fee_chargeback", "margin", "review_cost"):
        vals = []
        for mult in (1 - pct, 1.0, 1 + pct):
            c2 = cost.Costs.from_config(cfg, {name: mult})
            a1 = cost.decide_bayes(p_test, amt_test, c2)
            base2 = cost.realised_cost(a1, y_test, amt_test, c2)["total"]
            ad = cost.decide_conformal(sets_d1, p_test, amt_test, c2)
            ad, _ = cost.apply_capacity(ad, p_test, amt_test, c2, cap)
            d2 = cost.realised_cost(ad, y_test, amt_test, c2)["total"]
            vals.append(base2 - d2)
        sens[name] = vals
        signs = {np.sign(v) for v in vals if abs(v) > 1e-9}
        if len(signs) > 1:
            flips.append(name)
        print(f"{name:<18}" + "".join(f"{v:>+16,.0f}" for v in vals))

    print()
    if flips:
        print(f"  SIGN FLIPS on: {', '.join(flips)}. The conclusion is NOT robust to these")
        print("  assumptions and the slide must say so, naming the constant that decides it.")
    else:
        print("  Sign is stable across every sweep. The direction of the conclusion does not")
        print("  depend on the cost constants -- only its magnitude does.")

    _plot(cfg, rows, sweep, caps, base, source)

    out = cfg.results_dir() / f"block4_{source}.json"
    out.write_text(json.dumps({"config_hash": cfg.hash(), "data_source": source,
                               "capacity": cap, "arms": rows,
                               "capacity_sweep": {"caps": caps, "totals": sweep, "b1": base},
                               "sensitivity": sens, "sign_flips": flips},
                              indent=2, default=float), encoding="utf-8")
    print(f"\nwritten                {out.relative_to(config.REPO_ROOT)}")
    print("=" * 78)
    return 0


def _plot(cfg, rows, sweep, caps, base, source):
    fig_dir = cfg.results_dir() / "figures"
    fig_dir.mkdir(exist_ok=True)
    tag = "" if source == "ieee-cis" else f"  [{source} -- NOT REPORTABLE]"

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.4))

    arms = list(rows)
    comps = ["missed_fraud", "blocked_legit", "review"]
    labels = ["missed fraud", "blocked legitimate", "review"]
    bottom = np.zeros(len(arms))
    for comp, lab in zip(comps, labels):
        vals = np.array([rows[a][comp] for a in arms])
        a1.bar(arms, vals, bottom=bottom, label=lab)
        bottom += vals
    a1.set_ylabel("realised cost (₹)")
    a1.set_title("Graph 3a — where the money goes")
    a1.legend(fontsize=8); a1.grid(alpha=.3, axis="y")

    for arm, line in sweep.items():
        a2.plot([c * 100 for c in caps], line, "o-", label=arm)
    a2.axhline(base, ls="--", c="k", lw=1, label="B1 (no review)")
    a2.set_xlabel("review capacity (% of volume)")
    a2.set_ylabel("total realised cost (₹)")
    a2.set_title("Graph 3b — cost vs analyst capacity")
    a2.legend(fontsize=8); a2.grid(alpha=.3)

    fig.suptitle(f"Cost of the coverage promise{tag}", fontsize=10)
    fig.tight_layout(); fig.savefig(fig_dir / "graph3_cost.png", dpi=150); plt.close(fig)
    print(f"\nfigure                 figures/graph3_cost.png")


if __name__ == "__main__":
    raise SystemExit(main())
