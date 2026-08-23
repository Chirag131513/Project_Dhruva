"""The tau transform and the population router (PROTOCOL section 05).

WHAT TAU IS, AND WHAT IT IS NOT

tau(x, lambda) removes human-specific behavioural and device signal from a transaction. It masks
block I with probability lambda and compresses block D's inter-event timing. That is all it does.
Amounts, labels, card and merchant identity, and blocks C/M/V are untouched. No transaction is
created, deleted, or relabelled.

  MAY NOT CLAIM:  "this is what AI-agent payments look like"
  MAY CLAIM:      "tau is a controlled proxy for the progressive loss of human-specific
                   behavioural and device signal that industry reports under agent-initiated
                   transactions. I manipulate signal availability, not agent-ness. The
                   transactions and the fraud labels are real."

The distinction is the difference between an ablation study and a fabrication, and it is the
single most attackable part of this project. Say it before a judge has to ask.

TWO PROPERTIES THAT KEEP THE EXPERIMENT HONEST

1. ASSIGNMENT IS INDEPENDENT OF THE LABEL. Which rows get shifted is drawn without reference to
   isFraud. Correlating the shift with the label would manufacture the result -- the model would
   degrade on shifted rows because they are fraudulent, not because signal was removed.

2. THE ROUTER DOES NOT READ THE ASSIGNMENT FLAG. `route` infers population from what signal is
   actually present, exactly as a deployed router must. It therefore MISROUTES some rows -- a row
   whose identity block was already empty looks shifted whether or not tau touched it. That is a
   real property of the deployment, not a bug, and `routing_report` measures it so it can be
   reported rather than discovered.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import BLOCK_D, BLOCK_I

BASE = "BASE"
SHIFTED = "SHIFTED"


def assign(n: int, rho: float, rng: np.random.Generator) -> np.ndarray:
    """Which rows are designated shifted. Independent of the label, by construction.

    `n` is a row count rather than a frame, so there is no way to condition on isFraud even by
    accident -- the function cannot see it.
    """
    if not 0.0 <= rho <= 1.0:
        raise ValueError(f"rho must be in [0, 1], got {rho}")
    return rng.random(n) < rho


def tau(
    df: pd.DataFrame,
    lam: float,
    shifted: np.ndarray,
    rng: np.random.Generator,
    kappa: float = 0.5,
) -> pd.DataFrame:
    """Apply the signal-degradation transform to the designated rows.

    Masking is per-cell, not per-row: each block-I column is independently dropped with
    probability lambda. At lambda=1 the block is fully absent; at intermediate lambda a row
    retains a random subset, which is the graded degradation the sweep is about.

    Missingness is left as NaN and never imputed. LightGBM handles that natively, so an absent
    feature is genuinely absent rather than replaced by a median that the model can still learn
    from -- imputing here would substitute an artefact of the imputer for the effect I study.
    """
    if not 0.0 <= lam <= 1.0:
        raise ValueError(f"lambda must be in [0, 1], got {lam}")

    out = df.copy()
    shifted = np.asarray(shifted, dtype=bool)
    if shifted.size != len(df):
        raise ValueError("`shifted` must align with the frame")
    if lam == 0.0 or not shifted.any():
        return out

    # 1. mask block I
    id_cols = [c for c in BLOCK_I if c in out.columns]
    for c in id_cols:
        drop = shifted & (rng.random(len(out)) < lam)
        if drop.any():
            out.loc[drop, c] = np.nan

    # 2. compress block D inter-event timing
    d_cols = [c for c in BLOCK_D if c in out.columns]
    if d_cols and kappa:
        factor = 1.0 - lam * kappa
        idx = out.index[shifted]
        out.loc[idx, d_cols] = out.loc[idx, d_cols].astype(float) * factor

    return out


def route(df: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
    """Infer population from observed signal availability alone.

    A row is routed SHIFTED when at least `threshold` of its block-I columns are missing. The
    router never sees the assignment flag, so it is subject to the same ambiguity a production
    router faces: a transaction that simply never carried device data is indistinguishable from
    one whose device data was stripped.

    That ambiguity is not a defect to be engineered away. It is the operating condition, and
    `routing_report` quantifies how often it bites.
    """
    cols = [c for c in BLOCK_I if c in df.columns]
    if not cols:
        return np.full(len(df), BASE)
    missing_frac = df[cols].isna().to_numpy().mean(axis=1)
    return np.where(missing_frac >= threshold, SHIFTED, BASE)


@dataclass
class RoutingReport:
    n: int
    assigned_shifted: int
    routed_shifted: int
    agreement: float
    false_shifted: int   # routed SHIFTED though tau never touched them
    missed_shifted: int  # tau shifted them, but signal remained detectable

    def __str__(self) -> str:
        return "\n".join([
            f"  rows                     {self.n:,}",
            f"  assigned shifted (tau)   {self.assigned_shifted:,}",
            f"  routed shifted (signal)  {self.routed_shifted:,}",
            f"  agreement                {self.agreement:.1%}",
            f"  routed shifted, untouched by tau   {self.false_shifted:,}",
            f"  touched by tau, routed BASE        {self.missed_shifted:,}",
        ])


def routing_report(assigned: np.ndarray, routed: np.ndarray) -> RoutingReport:
    """How closely signal-based routing tracks the ground-truth assignment.

    Reported alongside every result. If agreement is poor, the coverage numbers are attributable
    to a mix of populations rather than to the populations I think I conditioned on -- and a
    reader is entitled to know that before believing the cells.
    """
    assigned = np.asarray(assigned, dtype=bool)
    routed_is_shifted = np.asarray(routed) == SHIFTED
    return RoutingReport(
        n=assigned.size,
        assigned_shifted=int(assigned.sum()),
        routed_shifted=int(routed_is_shifted.sum()),
        agreement=float((assigned == routed_is_shifted).mean()),
        false_shifted=int((~assigned & routed_is_shifted).sum()),
        missed_shifted=int((assigned & ~routed_is_shifted).sum()),
    )


def natural_population(df: pd.DataFrame) -> np.ndarray:
    """Population labels from real missingness, with NO tau applied -- experiment E0.

    This is the naturally occurring identity-absent sub-population. It carries no modelling
    assumption whatsoever, which is what makes it the strongest available answer to the objection
    that the test distribution was invented.
    """
    return route(df)
