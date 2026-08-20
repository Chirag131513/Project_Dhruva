"""Block 0 -- freeze the protocol, load the data, run the identity-coverage audit.

    python scripts/block0_audit.py [--dev]

Two jobs, in this order:

  1. FREEZE. Write results/protocol.lock, hashing the pre-registered constants. Every later
     block refuses to run if a frozen value changed without a recorded amendment.

  2. AUDIT. Measure the naturally occurring identity-absent sub-population (validation
     checkpoint V2). This is real-data evidence about the premise behind H1, obtained before
     any ablation exists -- which is what makes it worth having.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from dhruva import config, data, features


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true", help="use the development fixture")
    args = ap.parse_args()

    cfg = config.load()

    print("=" * 78)
    print("BLOCK 0  --  protocol freeze and identity-coverage audit")
    print("=" * 78)

    # ---- 1. freeze ------------------------------------------------------------------------
    h = cfg.freeze()
    print(f"\nprotocol frozen        hash={h}")
    print(f"  alpha={cfg.alpha}  gamma={cfg.gamma}  delay={cfg.delay_days}d  "
          f"min_cell_n={cfg.min_cell_n}  seeds={cfg.frozen['n_seeds']}")
    if cfg.amendments:
        print(f"  amendments on record: {len(cfg.amendments)}")
    print(f"  lock written to        {config.LOCK_PATH.relative_to(config.REPO_ROOT)}")

    # ---- 2. load --------------------------------------------------------------------------
    df = data.load(cfg.data_dir(), dev=args.dev, seed=cfg.base_seed)
    source = df.attrs["data_source"]

    if source != "ieee-cis":
        print("\n" + "!" * 78)
        print("  DEV FIXTURE IN USE -- plumbing only.")
        print("  No result from this source may be reported. Download IEEE-CIS before")
        print("  producing any number that appears in the submission.")
        print("!" * 78)

    # ---- 3. block structure ----------------------------------------------------------------
    print(f"\nfeature blocks  (PROTOCOL section 04)")
    print(features.summarise_blocks(df).to_string(index=False))

    # ---- 4. the audit ----------------------------------------------------------------------
    audit = data.identity_coverage(df)
    print(f"\nidentity coverage audit  --  validation checkpoint V2")
    print(audit)

    print("\ninterpretation")
    if audit.coverage < 0.02 or audit.coverage > 0.98:
        print("  The identity block is effectively all-or-nothing across the dataset, so there")
        print("  is NO natural signal-absent sub-population to exploit. E0 cannot run; the")
        print("  premise behind H1 must rest on tau and on E1's real temporal drift alone.")
        print("  Say so explicitly in the write-up rather than omitting E0 silently.")
    else:
        n_min = int(cfg.min_cell_n)
        n_fraud_without = int(
            (audit.n_total - audit.n_with_identity) * audit.fraud_rate_without
        )
        print(f"  A natural identity-absent sub-population exists "
              f"({1 - audit.coverage:.1%} of rows).")
        print(f"  Estimated fraud rows in it: ~{n_fraud_without:,} "
              f"(cell floor is {n_min}).")
        if n_fraud_without < n_min:
            print("  WARNING: too few fraud rows to calibrate a cell there. E0 can compare")
            print("  composition but NOT per-cell coverage. PROTOCOL section 12 stop rule.")
        else:
            print("  Large enough to calibrate a per-cell quantile. E0 is viable.")
        print("\n  NOTE: a difference in fraud rate is NOT yet evidence for H1. H1 is about")
        print("  CALIBRATION, which requires a fitted model -- Block 1 onward. This audit")
        print("  establishes only that the sub-population exists and differs in composition.")

    # ---- 5. record --------------------------------------------------------------------------
    out = cfg.results_dir() / "block0_audit.json"
    out.write_text(
        json.dumps(
            {"config_hash": h, "data_source": source,
             "audit": {k: v for k, v in audit.__dict__.items()}},
            indent=2, default=float,
        ),
        encoding="utf-8",
    )
    print(f"\nwritten                {out.relative_to(config.REPO_ROOT)}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
