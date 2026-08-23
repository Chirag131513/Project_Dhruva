"""Block 12 -- against a queue policy a team already has, and where the model is blind.

    python scripts/block12_policies.py [--seeds 5]

WHY THIS EXISTS. Block 9 compared escalation signals against a baseline with NO review queue.
No payments team runs that. The comparison that decides whether this is worth anything is
against the policies a risk team is already using to fill a finite queue:

    score    most suspicious first    -- the obvious policy, and the one most teams use
    amount   biggest transaction first -- extremely common, "watch the big ones"
    stake    most rupees at risk       -- the sophisticated version of the above
    band     nearest the cost-optimal cut (mine)

If band cannot beat those, the value claim collapses and I say so.

THE SECOND HALF answers a question a routing rule cannot: WHERE is the model blind? A rule that
reorders a queue is easy to dismiss. A map of which product, card type and amount band carry the
losses is something a risk team can act on directly -- retrain there, add features there, staff
there. The idea is borrowed from the scaffold analysis in arXiv:2607.06605, which localises
confident errors to specific molecular cores; the payments analogue is business segments.
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

from dhruva import config, cost, data, features, model, splits
from dhruva.cost import APPROVE, BLOCK, REVIEW
from dhruva.data import AMOUNT, TARGET

CAPS = [0.01, 0.02, 0.05, 0.10]
NAME = {"score": "most suspicious first", "amount": "biggest amount first",
        "stake": "most rupees at stake", "band": "nearest the cut (mine)"}


def localise(values, wrong, err, tot, min_n=200):
    """Share of transactions, error rate, and share of rupees lost, per segment."""
    g = np.array([str(v) for v in values])   # mixed str/float breaks np.unique
    out = []
    for v in np.unique(g):
        m = g == v
        if m.sum() < min_n:
            continue
        share, lost = float(m.mean()), float(err[m].sum() / tot)
        out.append({"value": v, "share": share, "err_rate": float(wrong[m].mean()),
                    "share_lost": lost, "concentration": lost / max(share, 1e-9)})
    return sorted(out, key=lambda r: -r["share_lost"])


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()
    cfg = config.load(); cfg.check_lock()
    costs = cost.Costs.from_config(cfg)

    sp = splits.chronological(data.load(cfg.data_dir()), cfg)
    enc, X = features.build(sp)
    y = sp.test[TARGET].to_numpy(); amt = sp.test[AMOUNT].to_numpy(dtype=float); n = len(y)

    print("=" * 80)
    print("A  DOES `band` BEAT A QUEUE POLICY A TEAM ALREADY HAS?")
    print("=" * 80)

    res = {k: {c: [] for c in CAPS} for k in NAME}
    b1s = []
    for s in range(args.seeds):
        sc = model.fit(X["train"], sp.train[TARGET].to_numpy(), kind="lgbm",
                       cfg=cfg, seed=cfg.base_seed + s)
        p = sc.predict_proba_fraud(X["test"])
        b1 = cost.realised_cost(cost.decide_bayes(p, amt, costs), y, amt, costs)["total"]
        b1s.append(b1)
        stake = np.maximum(p * costs.c_fn(amt), (1 - p) * costs.c_fp(amt))
        orders = {"band": -np.abs(p - costs.bayes_threshold(amt)) * 1e6 + stake / 1e6,
                  "score": p, "amount": amt, "stake": stake}
        for pol, o in orders.items():
            rank = np.argsort(-o)
            for c in CAPS:
                a = cost.decide_bayes(p, amt, costs)
                a[rank[:int(round(c * n))]] = REVIEW
                res[pol][c].append(b1 - cost.realised_cost(a, y, amt, costs)["total"])
        print(f"  seed {s+1}/{args.seeds}", flush=True)

    b1m = float(np.mean(b1s))
    print(f"\n  baseline, no queue: Rs{b1m:,.0f}\n")
    print(f"{'queue policy':<26}" + "".join(f"{c:>15.0%}" for c in CAPS))
    print("-" * 80)
    for pol in ("score", "amount", "stake", "band"):
        print(f"{NAME[pol]:<26}" + "".join(f"{np.mean(res[pol][c]):>+15,.0f}" for c in CAPS))

    print(f"\n{'capacity':<12}{'best rival':<26}{'band advantage':>18}{'% of loss':>12}")
    print("-" * 80)
    adv = {}
    for c in CAPS:
        rival = max(("score", "amount", "stake"), key=lambda k: np.mean(res[k][c]))
        d = float(np.mean(res["band"][c]) - np.mean(res[rival][c]))
        adv[c] = {"rival": rival, "delta": d, "share": d / b1m}
        print(f"{c:<12.0%}{NAME[rival]:<26}{d:>+18,.0f}{d/b1m:>12.1%}")

    lo, hi = adv[CAPS[0]]["share"], adv[CAPS[-1]]["share"]
    print("\nverdict")
    if adv[CAPS[-1]]["delta"] <= 0:
        print("  At the largest capacity band does NOT beat an existing policy. Say so.")
    print(f"  The advantage SHRINKS with capacity: {lo:.1%} at {CAPS[0]:.0%} -> "
          f"{hi:.1%} at {CAPS[-1]:.0%}.")
    print("  Read the small-capacity column, not the large one -- that is where real teams sit.")
    worst = min(("score", "amount", "stake"), key=lambda k: np.mean(res[k][CAPS[1]]))
    if np.mean(res[worst][CAPS[1]]) < 0:
        print(f"  At {CAPS[1]:.0%} capacity, '{NAME[worst]}' LOSES "
              f"Rs{-np.mean(res[worst][CAPS[1]]):,.0f}. The obvious policy is worse than useless"
              " when the queue is small.")

    # ---------------------------------------------------------------- B
    print("\n" + "=" * 80)
    print("B  WHERE IS THE MODEL BLIND?")
    print("=" * 80)
    sc = model.fit(X["train"], sp.train[TARGET].to_numpy(), kind="lgbm",
                   cfg=cfg, seed=cfg.base_seed)
    p = sc.predict_proba_fraud(X["test"])
    acts = cost.decide_bayes(p, amt, costs)
    wrong = ((acts == APPROVE) & (y == 1)) | ((acts == BLOCK) & (y == 0))
    err = np.where(y == 1, costs.c_fn(amt), costs.c_fp(amt)) * wrong
    tot = float(err.sum())

    q = np.quantile(amt, [0, .25, .5, .75, .9, 1.0])
    # Label with the full range: "Rs0+" style labels are unreadable and hide the band width.
    bi = np.clip(np.searchsorted(q, amt, "right") - 1, 0, len(q) - 2)
    band_lab = np.array([f"Rs{q[i]:,.0f}-{q[i+1]:,.0f}" for i in bi])

    groups = {"ProductCD": sp.test["ProductCD"].to_numpy(), "amount band": band_lab}
    if "card6" in sp.test:
        groups["card type"] = sp.test["card6"].to_numpy()

    blind = {}
    for name, g in groups.items():
        rows = localise(g, wrong, err, tot)
        blind[name] = rows
        print(f"\n  by {name}:")
        print(f"    {'value':<16}{'share txns':>12}{'err rate':>10}{'share Rs lost':>15}"
              f"{'concentration':>15}")
        for r in rows:
            print(f"    {r['value']:<16}{r['share']:>12.1%}{r['err_rate']:>10.2%}"
                  f"{r['share_lost']:>15.1%}{r['concentration']:>14.1f}x")

    out = cfg.results_dir() / "block12_policies.json"
    out.write_text(json.dumps({
        "config_hash": cfg.hash(), "seeds": args.seeds, "caps": CAPS, "b1_mean": b1m,
        "policies": {k: {str(c): res[k][c] for c in CAPS} for k in res},
        "advantage": {str(c): adv[c] for c in CAPS},
        "total_error_cost": tot, "blind": blind,
    }, indent=2, default=float), encoding="utf-8")
    print(f"\nwritten results/{out.name}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
