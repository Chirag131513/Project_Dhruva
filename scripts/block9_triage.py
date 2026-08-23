"""Block 9 -- what is abstention actually worth under a hard capacity limit?

    python scripts/block9_triage.py [--seeds 10]

THIS IS THE DECISIVE EXPERIMENT. It replaces coverage as the project's headline and it carries
kill conditions K1-K5 from the Stage-1 verdict.

THE QUESTION
    A merchant can review k% of transactions, no more. Given a fixed budget of analyst
    attention, WHICH cases should be escalated -- and does escalating them beat simply acting on
    a cost-optimal threshold?

THE FAIR COMPARISON
    Every signal escalates the SAME VOLUME (top-k by its own ambiguity ranking). Non-escalated
    rows get the per-transaction Bayes decision. So the arms differ only in WHICH cases they
    pick, never in how many. Anything else would compare escalation rate, not signal quality.

    conformal   the prediction set is not a singleton; ties broken by rupees at stake
    band        |p - t(x)| small -- plain distance to the cost-optimal threshold, no conformal
                machinery at all.  <<< THIS IS K3. If it matches conformal, my machinery is
                decoration and I say so.
    disagree    spread across boosting stages (100/200/300/400 trees) -- a cheap stand-in for
                DAUNT's ensemble-disagreement signal. Labelled a PROXY, not a reimplementation.
    random      sanity floor. If a signal cannot beat random escalation it is not a signal.

KILL CONDITIONS, declared before running
    K1  net <= 0 at every capacity            -> abandon the economic claim
    K2  benefit not monotone in capacity      -> drop the "scales with capacity" claim
    K3  band matches conformal within CI      -> conformal is unnecessary; report that
    K4  disagree beats conformal              -> contribution becomes the curve, not the signal
    K5  sign flips under +/-50% cost sweep    -> downgrade to "cost-neutral"

Do not tune anything in this file to change which condition fires.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from dhruva import config, conformal, cost, data, features, model, splits
from dhruva.cost import APPROVE, BLOCK, REVIEW
from dhruva.data import AMOUNT, TARGET

CAPS = [0.01, 0.02, 0.05, 0.10]
SIGNALS = ["conformal", "band", "disagree", "random"]
STAGES = [100, 200, 300, 400]


def ambiguity(sig, p, sets, amt, costs, rng):
    """Rank rows by how much a human would add. Higher = escalate sooner.

    Every signal returns a score on the same scale-free footing; only the ordering is used.
    """
    stake = np.maximum(p * costs.c_fn(amt), (1 - p) * costs.c_fp(amt))
    if sig == "conformal":
        # Non-singleton sets first, ordered within that group by rupees at stake.
        return np.where(sets.sum(axis=1) != 1, 1.0, 0.0) * 1e12 + stake
    if sig == "band":
        # Distance to the per-transaction Bayes threshold. No conformal anything.
        return -np.abs(p - costs.bayes_threshold(amt)) * 1e6 + stake / 1e6
    if sig == "disagree":
        return p  # replaced by caller with stage spread; kept for signature symmetry
    if sig == "random":
        return rng.random(p.size)
    raise ValueError(sig)


def run_arm(order, k, p, y, amt, costs):
    """Escalate the top-k rows by `order`; everything else takes the Bayes decision."""
    acts = cost.decide_bayes(p, amt, costs)
    if k > 0:
        acts[np.argsort(-order)[:k]] = REVIEW
    return cost.realised_cost(acts, y, amt, costs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    args = ap.parse_args()

    cfg = config.load(); cfg.check_lock()
    f = cfg.frozen
    costs = cost.Costs.from_config(cfg)

    print("=" * 78)
    print("BLOCK 9  --  abstention economics under capacity  (decisive experiment)")
    print("=" * 78)

    df = data.load(cfg.data_dir())
    print(f"\nsource                 {df.attrs['data_source']}")
    sp = splits.chronological(df, cfg)
    enc, X = features.build(sp)
    y_tr = sp.train[TARGET].to_numpy()
    y_cal, y_te = sp.cal[TARGET].to_numpy(), sp.test[TARGET].to_numpy()
    amt = sp.test[AMOUNT].to_numpy(dtype=float)
    seg_c = sp.cal["ProductCD"].astype(str).to_numpy()
    seg_t = sp.test["ProductCD"].astype(str).to_numpy()
    n = len(y_te)
    a_amd = {0: float(f["review_cap_headline"]) / float((y_cal == 0).mean()),
             1: float(f["amendment1_alpha_fraud"])}

    print(f"TEST                   {n:,} rows, {int(y_te.sum()):,} fraud")
    print(f"seeds                  {args.seeds}   capacities {[f'{c:.0%}' for c in CAPS]}\n")

    # results[signal][cap] = list over seeds of net-vs-B1
    res = {s: {c: [] for c in CAPS} for s in SIGNALS}
    b1_seeds = []

    for si in range(args.seeds):
        seed = cfg.base_seed + si
        rng = np.random.default_rng(seed)
        sc = model.fit(X["train"], y_tr, kind="lgbm", cfg=cfg, seed=seed)
        p = sc.predict_proba_fraud(X["test"])
        b1 = cost.realised_cost(cost.decide_bayes(p, amt, costs), y_te, amt, costs)
        b1_seeds.append(b1["total"])

        cal = conformal.calibrate(
            conformal.nonconformity(sc.predict_proba_fraud(X["cal"])), y_cal, seg_c, a_amd,
            min_cell_n=cfg.min_cell_n, class_conditional=True, population_conditional=True)
        sets = conformal.predict_set(conformal.nonconformity(p), seg_t, cal)

        # boosting-stage spread: one fit, four predictions. A proxy for ensemble disagreement.
        stage_p = np.vstack([
            np.clip(sc.model.predict_proba(X["test"], num_iteration=m)[:, 1], 1e-6, 1 - 1e-6)
            for m in STAGES])
        spread = stage_p.std(axis=0)

        for sig in SIGNALS:
            order = spread if sig == "disagree" else ambiguity(sig, p, sets, amt, costs, rng)
            for c in CAPS:
                r = run_arm(order, int(round(c * n)), p, y_te, amt, costs)
                res[sig][c].append(b1["total"] - r["total"])

        print(f"  seed {si+1}/{args.seeds}  B1 Rs{b1['total']:,.0f}   "
              + "  ".join(f"{s[:4]}@5%:{res[s][0.05][-1]:+,.0f}" for s in SIGNALS), flush=True)

    # ---------------------------------------------------------------- report
    b1m = float(np.mean(b1_seeds))
    print(f"\n{'='*78}\nNET BENEFIT vs B1 (mean over {args.seeds} seeds, B1 = Rs{b1m:,.0f})")
    print(f"{'signal':<11}" + "".join(f"{c:>16.0%}" for c in CAPS))
    print("-" * 78)
    for s in SIGNALS:
        print(f"{s:<11}" + "".join(f"{np.mean(res[s][c]):>+16,.0f}" for c in CAPS))
    print(f"\n{'':11}" + "".join(f"{'% of loss':>16}" for _ in CAPS))
    print(f"{'conformal':<11}" + "".join(f"{np.mean(res['conformal'][c])/b1m:>16.1%}" for c in CAPS))

    # ---------------------------------------------------------------- kill tests
    try:
        from scipy.stats import wilcoxon
    except ImportError:
        wilcoxon = None

    conf = {c: np.array(res["conformal"][c]) for c in CAPS}
    band = {c: np.array(res["band"][c]) for c in CAPS}
    dis = {c: np.array(res["disagree"][c]) for c in CAPS}
    means = [conf[c].mean() for c in CAPS]

    print(f"\n{'='*78}\nKILL CONDITIONS")
    k1 = all(m <= 0 for m in means)
    print(f"  K1  net<=0 everywhere ............ {'FIRED' if k1 else 'passed'}"
          f"   (best {max(means):+,.0f} at {CAPS[int(np.argmax(means))]:.0%})")
    mono = all(b >= a - 1e-9 for a, b in zip(means, means[1:]))
    print(f"  K2  non-monotone in capacity ..... {'passed' if mono else 'FIRED'}"
          f"   ({' -> '.join(f'{m:+,.0f}' for m in means)})")

    hi = max(CAPS)
    d = conf[hi] - band[hi]
    lo_ci, hi_ci = np.percentile(
        [np.mean(np.random.default_rng(i).choice(d, d.size)) for i in range(2000)], [2.5, 97.5])
    p_band = wilcoxon(conf[hi], band[hi]).pvalue if wilcoxon and d.std() > 0 else float("nan")
    # K3 fires when the simple rule is AT LEAST as good -- a tie kills the machinery, and the
    # simple rule being outright better kills it harder. Testing only for a tie (0 inside the CI)
    # would report "passed" in precisely the case where conformal is actively worse.
    k3_tie = lo_ci <= 0 <= hi_ci
    k3_worse = hi_ci < 0
    k3 = k3_tie or k3_worse
    verdict3 = ("FIRED - band BEATS conformal" if k3_worse
                else "FIRED - indistinguishable" if k3_tie else "passed")
    print(f"  K3  band >= conformal ............ {verdict3}")
    print(f"      conformal-band @ {hi:.0%}: {d.mean():+,.0f}  95% CI [{lo_ci:+,.0f}, {hi_ci:+,.0f}]"
          f"  p={p_band:.4f}")
    k4 = dis[hi].mean() > conf[hi].mean()
    print(f"  K4  disagreement beats conformal . {'FIRED' if k4 else 'passed'}"
          f"   ({dis[hi].mean():+,.0f} vs {conf[hi].mean():+,.0f})")

    print(f"\n  n={args.seeds} paired; min achievable two-sided Wilcoxon p ~ "
          f"{2**-(args.seeds-1):.4f}. A non-significant result here means underpowered, "
          f"not 'no effect'.")

    # ---------------------------------------------------------------- K5 sensitivity
    print(f"\n{'='*78}\nK5  cost sensitivity at {hi:.0%} capacity (single seed)")
    sc = model.fit(X["train"], y_tr, kind="lgbm", cfg=cfg, seed=cfg.base_seed)
    p = sc.predict_proba_fraud(X["test"])
    cal = conformal.calibrate(
        conformal.nonconformity(sc.predict_proba_fraud(X["cal"])), y_cal, seg_c, a_amd,
        min_cell_n=cfg.min_cell_n, class_conditional=True, population_conditional=True)
    sets = conformal.predict_set(conformal.nonconformity(p), seg_t, cal)
    pct = float(f["cost_sensitivity_pct"]); flips = []
    print(f"{'constant':<17}{'-50%':>16}{'base':>16}{'+50%':>16}")
    print("-" * 78)
    sens = {}
    for name in ("fee_chargeback", "margin", "review_cost", "goodwill"):
        row = []
        for m in (1 - pct, 1.0, 1 + pct):
            c2 = cost.Costs.from_config(cfg, {name: m})
            b = cost.realised_cost(cost.decide_bayes(p, amt, c2), y_te, amt, c2)["total"]
            o = ambiguity("conformal", p, sets, amt, c2, np.random.default_rng(0))
            row.append(b - run_arm(o, int(round(hi * n)), p, y_te, amt, c2)["total"])
        sens[name] = row
        if len({np.sign(v) for v in row if abs(v) > 1e-9}) > 1:
            flips.append(name)
        print(f"{name:<17}" + "".join(f"{v:>+16,.0f}" for v in row))
    print(f"\n  K5  sign flips ................... {'FIRED on ' + ', '.join(flips) if flips else 'passed'}")

    # ---------------------------------------------------------------- verdict
    print(f"\n{'='*78}\nVERDICT")
    best_sig = max(SIGNALS, key=lambda s: np.mean(res[s][hi]))
    if k1:
        print("  K1 fired. The economic claim is dead. Fall back to the identity and the")
        print("  model-quality findings as a measurement study, and report this honestly.")
    elif k3 or k4:
        print(f"  Conformal is NOT the best escalation signal. At {hi:.0%} capacity the winner is")
        print(f"  '{best_sig}' at {np.mean(res[best_sig][hi]):+,.0f} against conformal's "
              f"{conf[hi].mean():+,.0f}.")
        print("  The honest headline is therefore about the CAPACITY CURVE and the value of")
        print("  escalating at all -- not about conformal prediction, which I should stop")
        print("  presenting as the method. Report the ranking of signals as the result.")
    else:
        print(f"  Conformal abstention beats both the threshold and the simpler signals at "
              f"{hi:.0%} capacity,")
        print(f"  cutting loss by {max(means)/b1m:.1%}. K5 " +
              ("flagged sign instability -- report as cost-neutral where it flips."
               if flips else "held across every cost sweep."))

    out = cfg.results_dir() / "block9_triage.json"
    out.write_text(json.dumps({
        "config_hash": cfg.hash(), "seeds": args.seeds, "caps": CAPS, "b1_mean": b1m,
        "net": {s: {str(c): res[s][c] for c in CAPS} for s in SIGNALS},
        "kill": {"K1": bool(k1), "K2": bool(not mono), "K3": bool(k3), "K4": bool(k4),
                 "K5": flips},
        "k3_detail": {"delta": float(d.mean()), "ci": [float(lo_ci), float(hi_ci)],
                      "p": float(p_band)},
        "sensitivity": sens,
    }, indent=2, default=float), encoding="utf-8")
    print(f"\nwritten                results/{out.name}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
