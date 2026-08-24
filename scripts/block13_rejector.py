"""Block 13 -- a learned rejector against the one-line rule, and an analyst-accuracy sweep.

    python scripts/block13_rejector.py [--seeds 5]

=====================================================================================
PRE-REGISTERED BEFORE THE FIRST RUN. Written into this docstring, committed, and not
edited afterwards. Every interpretation below was fixed while the outcome was unknown.
=====================================================================================

WHY. RESULTS section 11 has said from the beginning that `band` was written as a STRAWMAN for
the Block 9 kill test and won anyway, so the signal space is barely explored. The obvious
objection from anyone who has trained a model is: "you compared your hand-built ranking against
three heuristics -- did you try just LEARNING the ranking?" Until now the answer was no, and the
write-up invited the question. This block answers it.

EXPERIMENT 1 -- the learned rejector.
Train a small model to predict, per transaction, whether ESCALATING IT YIELDS POSITIVE REALISED
RUPEE VALUE, then rank the queue by that prediction.

    target      v(x) = cost_if_Bayes_decides(x) - cost_if_reviewed(x)  >  0
                where cost_if_reviewed = review_cost + eps_hum * (c_FN if fraud else c_FP)
    features    ONLY what the gate already has: p, amount, log1p(amount), and one-hot
                ProductCD and card6. No V/C/D/M blocks, no engineered features.
    trained on  the CALIBRATION split. Never on test.
    two arms    logistic regression, and a deliberately shallow LightGBM. Both use FIXED
                settings declared here before the run (GBM: 100 trees, 8 leaves, depth 3,
                lr 0.05). NO TUNING PASS. If beating band needs a hyperparameter search,
                the finding is "band stands" and I report that instead of searching.

PRE-REGISTERED INTERPRETATION. Decided at 2% capacity, the honest operating point, measured in
points of baseline loss (1 point = 1% of the no-queue baseline). Encoded in verdict() below so
it cannot be re-read favourably afterwards:

    rejector - band  >=  +2 points   ->  "hand-built ranking left money on the table, and here
                                          is the better rule." Report the rejector as the method.
    within        +/- 2 points       ->  "the one-line band rule is near-optimal; simplicity
                                          wins." A learned model with more information and a
                                          label requirement cannot beat one line of arithmetic.
    rejector - band  <=  -2 points   ->  "band is robust; the simple rule generalises."

ALL THREE ARE REPORTABLE AND USEFUL. There is no outcome of this experiment that is bad for the
project, which is precisely why it is safe to run and why it was pre-registered.

STATED IN ADVANCE, REGARDLESS OF WHO WINS: the rejector needs LABELS to train and `band` needs
none. Chargeback labels arrive weeks late (section 8). So even a rejector that wins on rupees
carries a deployment cost band does not, and that has to be said in the same breath as the
number.

ALSO STATED IN ADVANCE: the pre-registered target is a CLASSIFICATION of the sign of v(x). It
therefore ignores magnitude -- a case worth +1 rupee ranks alongside one worth +50,000. That is
a real weakness of the specified target and I am not going to quietly switch to a regressor if
classification loses; I will report the limitation.

EXPERIMENT 2 -- analyst accuracy sweep.
The whole project assumes a 5% analyst error rate (95% accuracy), declared and never measured
(section 8). Re-run band vs score at analyst accuracy 0.70 / 0.80 / 0.90 / 0.95 and report the
LOWEST accuracy at which each claim still holds:

    (a) the band-vs-score gap at 2% capacity stays positive
    (b) the "recall up AND false positives down" dominance stays true

PRE-REGISTERED NOTE ON (b), written before running because it follows from reading cost.py
rather than from any result: `realised_cost` credits fraud_recall for any case that is not
APPROVEd -- a reviewed fraud counts as caught whatever the analyst then decides -- and counts
fpr only over BLOCKed legitimate cases. So the RAW recall/FPR figures are ARITHMETICALLY
INDEPENDENT of the analyst error rate, and claim (b) cannot break no matter what I sweep. That
would be a hollow answer to a fair question, so this block also reports an ANALYST-ADJUSTED
recall and FPR, which credit the analyst only (1 - eps) of the time:

    adj_recall = [blocked frauds + (1-eps) * reviewed frauds] / all frauds
    adj_fpr    = [blocked legits + eps     * reviewed legits] / all legits

Both are printed. The raw pair is what RESULTS section 0 currently reports; the adjusted pair is
the honest stress test of it, and if the adjusted version breaks earlier, that is the number
that belongs in the write-up.

NOTHING IN THIS BLOCK MODIFIES AN EXISTING RESULT. It writes one new file,
results/block13_rejector.json, and touches nothing else in results/.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from dhruva import config, cost, data, features, model, splits
from dhruva.cost import APPROVE, BLOCK, REVIEW
from dhruva.data import AMOUNT, TARGET

CAPS = [0.01, 0.02, 0.05, 0.10]
DECIDE_AT = 0.02          # pre-registered decision capacity
MARGIN_POINTS = 2.0       # pre-registered indifference band, in points of baseline loss
ACCURACIES = [0.70, 0.80, 0.90, 0.95]

# Fixed before the run. Deliberately small: a shallow model that wins is interesting, a tuned
# one that wins tells you only that you tuned it.
GBM_PARAMS = dict(n_estimators=100, num_leaves=8, max_depth=3, learning_rate=0.05,
                  verbosity=-1, n_jobs=-1)

NAME = {"score": "most suspicious first", "amount": "biggest amount first",
        "stake": "most rupees at stake", "band": "nearest the cut (band)",
        "rej_lr": "learned rejector (logreg)", "rej_gbm": "learned rejector (shallow GBM)"}


def seg_levels(df):
    """Fix the one-hot vocabulary ONCE, on the split the rejector trains on.

    Deriving levels separately per split silently produces different column counts -- cal had 12
    and test 11 on the first run -- so the encoder must be fitted, not recomputed. A level that
    appears only in test gets no column and falls through as all-zeros, which is the correct
    behaviour for a category the rejector never saw while training.
    """
    out = {}
    for c in ("ProductCD", "card6"):
        if c in df:
            # str() per element, not .astype(str): under pandas 3.0 a missing value survives
            # .astype(str) as a float nan, and np.unique then compares float to str and raises.
            # Same dtype trap as bug 2 in RESULTS section 7, which nulled 15 columns silently.
            # block12_policies.localise() carries this identical idiom for the same reason.
            out[c] = sorted(np.unique(np.array([str(x) for x in df[c].to_numpy()])))
    return out


def seg_matrix(df, p, amt, levels):
    """Features the gate already has: score, amount, and coarse segment. Nothing else."""
    cols = [np.asarray(p, float), np.asarray(amt, float), np.log1p(np.asarray(amt, float))]
    for c, lvls in levels.items():
        v = np.array([str(x) for x in df[c].to_numpy()])
        for lvl in lvls:
            cols.append((v == lvl).astype(float))
    return np.column_stack(cols)


def escalation_value(p, y, amt, costs):
    """v(x) = what the Bayes decision costs minus what a review costs. Positive = escalate."""
    acts = cost.decide_bayes(p, amt, costs)
    fn, fp = costs.c_fn(amt), costs.c_fp(amt)
    bayes_cost = np.where((acts == APPROVE) & (y == 1), fn,
                          np.where((acts == BLOCK) & (y == 0), fp, 0.0))
    review_cost = costs.review_cost + costs.human_error_rate * np.where(y == 1, fn, fp)
    return bayes_cost - review_cost


def adjusted_recall_fpr(acts, y, eps):
    """Recall/FPR that credit the analyst only (1-eps) of the time. See the docstring."""
    fraud, legit = y == 1, y == 0
    blocked_f = ((acts == BLOCK) & fraud).sum()
    rev_f = ((acts == REVIEW) & fraud).sum()
    blocked_l = ((acts == BLOCK) & legit).sum()
    rev_l = ((acts == REVIEW) & legit).sum()
    return (float((blocked_f + (1 - eps) * rev_f) / max(fraud.sum(), 1)),
            float((blocked_l + eps * rev_l) / max(legit.sum(), 1)))


def verdict(delta_points):
    """The pre-registered decision rule, as code so it cannot be re-read afterwards."""
    if delta_points >= MARGIN_POINTS:
        return ("REJECTOR WINS",
                "The hand-built ranking left money on the table. Report the rejector as the "
                "method -- and report that it needs labels, which band does not.")
    if delta_points <= -MARGIN_POINTS:
        return ("BAND WINS",
                "band is robust: a learned model with the same inputs is WORSE. The simple "
                "rule generalises.")
    return ("TIE -- SIMPLICITY WINS",
            "The one-line band rule is near-optimal. A learned model with a label requirement "
            "cannot separate itself from one line of arithmetic. Ship the arithmetic.")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()
    cfg = config.load(); cfg.check_lock()
    costs = cost.Costs.from_config(cfg)

    sp = splits.chronological(data.load(cfg.data_dir()), cfg)
    enc, X = features.build(sp)
    y_tr = sp.train[TARGET].to_numpy()
    y_cal = sp.cal[TARGET].to_numpy(); amt_cal = sp.cal[AMOUNT].to_numpy(dtype=float)
    y = sp.test[TARGET].to_numpy(); amt = sp.test[AMOUNT].to_numpy(dtype=float)
    n = len(y)

    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    import lightgbm as lgb

    print("=" * 84)
    print("BLOCK 13A  LEARNED REJECTOR vs THE ONE-LINE RULE")
    print("=" * 84)
    print(f"  decision capacity {DECIDE_AT:.0%}, indifference band +/-{MARGIN_POINTS:.0f} points"
          f" of baseline loss -- both pre-registered\n")

    pols = ["score", "amount", "stake", "band", "rej_lr", "rej_gbm"]
    res = {k: {c: [] for c in CAPS} for k in pols}
    b1s = []

    for s in range(args.seeds):
        sc = model.fit(X["train"], y_tr, kind="lgbm", cfg=cfg, seed=cfg.base_seed + s)
        p_cal = sc.predict_proba_fraud(X["cal"])
        p = sc.predict_proba_fraud(X["test"])
        b1 = cost.realised_cost(cost.decide_bayes(p, amt, costs), y, amt, costs)["total"]
        b1s.append(b1)

        # --- train the rejector on CAL only -------------------------------------------------
        v_cal = escalation_value(p_cal, y_cal, amt_cal, costs)
        t_cal = (v_cal > 0).astype(int)
        levels = seg_levels(sp.cal)          # vocabulary fixed on the training split
        F_cal = seg_matrix(sp.cal, p_cal, amt_cal, levels)
        F_test = seg_matrix(sp.test, p, amt, levels)
        assert F_cal.shape[1] == F_test.shape[1], "feature width drifted between splits"

        if t_cal.sum() in (0, len(t_cal)):        # degenerate target -> cannot learn a ranking
            r_lr = r_gbm = np.zeros(n)
        else:
            lr = make_pipeline(StandardScaler(),
                               LogisticRegression(max_iter=2000, random_state=cfg.base_seed + s))
            lr.fit(F_cal, t_cal)
            r_lr = lr.predict_proba(F_test)[:, 1]

            g = lgb.LGBMClassifier(random_state=cfg.base_seed + s, **GBM_PARAMS)
            g.fit(F_cal, t_cal)
            r_gbm = g.predict_proba(F_test)[:, 1]

        stake = np.maximum(p * costs.c_fn(amt), (1 - p) * costs.c_fp(amt))
        orders = {"band": -np.abs(p - costs.bayes_threshold(amt)) * 1e6 + stake / 1e6,
                  "score": p, "amount": amt, "stake": stake,
                  "rej_lr": r_lr, "rej_gbm": r_gbm}
        for pol, o in orders.items():
            rank = np.argsort(-o)
            for c in CAPS:
                a = cost.decide_bayes(p, amt, costs)
                a[rank[:int(round(c * n))]] = REVIEW
                res[pol][c].append(b1 - cost.realised_cost(a, y, amt, costs)["total"])
        print(f"  seed {s+1}/{args.seeds}  (escalate-positive rate in cal: {t_cal.mean():.3%})",
              flush=True)

    b1m = float(np.mean(b1s))
    print(f"\n  baseline, no queue: Rs{b1m:,.0f}\n")
    print(f"{'queue policy':<32}" + "".join(f"{c:>13.0%}" for c in CAPS))
    print("-" * 84)
    for pol in pols:
        print(f"{NAME[pol]:<32}" + "".join(f"{np.mean(res[pol][c]):>+13,.0f}" for c in CAPS))

    band_d = float(np.mean(res["band"][DECIDE_AT]))
    best_rej = max(("rej_lr", "rej_gbm"), key=lambda k: np.mean(res[k][DECIDE_AT]))
    rej_d = float(np.mean(res[best_rej][DECIDE_AT]))
    delta_pts = (rej_d - band_d) / b1m * 100.0
    tag, gloss = verdict(delta_pts)

    print(f"\n  at {DECIDE_AT:.0%} capacity: band {band_d:+,.0f} | best rejector "
          f"({NAME[best_rej]}) {rej_d:+,.0f}")
    print(f"  difference: {rej_d - band_d:+,.0f} = {delta_pts:+.2f} points of baseline loss")
    print(f"\n  PRE-REGISTERED VERDICT: {tag}\n  {gloss}")
    print("\n  Stated regardless of outcome: the rejector needs LABELS to fit and band needs")
    print("  none. Chargeback labels arrive weeks late, so band refits on last week's traffic")
    print("  and the rejector cannot.")

    # ---------------------------------------------------------------- 13B
    print("\n" + "=" * 84)
    print("BLOCK 13B  HOW BAD CAN THE ANALYST BE BEFORE THE CLAIMS BREAK?")
    print("=" * 84)
    sc = model.fit(X["train"], y_tr, kind="lgbm", cfg=cfg, seed=cfg.base_seed)
    p = sc.predict_proba_fraud(X["test"])
    stake = np.maximum(p * costs.c_fn(amt), (1 - p) * costs.c_fp(amt))
    band_o = -np.abs(p - costs.bayes_threshold(amt)) * 1e6 + stake / 1e6

    sweep = []
    print(f"\n{'accuracy':<10}{'band-score @2%':>18}{'raw recall':>13}{'raw FPR':>10}"
          f"{'adj recall':>13}{'adj FPR':>10}")
    print("-" * 84)
    for acc in ACCURACIES:
        eps = 1.0 - acc
        c2 = replace(costs, human_error_rate=eps)
        base = cost.realised_cost(cost.decide_bayes(p, amt, c2), y, amt, c2)
        row = {"accuracy": acc}
        nets = {}
        for pol, o in (("band", band_o), ("score", p)):
            a = cost.decide_bayes(p, amt, c2)
            a[np.argsort(-o)[:int(round(DECIDE_AT * n))]] = REVIEW
            r = cost.realised_cost(a, y, amt, c2)
            nets[pol] = base["total"] - r["total"]
            if pol == "band":
                a10 = cost.decide_bayes(p, amt, c2)
                a10[np.argsort(-o)[:int(round(0.10 * n))]] = REVIEW
                r10 = cost.realised_cost(a10, y, amt, c2)
                ar, af = adjusted_recall_fpr(a10, y, eps)
                row.update(raw_recall=r10["fraud_recall"], raw_fpr=r10["fpr"],
                           adj_recall=ar, adj_fpr=af,
                           base_recall=base["fraud_recall"], base_fpr=base["fpr"])
        row["gap"] = float(nets["band"] - nets["score"])
        row["band_net"] = float(nets["band"]); row["score_net"] = float(nets["score"])
        row["dominates_raw"] = bool(row["raw_recall"] > row["base_recall"]
                                    and row["raw_fpr"] < row["base_fpr"])
        row["dominates_adj"] = bool(row["adj_recall"] > row["base_recall"]
                                    and row["adj_fpr"] < row["base_fpr"])
        sweep.append(row)
        print(f"{acc:<10.0%}{row['gap']:>+18,.0f}{row['raw_recall']:>13.1%}"
              f"{row['raw_fpr']:>10.2%}{row['adj_recall']:>13.1%}{row['adj_fpr']:>10.2%}")

    ok_gap = [r["accuracy"] for r in sweep if r["gap"] > 0]
    ok_adj = [r["accuracy"] for r in sweep if r["dominates_adj"]]
    print(f"\n  (a) band-vs-score gap at {DECIDE_AT:.0%} stays positive down to analyst accuracy "
          f"{min(ok_gap):.0%}" if ok_gap else "\n  (a) gap is negative at every accuracy tested")
    print(f"  (b) recall-up / FPR-down, ANALYST-ADJUSTED, holds down to "
          f"{min(ok_adj):.0%}" if ok_adj else "  (b) adjusted dominance fails at every accuracy")
    print("      raw recall/FPR are independent of analyst accuracy by construction "
          "(realised_cost credits any non-APPROVE), which is why the adjusted pair is the one "
          "to quote under challenge.")

    out = cfg.results_dir() / "block13_rejector.json"
    out.write_text(json.dumps({
        "config_hash": cfg.hash(), "seeds": args.seeds, "caps": CAPS,
        "decide_at": DECIDE_AT, "margin_points": MARGIN_POINTS, "b1_mean": b1m,
        "gbm_params": GBM_PARAMS,
        "policies": {k: {str(c): res[k][c] for c in CAPS} for k in res},
        "band_at_decide": band_d, "best_rejector": best_rej,
        "rejector_at_decide": rej_d, "delta_points": delta_pts,
        "verdict": tag, "verdict_gloss": gloss,
        "analyst_sweep": sweep,
    }, indent=2, default=float), encoding="utf-8")
    print(f"\nwritten results/{out.name}")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
