"""Block 1 -- chronological split, base scorer, honest detection metrics.

    python scripts/block1_baseline.py [--dev] [--kind lgbm|logreg|rf]

At the end of this block a valid submission exists: a fraud model evaluated on a temporally
held-out period with a delay window, reported with PR-AUC and Precision@k rather than accuracy.
Everything after this adds results; nothing after this is needed for the submission to be real.

THE GO/NO-GO CHECK AT THE END

If block I (identity/device) contributes essentially nothing to the fitted model, then masking it
cannot degrade anything, and H1 is dead before the experiment begins. Better to learn that here,
in one run, than after building the whole apparatus around it. The block-importance table is
printed for exactly that reason.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from dhruva import config, data, features, metrics, model, splits
from dhruva.data import TARGET


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--kind", default="lgbm", choices=["lgbm", "logreg", "rf"])
    args = ap.parse_args()

    cfg = config.load()
    cfg.check_lock()

    print("=" * 78)
    print(f"BLOCK 1  --  baseline scorer ({args.kind})")
    print("=" * 78)

    df = data.load(cfg.data_dir(), dev=args.dev, seed=cfg.base_seed)
    source = df.attrs["data_source"]
    if source != "ieee-cis":
        print("\n  [DEV FIXTURE -- not reportable]")

    # ---- split ------------------------------------------------------------------------------
    sp = splits.chronological(df, cfg)
    print(f"\nchronological split  (delay = {cfg.delay_days}d, rows in the gap are dropped)")
    print(sp)

    # ---- features ---------------------------------------------------------------------------
    enc, X = features.build(sp)
    print(f"\nfeatures               {len(enc.columns)} columns "
          f"({len(enc.categorical)} categorical, encoded on TRAIN only)")

    y_train = sp.train[TARGET].to_numpy()
    y_cal = sp.cal[TARGET].to_numpy()
    y_test = sp.test[TARGET].to_numpy()

    # ---- fit --------------------------------------------------------------------------------
    print(f"\nfitting {args.kind} on {len(X['train']):,} rows ...")
    scorer = model.fit(X["train"], y_train, kind=args.kind, cfg=cfg, seed=cfg.base_seed)

    p_cal = scorer.predict_proba_fraud(X["cal"])
    p_test = scorer.predict_proba_fraud(X["test"])

    # ---- evaluate ---------------------------------------------------------------------------
    k_frac = float(cfg.frozen["review_cap_headline"])
    res_cal = metrics.summarise(y_cal, p_cal, k_frac)
    res_test = metrics.summarise(y_test, p_test, k_frac)

    print(f"\nheld-out performance   (Precision@k at k = {k_frac:.0%} review capacity)")
    print(f"{'':22}{'CAL':>12}{'TEST':>12}")
    print("-" * 78)
    for key, label in [
        ("pr_auc", "PR-AUC"),
        ("precision_at_k", f"Precision@{k_frac:.0%}"),
        ("recall_at_k", f"Recall@{k_frac:.0%}"),
        ("ece", "ECE"),
        ("brier", "Brier"),
        ("roc_auc", "ROC-AUC (not a headline)"),
    ]:
        print(f"  {label:<20}{res_cal[key]:>12.4f}{res_test[key]:>12.4f}")
    n_cal, n_test = f"{res_cal['n']:,}", f"{res_test['n']:,}"
    pos_cal, pos_test = f"{res_cal['n_positive']:,}", f"{res_test['n_positive']:,}"
    print(f"  {'rows':<20}{n_cal:>12}{n_test:>12}")
    print(f"  {'fraud rows':<20}{pos_cal:>12}{pos_test:>12}")

    base_rate = float(y_test.mean())
    print(f"\n  base rate on TEST      {base_rate:.4f}")
    print(f"  PR-AUC lift over base  {res_test['pr_auc'] / base_rate:.1f}x")
    print("  (accuracy is not computed -- at this base rate it would read "
          f"{1 - base_rate:.1%} for a model that predicts 'legitimate' every time)")

    # ---- go / no-go -------------------------------------------------------------------------
    print("\nblock importance  --  GO/NO-GO for H1")
    bi = model.block_importance(scorer)
    if bi.empty:
        print("  (this scorer exposes no importances)")
    else:
        print(bi.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
        share_i = float(bi.loc[bi["block"] == "I", "share"].sum()) if "I" in set(bi["block"]) else 0.0
        print(f"\n  block I (identity/device) share: {share_i:.2%}")
        if share_i < 0.01:
            print("  STOP AND THINK. The model barely uses block I, so masking it cannot")
            print("  meaningfully degrade anything and H1 has no room to be true. Either the")
            print("  identity block is too sparse to matter on this data, or the block")
            print("  partition needs revisiting BEFORE tau is built. Do not proceed to Block 3")
            print("  assuming the effect will appear.")
        else:
            print("  Block I carries real weight. tau has something to remove; H1 is testable.")

    # ---- record -----------------------------------------------------------------------------
    out = cfg.results_dir() / f"block1_{args.kind}.json"
    out.write_text(json.dumps({
        "config_hash": cfg.hash(),
        "data_source": source,
        "scorer": args.kind,
        "split": {"train": len(sp.train), "cal": len(sp.cal),
                  "test": len(sp.test), "dropped_to_delay": sp.dropped},
        "cal": res_cal,
        "test": res_test,
        "block_importance": bi.to_dict(orient="records") if not bi.empty else [],
    }, indent=2, default=float), encoding="utf-8")

    np.save(cfg.results_dir() / f"p_test_{args.kind}.npy", p_test)
    np.save(cfg.results_dir() / f"p_cal_{args.kind}.npy", p_cal)

    print(f"\nwritten                {out.relative_to(config.REPO_ROOT)}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
