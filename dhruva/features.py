"""Feature blocks and TRAIN-only encoding.

THE BLOCK PARTITION (PROTOCOL section 04) IS FIXED BEFORE ANY RESULT IS SEEN

    T  transaction core     amount, product, card, address, distance, email domain
    C  counting / velocity  C1-C14
    D  timedeltas           D1-D15          <- partially degraded by tau (timing compression)
    M  match flags          M1-M9
    V  Vesta engineered     V1-V339
    I  identity / device    id_01-id_38, DeviceType, DeviceInfo   <- PRIMARY ablation target

Block I is the target because industry reports that behavioural and device signals degrade or
disappear when an agent transacts on a customer's behalf (Riskified; Stripe's Checkout bot score;
Forter's scripted-mode measurements). Every masking decision traces to one of those.

Block V is NOT ablated even though it plausibly contains behavioural derivatives, because its
provenance is undocumented. Ablating opaque features would make the manipulation unfalsifiable.
The cost of that choice is that some behavioural signal survives tau, so any degradation we
measure is a LOWER BOUND -- which is the conservative direction, and must be stated as such.

ENCODING IS FITTED ON TRAIN ONLY

Categorical levels are mapped from TRAIN-observed values; anything unseen at CAL/TEST maps to a
reserved UNSEEN code. No target encoding, no full-timeline aggregates, no statistics that could
carry information backwards through time. The encoder is an object fitted once and applied, so
there is no code path in which CAL or TEST can influence it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import AMOUNT, ID, TARGET, TIME

UNSEEN = -1
NA_CODE = -2

BLOCK_T = ["ProductCD", "card1", "card2", "card3", "card4", "card5", "card6",
           "addr1", "addr2", "dist1", "dist2", "P_emaildomain", "R_emaildomain", AMOUNT]
BLOCK_C = [f"C{i}" for i in range(1, 15)]
BLOCK_D = [f"D{i}" for i in range(1, 16)]
BLOCK_M = [f"M{i}" for i in range(1, 10)]
BLOCK_V = [f"V{i}" for i in range(1, 340)]
BLOCK_I = [f"id_{i:02d}" for i in range(1, 39)] + ["DeviceType", "DeviceInfo"]

BLOCKS: dict[str, list[str]] = {
    "T": BLOCK_T, "C": BLOCK_C, "D": BLOCK_D, "M": BLOCK_M, "V": BLOCK_V, "I": BLOCK_I,
}

NON_FEATURES = {ID, TARGET, TIME}


def block_of(column: str) -> str | None:
    for name, cols in BLOCKS.items():
        if column in cols:
            return name
    return None


def present_blocks(df: pd.DataFrame) -> dict[str, list[str]]:
    """Block -> the columns of that block actually present in this frame."""
    return {b: [c for c in cols if c in df.columns] for b, cols in BLOCKS.items()}


@dataclass
class Encoder:
    """Label encoding for object columns, fitted on TRAIN and then frozen."""

    maps: dict[str, dict[object, int]] = field(default_factory=dict)
    columns: list[str] = field(default_factory=list)
    categorical: list[str] = field(default_factory=list)

    @staticmethod
    def _is_categorical(s: pd.Series) -> bool:
        """Non-numeric means categorical, however the dtype happens to be spelled.

        Testing `dtype == object` is NOT sufficient. pandas 3.0 gives string columns a dedicated
        `str` dtype, so an object-only check silently misses every string column -- and the
        numeric coercion below then turns them all into NaN. That failure is invisible: the model
        still trains, still scores, and quietly ignores ProductCD, card4, card6, M1-M9, both
        email domains, DeviceType and DeviceInfo. Block M's importance collapsing to exactly
        0.0000 is what exposed it here.

        Asking "is this numeric?" is version-proof in a way that enumerating dtypes is not.
        """
        return not pd.api.types.is_numeric_dtype(s)

    def fit(self, train: pd.DataFrame) -> "Encoder":
        self.columns = [c for c in train.columns if c not in NON_FEATURES]
        self.categorical = [c for c in self.columns if self._is_categorical(train[c])]
        for c in self.categorical:
            levels = pd.Series(train[c].dropna().unique()).tolist()
            self.maps[c] = {v: i for i, v in enumerate(sorted(levels, key=str))}
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply the fitted encoding. Never re-fits, never sees a label."""
        missing = [c for c in self.columns if c not in df.columns]
        if missing:
            raise KeyError(f"{len(missing)} fitted columns absent from frame: {missing[:5]}")

        out = df[self.columns].copy()
        for c in self.categorical:
            m = self.maps[c]
            out[c] = (
                out[c].map(lambda v: NA_CODE if pd.isna(v) else m.get(v, UNSEEN)).astype("int32")
            )
        for c in out.columns:
            if c not in self.categorical:
                out[c] = pd.to_numeric(out[c], errors="coerce").astype("float32")
        return out


def build(splits, ) -> tuple[Encoder, dict[str, pd.DataFrame]]:
    """Fit the encoder on TRAIN, transform all three splits.

    Returns the encoder so downstream code (the tau transform, the console) can round-trip
    column identity without re-deriving the block partition.
    """
    enc = Encoder().fit(splits.train)
    return enc, {
        "train": enc.transform(splits.train),
        "cal": enc.transform(splits.cal),
        "test": enc.transform(splits.test),
    }


def summarise_blocks(df: pd.DataFrame) -> pd.DataFrame:
    """Per-block column count and missingness. Printed by Block 0 as a sanity record."""
    rows = []
    for b, cols in present_blocks(df).items():
        if not cols:
            rows.append({"block": b, "n_cols": 0, "pct_missing": float("nan")})
            continue
        rows.append({
            "block": b,
            "n_cols": len(cols),
            "pct_missing": float(df[cols].isna().to_numpy().mean()),
        })
    unassigned = [c for c in df.columns if c not in NON_FEATURES and block_of(c) is None]
    rows.append({"block": "unassigned", "n_cols": len(unassigned),
                 "pct_missing": float("nan")})
    return pd.DataFrame(rows)
