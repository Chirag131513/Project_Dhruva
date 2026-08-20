"""Block 3 -- the tau sweep. Produces Graph 1 and Graph 2.

    python scripts/block3_shift.py [--dev] [--seeds 3]

GRAPH 1 (E2, lambda sweep, arm B1)
    R(lambda) = [relative ECE degradation] / [relative PR-AUC degradation]
    H1 predicts R > 1 and rising: calibration decays faster than discrimination.
    The RATIO is the hypothesis. Eyeballing two curves until one looks worse than the other is
    the failure this pre-registration exists to prevent.

GRAPH 2 (E3, rho sweep at the headline lambda)
    Per-cell coverage for B2 / B3 / D1. H3a predicts only D1 holds nominal on BOTH populations.

Also reports the routing agreement between tau's assignment and the signal-based router, since
every coverage number is conditional on the router having put rows in the right cell.
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
import pandas as pd

from dhruva import config, conformal, data, features, metrics, model, shift, splits
from dhruva.conformal import FRAUD, LEGIT
from dhruva.data import TARGET

ARMS = {"B2": (False, False), "B3": (True, False), "D1": (True, True)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()

    cfg = config.load()
    cfg.check_lock()
    alpha, target = cfg.alpha, 1.0 - cfg.alpha
    f = cfg.frozen
    lam_head = float(f["lambda_headline"])
    kappa = float(f["kappa"])

    print("=" * 78)
    print("BLOCK 3  --  tau sweep  (Graph 1 + Graph 2)")
    print("=" * 78)

    df = data.load(cfg.data_dir(), dev=args.dev, seed=cfg.base_seed)
    source = df.attrs["data_source"]
    print(f"\nsource                 {source}")
    if source != "ieee-cis":
        print("  [not reportable -- IEEE-CIS is the only source for a headline result]")

    sp = splits.chronological(df, cfg)
    enc, _ = features.build(sp)
    y_cal, y_test = sp.cal[TARGET].to_numpy(), sp.test[TARGET].to_numpy()

    print(f"\nfitting base scorer on unshifted TRAIN ...")
    scorer = model.fit(enc.transform(sp.train), sp.train[TARGET].to_numpy(),
                       kind="lgbm", cfg=cfg, seed=cfg.base_seed)
    print("  (the base model is NEVER refitted below -- that is the point)")

    # ---------------------------------------------------------------------------------------
    # E2 / Graph 1 : lambda sweep, everything shifted so the effect is not diluted by rho
    # ---------------------------------------------------------------------------------------
    print(f"\nE2  lambda sweep   (rho = 1.0, so lambda is the only moving part)")
    print(f"{'lambda':>8}{'PR-AUC':>10}{'ECE':>10}{'rel dPR':>10}{'rel dECE':>11}{'R':>9}")
    print("-" * 78)

    e2, base_ref = [], None
    for lam in f["lambda_sweep"]:
        per_seed = []
        for s in range(args.seeds):
            rng = np.random.default_rng(cfg.base_seed + 1000 * s)
            shifted = shift.assign(len(sp.test), 1.0, rng)
            t = shift.tau(sp.test, lam, shifted, rng, kappa)
            p = scorer.predict_proba_fraud(enc.transform(t))
            per_seed.append(metrics.summarise(y_test, p, float(f["review_cap_headline"])))

        row = {k: float(np.mean([d[k] for d in per_seed])) for k in per_seed[0]}
        row["lambda"] = lam
        if base_ref is None:
            base_ref = row
        r = metrics.degradation_ratio(base_ref, row)
        row["R"] = r
        rel_pr = (base_ref["pr_auc"] - row["pr_auc"]) / base_ref["pr_auc"]
        rel_ece = (row["ece"] - base_ref["ece"]) / base_ref["ece"]
        row["rel_d_pr"], row["rel_d_ece"] = rel_pr, rel_ece
        e2.append(row)
        print(f"{lam:>8.2f}{row['pr_auc']:>10.4f}{row['ece']:>10.4f}"
              f"{rel_pr:>10.3f}{rel_ece:>11.3f}{r:>9.2f}")

    finite = [r["R"] for r in e2[1:] if np.isfinite(r["R"])]
    print("\nH1 verdict")
    if not finite:
        print("  R undefined across the sweep (no measurable degradation in one term).")
    elif all(r > 1 for r in finite) and finite[-1] >= finite[0]:
        print(f"  R > 1 throughout and rising ({finite[0]:.2f} -> {finite[-1]:.2f}).")
        print("  Calibration degrades faster than discrimination -- CONSISTENT with H1.")
    elif all(r > 1 for r in finite):
        print(f"  R > 1 throughout but not monotone ({min(finite):.2f}-{max(finite):.2f}).")
        print("  Partially consistent with H1; report the non-monotonicity.")
    else:
        print(f"  R <= 1 somewhere (min {min(finite):.2f}). H1 is NOT supported here.")
        print("  Honest conclusion: signal loss is a model problem, not a calibration problem.")
        print("  Report the curve as measured. Do not tune until the pattern appears.")

    # ---------------------------------------------------------------------------------------
    # E3 / Graph 2 : rho sweep at headline lambda, three arms
    # ---------------------------------------------------------------------------------------
    print(f"\nE3  rho sweep at lambda={lam_head}   coverage per (population x class), "
          f"target {target:.0%}")
    print(f"{'rho':>6}{'arm':>5}{'BASE.lgt':>10}{'BASE.frd':>10}{'SHFT.lgt':>10}"
          f"{'SHFT.frd':>10}{'review':>9}{'route':>8}")
    print("-" * 78)

    e3 = []
    for rho in f["rho_sweep"]:
        for arm, (cc, pc) in ARMS.items():
            acc = {}
            rev, agree = [], []
            for s in range(args.seeds):
                rng = np.random.default_rng(cfg.base_seed + 1000 * s + 7)

                sh_cal = shift.assign(len(sp.cal), rho, rng)
                cal_df = shift.tau(sp.cal, lam_head, sh_cal, rng, kappa)
                sh_test = shift.assign(len(sp.test), rho, rng)
                test_df = shift.tau(sp.test, lam_head, sh_test, rng, kappa)

                pop_cal = shift.route(cal_df)
                pop_test = shift.route(test_df)
                agree.append(shift.routing_report(sh_test, pop_test).agreement)

                s_cal = conformal.nonconformity(scorer.predict_proba_fraud(enc.transform(cal_df)))
                s_test = conformal.nonconformity(
                    scorer.predict_proba_fraud(enc.transform(test_df)))

                cal = conformal.calibrate(s_cal, y_cal, pop_cal, alpha,
                                          min_cell_n=cfg.min_cell_n,
                                          class_conditional=cc, population_conditional=pc)
                sets = conformal.predict_set(s_test, pop_test, cal)
                cov = conformal.coverage(sets, y_test, pop_test, cal)
                rev.append(float((sets.sum(axis=1) != 1).mean()))
                for k, v in cov.items():
                    acc.setdefault(k, []).append(v)

            cells = {f"{k[0]}|{k[1]}": float(np.nanmean(v)) if not all(np.isnan(v)) else float("nan")
                     for k, v in acc.items()}
            g = lambda p, c: cells.get(f"{p}|{c}", float("nan"))
            row = {"rho": rho, "arm": arm, "review": float(np.mean(rev)),
                   "routing_agreement": float(np.mean(agree)), **cells}
            e3.append(row)
            print(f"{rho:>6.1f}{arm:>5}{g('BASE', LEGIT):>10.3f}{g('BASE', FRAUD):>10.3f}"
                  f"{g(shift.SHIFTED, LEGIT):>10.3f}{g(shift.SHIFTED, FRAUD):>10.3f}"
                  f"{row['review']:>9.1%}{row['routing_agreement']:>8.1%}")

    _plot(cfg, e2, e3, target, lam_head, source)

    out = cfg.results_dir() / f"block3_{source}.json"
    out.write_text(json.dumps({"config_hash": cfg.hash(), "data_source": source,
                               "seeds": args.seeds, "e2": e2, "e3": e3},
                              indent=2, default=float), encoding="utf-8")
    print(f"\nwritten                {out.relative_to(config.REPO_ROOT)}")
    print("=" * 78)
    return 0


def _plot(cfg, e2, e3, target, lam_head, source):
    fig_dir = cfg.results_dir() / "figures"
    fig_dir.mkdir(exist_ok=True)
    tag = "" if source == "ieee-cis" else f"  [{source} -- NOT REPORTABLE]"

    # ---- Graph 1 -------------------------------------------------------------------------
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    lam = [r["lambda"] for r in e2]
    a1.plot(lam, [r["rel_d_pr"] for r in e2], "o-", label="discrimination (rel. ΔPR-AUC)")
    a1.plot(lam, [r["rel_d_ece"] for r in e2], "s-", label="calibration (rel. ΔECE)")
    a1.set_xlabel("λ  signal-loss severity"); a1.set_ylabel("relative degradation")
    a1.set_title("Graph 1a — what degrades"); a1.legend(fontsize=8); a1.grid(alpha=.3)

    R = [r["R"] if np.isfinite(r["R"]) else np.nan for r in e2]
    a2.plot(lam, R, "o-", color="crimson")
    a2.axhline(1.0, ls="--", c="k", lw=1, label="R = 1 (equal rates)")
    a2.set_xlabel("λ"); a2.set_ylabel("R = relΔECE / relΔPR-AUC")
    a2.set_title("Graph 1b — H1: R > 1 and rising"); a2.legend(fontsize=8); a2.grid(alpha=.3)
    fig.suptitle(f"Degradation under behavioural signal loss{tag}", fontsize=10)
    fig.tight_layout(); fig.savefig(fig_dir / "graph1_degradation.png", dpi=150); plt.close(fig)

    # ---- Graph 2 -------------------------------------------------------------------------
    d = pd.DataFrame(e3)
    cells = [("BASE|0", "BASE·legit"), ("BASE|1", "BASE·fraud"),
             ("SHIFTED|0", "SHIFTED·legit"), ("SHIFTED|1", "SHIFTED·fraud")]
    fig, axes = plt.subplots(1, len(cells), figsize=(15, 3.6), sharey=True)
    for ax, (key, label) in zip(axes, cells):
        for arm, style in (("B2", "o:"), ("B3", "s--"), ("D1", "D-")):
            sub = d[d["arm"] == arm]
            if key in sub:
                ax.plot(sub["rho"], sub[key], style, label=arm, ms=4)
        ax.axhline(target, c="k", ls="--", lw=1)
        ax.axhspan(target - .02, target + .02, color="k", alpha=.06)
        ax.set_title(label, fontsize=9); ax.set_xlabel("ρ  shifted share"); ax.grid(alpha=.3)
    axes[0].set_ylabel(f"empirical coverage (target {target:.0%})")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Graph 2 — coverage per cell at λ={lam_head}{tag}", fontsize=10)
    fig.tight_layout(); fig.savefig(fig_dir / "graph2_coverage.png", dpi=150); plt.close(fig)

    print(f"\nfigures                {fig_dir.name}/graph1_degradation.png, "
          f"{fig_dir.name}/graph2_coverage.png")


if __name__ == "__main__":
    raise SystemExit(main())
