"""Data loading and the Block 0 identity-coverage audit.

TWO SOURCES, AND THEY MUST NEVER BE CONFUSED

  ieee-cis   the real thing. 590,540 card-not-present transactions over ~6 months, 3.5% fraud.
             Every reported result must come from here.

  dev        a deterministic fixture with the same schema and shape. It exists so the pipeline,
             the tests and the console can be built before the Kaggle download completes.
             It is hand-specified, NOT a learned generative model -- but that distinction does
             not make it safe to report from. It is plumbing only.

Every frame carries `df.attrs["data_source"]`, and every artefact downstream records it. The
console shows a DEV DATA banner whenever it is not "ieee-cis". This is the discipline that keeps
us on the right side of the synthetic-data critique (arXiv:2604.13125).

THE BLOCK 0 AUDIT

IEEE-CIS's identity table does not cover every transaction. That gives us a naturally occurring
sub-population for which the device/identity block is simply absent -- no ablation involved. If
its calibration differs from the identity-present population, the premise behind H1 has support
in real data before we manipulate anything, which is the strongest available answer to "you
invented your test distribution". `identity_coverage` measures it; block0 reports it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

TARGET = "isFraud"
TIME = "TransactionDT"
AMOUNT = "TransactionAmt"
ID = "TransactionID"

# Identity/device columns -- PROTOCOL section 04, block I. The primary ablation target.
IDENTITY_COLS = [f"id_{i:02d}" for i in range(1, 39)] + ["DeviceType", "DeviceInfo"]


# ------------------------------------------------------------------------------------------
# Loading
# ------------------------------------------------------------------------------------------

def load(data_dir: Path, dev: bool = False, seed: int = 20260820) -> pd.DataFrame:
    """Load IEEE-CIS, or the development fixture when `dev` or the files are absent."""
    tx_path = Path(data_dir) / "train_transaction.csv"
    id_path = Path(data_dir) / "train_identity.csv"

    if dev or not tx_path.exists():
        df = _fixture(seed=seed)
        df.attrs["data_source"] = "dev-fixture"
        return df

    tx = pd.read_csv(tx_path)
    ident = pd.read_csv(id_path) if id_path.exists() else pd.DataFrame({ID: []})

    # LEFT join: transactions with no identity record are kept, with the block all-NaN.
    # That is the natural sub-population the audit below is about -- dropping them would
    # discard the single best piece of real-data evidence available to this project.
    df = tx.merge(ident, on=ID, how="left")
    df = df.sort_values(TIME, kind="mergesort").reset_index(drop=True)
    df.attrs["data_source"] = "ieee-cis"
    return df


def is_real(df: pd.DataFrame) -> bool:
    return df.attrs.get("data_source") == "ieee-cis"


# ------------------------------------------------------------------------------------------
# Block 0 audit
# ------------------------------------------------------------------------------------------

@dataclass
class IdentityAudit:
    n_total: int
    n_with_identity: int
    coverage: float
    fraud_rate_with: float
    fraud_rate_without: float
    amount_median_with: float
    amount_median_without: float
    data_source: str

    def __str__(self) -> str:
        lift = (
            self.fraud_rate_without / self.fraud_rate_with
            if self.fraud_rate_with > 0
            else float("nan")
        )
        return "\n".join([
            f"  source                  {self.data_source}",
            f"  transactions            {self.n_total:,}",
            f"  with identity block     {self.n_with_identity:,}  ({self.coverage:.1%})",
            f"  without identity block  {self.n_total - self.n_with_identity:,}  "
            f"({1 - self.coverage:.1%})",
            "",
            f"  fraud rate   WITH identity   {self.fraud_rate_with:.3%}",
            f"  fraud rate   WITHOUT         {self.fraud_rate_without:.3%}   "
            f"({lift:.2f}x)",
            f"  median amount WITH / WITHOUT  {self.amount_median_with:,.2f} / "
            f"{self.amount_median_without:,.2f}",
        ])


def identity_coverage(df: pd.DataFrame) -> IdentityAudit:
    """Measure the naturally occurring identity-absent sub-population.

    A transaction counts as identity-present if ANY block-I column is non-null. In IEEE-CIS the
    identity table is joined wholesale, so presence is effectively all-or-nothing; using `any`
    rather than a threshold keeps that honest if partial records exist.

    NOTE ON INTERPRETATION. A difference in fraud rate between the two groups is NOT by itself
    evidence for H1. H1 is about calibration, and calibration is measured after a model is fitted
    (Block 1 onward). This audit establishes that the sub-population exists, is large enough to
    calibrate on, and differs in composition. Do not overstate it beyond that.
    """
    present_cols = [c for c in IDENTITY_COLS if c in df.columns]
    has_id = (
        df[present_cols].notna().any(axis=1)
        if present_cols
        else pd.Series(False, index=df.index)
    )

    with_id, without_id = df[has_id], df[~has_id]
    return IdentityAudit(
        n_total=len(df),
        n_with_identity=int(has_id.sum()),
        coverage=float(has_id.mean()),
        fraud_rate_with=float(with_id[TARGET].mean()) if len(with_id) else float("nan"),
        fraud_rate_without=float(without_id[TARGET].mean()) if len(without_id) else float("nan"),
        amount_median_with=float(with_id[AMOUNT].median()) if len(with_id) else float("nan"),
        amount_median_without=(
            float(without_id[AMOUNT].median()) if len(without_id) else float("nan")
        ),
        data_source=df.attrs.get("data_source", "unknown"),
    )


def has_identity(df: pd.DataFrame) -> pd.Series:
    """Boolean mask: does this row carry any identity/device signal?"""
    cols = [c for c in IDENTITY_COLS if c in df.columns]
    return df[cols].notna().any(axis=1) if cols else pd.Series(False, index=df.index)


# ------------------------------------------------------------------------------------------
# Development fixture
# ------------------------------------------------------------------------------------------

def _fixture(n: int = 60_000, prevalence: float = 0.035, seed: int = 20260820) -> pd.DataFrame:
    """A deterministic stand-in with IEEE-CIS's schema and structural properties.

    It reproduces the properties the pipeline must handle -- temporal ordering, heavy class
    imbalance, mixed dtypes, missing values, high-cardinality categoricals, partial identity
    coverage, and a mild drift over time -- so that every code path is exercised before the real
    data lands.

    It deliberately does NOT reproduce the behavioural, velocity and multi-account structure of
    real fraud. That is exactly what synthetic generators fail at, and pretending otherwise is
    the trap this project is built to avoid. PLUMBING ONLY.
    """
    rng = np.random.default_rng(seed)

    # ~6 months of transactions, ordered, with a diurnal-ish arrival pattern.
    dt = np.sort(rng.uniform(86_400, 86_400 * 182, size=n)).astype(np.int64)
    t_norm = (dt - dt.min()) / (dt.max() - dt.min())

    # Latent risk with mild drift: the fraud generating process is not stationary.
    latent = rng.normal(0, 1, n) + 0.6 * t_norm
    amount = np.round(np.exp(rng.normal(4.2, 1.1, n)) + 1.0, 2)

    p = 1.0 / (1.0 + np.exp(-(latent * 1.3 + 0.35 * np.log1p(amount) - 5.2)))
    y = (rng.random(n) < p * (prevalence / p.mean())).astype(int)

    df = pd.DataFrame({
        ID: np.arange(1, n + 1),
        TIME: dt,
        AMOUNT: amount,
        TARGET: y,
        "ProductCD": rng.choice(list("WCRHS"), n, p=[.74, .12, .06, .05, .03]),
    })

    # Card / address / distance / email -- high-cardinality categoricals with missingness.
    df["card1"] = rng.integers(1000, 19000, n)
    df["card2"] = _with_missing(rng.integers(100, 600, n).astype(float), rng, 0.02)
    df["card3"] = _with_missing(rng.choice([150.0, 185.0], n, p=[.9, .1]), rng, 0.01)
    df["card4"] = rng.choice(["visa", "mastercard", "amex", "discover"], n, p=[.65, .31, .02, .02])
    df["card5"] = _with_missing(rng.choice([226.0, 224.0, 166.0], n), rng, 0.03)
    df["card6"] = rng.choice(["debit", "credit"], n, p=[.75, .25])
    df["addr1"] = _with_missing(rng.integers(100, 540, n).astype(float), rng, 0.11)
    df["addr2"] = _with_missing(np.full(n, 87.0), rng, 0.11)
    df["dist1"] = _with_missing(rng.exponential(60, n), rng, 0.60)
    df["dist2"] = _with_missing(rng.exponential(200, n), rng, 0.93)
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "anonymous.com"]
    df["P_emaildomain"] = _cat_with_missing(rng.choice(domains, n), rng, 0.16)
    df["R_emaildomain"] = _cat_with_missing(rng.choice(domains, n), rng, 0.77)

    # C: counting/velocity.  D: timedeltas.  M: match flags.  V: engineered.
    #
    # SIGNAL BUDGET. Every block carries only a WEAK relationship to the label, and each is
    # heavily diluted with noise. An earlier version used poisson(1.2 + 2.5*y) for block C,
    # which handed the model the label almost directly: PR-AUC came out at 0.9997 and block C
    # took 64% of the importance. A fixture the model solves perfectly cannot exercise the
    # calibration path at all -- there is nothing left to miscalibrate, and the conformal layer
    # is never stressed. Real fraud detection lands far below that, so the fixture must too.
    # `test_fixture_is_not_trivially_separable` holds this honest.
    noise = lambda scale=1.0: rng.normal(0, scale, n)
    for i in range(1, 15):
        lam = 1.4 + 0.35 * y * (i % 4 == 0) + 0.25 * np.abs(noise())
        df[f"C{i}"] = rng.poisson(np.clip(lam, 0.05, None)).astype(float)
    for i in range(1, 16):
        col = rng.exponential(30, n) * (1.0 + 0.10 * y + 0.3 * np.abs(noise()))
        df[f"D{i}"] = _with_missing(col, rng, 0.25 if i > 5 else 0.05)
    for i in range(1, 10):
        flip = rng.random(n) < (0.30 + 0.10 * y)      # match flags weakly anti-correlate
        df[f"M{i}"] = _cat_with_missing(
            np.where(flip, "F", "T").astype(object), rng, 0.35
        )
    for i in range(1, 51):  # V1..V50 -- a subset; the real set is V1..V339
        eff = 0.18 if i % 5 == 0 else 0.04
        df[f"V{i}"] = _with_missing(rng.normal(y * eff, 1, n), rng, 0.20)

    # Identity block, present for only part of the data -- mirrors IEEE-CIS's join structure.
    # The share is a structural property we must handle, not a number to be relied upon.
    # Identity block, present for only part of the data -- mirrors IEEE-CIS's join structure.
    # It is given a somewhat STRONGER per-feature relationship than the other blocks, because
    # that is what makes it worth ablating: device and behavioural signals are informative in
    # real fraud detection, which is exactly why losing them is expected to hurt. Note this is a
    # property we BUILD INTO the fixture, so no conclusion about H1 may be drawn from it. On
    # IEEE-CIS the block's real contribution is measured, not assumed -- that is Block 1's
    # go/no-go check.
    has_id = rng.random(n) < 0.24
    id_cols = {}
    for i in range(1, 39):
        signal = rng.normal(y * 0.55, 1, n) if i <= 11 else rng.integers(0, 5, n).astype(float)
        id_cols[f"id_{i:02d}"] = np.where(has_id, signal, np.nan)
    id_cols["DeviceType"] = np.where(has_id, rng.choice(["desktop", "mobile"], n), None)
    id_cols["DeviceInfo"] = np.where(
        has_id, rng.choice(["Windows", "iOS", "Android", "MacOS"], n), None
    )
    # Built in one concat rather than 40 inserts -- repeated insertion fragments the frame.
    df = pd.concat([df, pd.DataFrame(id_cols, index=df.index)], axis=1)

    return df.sort_values(TIME, kind="mergesort").reset_index(drop=True)


def _with_missing(a: np.ndarray, rng: np.random.Generator, frac: float) -> np.ndarray:
    a = a.astype(float).copy()
    a[rng.random(a.size) < frac] = np.nan
    return a


def _cat_with_missing(a: np.ndarray, rng: np.random.Generator, frac: float) -> np.ndarray:
    a = a.astype(object).copy()
    a[rng.random(a.size) < frac] = None
    return a
