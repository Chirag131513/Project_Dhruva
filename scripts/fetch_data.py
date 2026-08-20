"""Download IEEE-CIS into the configured data directory, then verify it.

    python scripts/fetch_data.py

Requires Kaggle auth to already exist -- run `kaggle auth login` once, in your own terminal.
This script never reads, writes, or transports credentials; it only uses whatever the CLI has
already cached for the current user.

It fetches only train_transaction.csv and train_identity.csv. The competition's test files carry
no public labels, so they are useless here -- our test period comes from splitting `train`
chronologically, which is the correct construction anyway.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dhruva import config

COMPETITION = "ieee-fraud-detection"
WANTED = ["train_transaction.csv", "train_identity.csv"]


def check_auth() -> bool:
    """Probe auth with a cheap authenticated call.

    NOT `kaggle whoami` -- that subcommand does not exist in CLI 2.x and the check would always
    fail. NOT `kaggle auth print-access-token` either: it prints the secret to stdout, and a
    credential should never pass through a script that captures output.

    A competition search needs auth, returns quickly, and reveals nothing sensitive.
    """
    r = subprocess.run(
        [sys.executable, "-m", "kaggle", "competitions", "list", "-s", COMPETITION],
        capture_output=True, text=True,
    )
    if r.returncode == 0 and "Authentication required" not in (r.stdout + r.stderr):
        print("  authenticated          yes")
        return True

    print("  NOT AUTHENTICATED")
    print("  Run this in your own terminal, once:   kaggle auth login")
    print("  (OAuth browser flow -- no token file, nothing to paste)")
    print()
    print("  If ~/.kaggle/kaggle.json exists, it is NOT used by CLI 2.x and can be deleted.")
    print("  That older format also breaks when written by PowerShell's `Out-File -Encoding")
    print("  utf8`, which prepends a BOM the JSON parser rejects.")
    return False


def download(dest: Path) -> bool:
    dest.mkdir(parents=True, exist_ok=True)
    ok = True
    for name in WANTED:
        target = dest / name
        if target.exists():
            print(f"  {name:<26} already present ({target.stat().st_size / 1e6:,.0f} MB)")
            continue

        print(f"  {name:<26} downloading ...", flush=True)
        r = subprocess.run(
            [sys.executable, "-m", "kaggle", "competitions", "download",
             "-c", COMPETITION, "-f", name, "-p", str(dest)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout).strip()
            print(f"    FAILED: {err[:400]}")
            if "403" in err or "Forbidden" in err:
                print("    403 almost always means the competition rules have not been")
                print(f"    accepted: https://www.kaggle.com/c/{COMPETITION}/rules")
            ok = False
            continue

        # Kaggle serves single files zipped when they are large.
        for z in list(dest.glob(f"{name}.zip")) + list(dest.glob(f"{Path(name).stem}.zip")):
            with zipfile.ZipFile(z) as zf:
                zf.extractall(dest)
            z.unlink()
            print(f"    unzipped and removed {z.name}")

        if target.exists():
            print(f"    ok  ({target.stat().st_size / 1e6:,.0f} MB)")
        else:
            print("    downloaded, but the expected CSV is not there -- check the folder")
            ok = False
    return ok


def verify(dest: Path) -> bool:
    """Confirm the files load and carry the columns the pipeline depends on."""
    import pandas as pd

    from dhruva.data import IDENTITY_COLS

    tx, ident = dest / WANTED[0], dest / WANTED[1]
    if not tx.exists():
        print("  train_transaction.csv missing -- nothing to verify")
        return False

    head = pd.read_csv(tx, nrows=5)
    print(f"\n  train_transaction      {head.shape[1]} columns")
    for col in ("TransactionID", "TransactionDT", "TransactionAmt", "isFraud"):
        print(f"    {col:<18} {'present' if col in head.columns else 'MISSING'}")

    if ident.exists():
        ih = pd.read_csv(ident, nrows=5)
        found = [c for c in IDENTITY_COLS if c in ih.columns]
        print(f"  train_identity         {ih.shape[1]} columns, "
              f"{len(found)} of {len(IDENTITY_COLS)} expected block-I columns")
        if len(found) < 10:
            print("    WARNING: block I is the primary ablation target. Too few columns here")
            print("    would make tau meaningless. Check the identity file.")
    else:
        print("  train_identity.csv     MISSING -- E0 and tau both depend on it")
        return False
    return True


def main() -> int:
    cfg = config.load()
    dest = cfg.data_dir()

    print("=" * 78)
    print("FETCH  --  IEEE-CIS Fraud Detection")
    print("=" * 78)
    print(f"\ndestination            {dest}")

    if not check_auth():
        return 1
    print()
    if not download(dest):
        print("\n  one or more files did not arrive -- see the errors above")
        return 1
    if not verify(dest):
        return 1

    print("\n" + "=" * 78)
    print("  Ready. Run the blocks WITHOUT --dev:")
    print("    python scripts/block0_audit.py")
    print("    python scripts/block1_baseline.py")
    print("    python scripts/block2_conformal.py")
    print("    python scripts/block3_shift.py --seeds 3")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
