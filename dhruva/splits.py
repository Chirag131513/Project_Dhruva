"""Chronological train / delay / calibration / test splits.

WHY NOT A RANDOM SPLIT

Payment fraud labels arrive late. A transaction is confirmed fraudulent when the customer
disputes it -- days or weeks after it settled. A random split therefore trains on the future to
predict the past, and produces a number that is both excellent and meaningless. Dal Pozzolo et
al. (TNNLS 2017) formalised this; the Fraud Detection Handbook (Ch. 5) gives the protocol I
follow here.

THE DELAY WINDOW IS NOT DECORATION

Between TRAIN and CAL sits a gap of `delay_days` whose rows are DISCARDED entirely. Without it,
the most recent training rows carry labels that, at the moment of the decision they are supposed
to inform, would not yet have existed. The gap is what makes the evaluation answerable to the
question "could this system actually have known that at the time?"

    |------- TRAIN -------|-- DELAY --|--- CAL ---|------- TEST -------|
        fit base scorer      dropped    fit CP        evaluate once
                                        quantiles

TEST is read once, at the end. The only thing permitted to consume a TEST label before then is
the ACI update, and only for rows whose timestamp is older than the delay window -- which is the
verification-latency simulation, enforced by `releasable_at` rather than by good intentions.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .data import TIME

SECONDS_PER_DAY = 86_400


@dataclass(frozen=True)
class Splits:
    train: pd.DataFrame
    cal: pd.DataFrame
    test: pd.DataFrame
    delay_seconds: int
    dropped: int

    def __str__(self) -> str:
        def span(d: pd.DataFrame) -> str:
            if not len(d):
                return "empty"
            lo, hi = d[TIME].min(), d[TIME].max()
            return f"day {lo / SECONDS_PER_DAY:6.1f} -> {hi / SECONDS_PER_DAY:6.1f}"

        return "\n".join([
            f"  TRAIN  {len(self.train):>8,}  {span(self.train)}   "
            f"fraud {self.train['isFraud'].mean():.3%}",
            f"  DELAY  {self.dropped:>8,}  (dropped -- labels unavailable at decision time)",
            f"  CAL    {len(self.cal):>8,}  {span(self.cal)}   "
            f"fraud {self.cal['isFraud'].mean():.3%}",
            f"  TEST   {len(self.test):>8,}  {span(self.test)}   "
            f"fraud {self.test['isFraud'].mean():.3%}",
        ])


def chronological(df: pd.DataFrame, cfg) -> Splits:
    """Split by time. Fractions are of the *time span*, not of the row count.

    Splitting on row count would place the boundary wherever transaction volume happened to be
    dense, which makes the delay window a different number of days in every run and the splits
    incomparable across datasets. Splitting on the timeline keeps `delay_days` meaning days.
    """
    df = df.sort_values(TIME, kind="mergesort").reset_index(drop=True)
    t0, t1 = df[TIME].min(), df[TIME].max()
    span = t1 - t0

    f = cfg.frozen
    delay = int(cfg.delay_days) * SECONDS_PER_DAY

    train_end = t0 + span * float(f["train_frac"])
    cal_start = train_end + delay
    cal_end = cal_start + span * float(f["cal_frac"])

    train = df[df[TIME] <= train_end]
    cal = df[(df[TIME] > cal_start) & (df[TIME] <= cal_end)]
    test = df[df[TIME] > cal_end]
    dropped = int(((df[TIME] > train_end) & (df[TIME] <= cal_start)).sum())

    splits = Splits(
        train=train.reset_index(drop=True),
        cal=cal.reset_index(drop=True),
        test=test.reset_index(drop=True),
        delay_seconds=delay,
        dropped=dropped,
    )
    assert_no_leakage(splits)
    return splits


def assert_no_leakage(s: Splits) -> None:
    """Structural guarantees. Cheap to check, catastrophic to get wrong silently."""
    if not len(s.train) or not len(s.cal) or not len(s.test):
        raise ValueError(
            f"empty split (train={len(s.train)}, cal={len(s.cal)}, test={len(s.test)}). "
            "The time span is probably too short for the configured delay window."
        )

    train_end, cal_start = s.train[TIME].max(), s.cal[TIME].min()
    if cal_start <= train_end:
        raise AssertionError(f"CAL starts at {cal_start} but TRAIN ends at {train_end}")

    gap = cal_start - train_end
    if gap < s.delay_seconds:
        raise AssertionError(
            f"delay gap is {gap / SECONDS_PER_DAY:.2f}d, "
            f"below the required {s.delay_seconds / SECONDS_PER_DAY:.2f}d"
        )

    if s.test[TIME].min() <= s.cal[TIME].max():
        raise AssertionError("TEST overlaps CAL in time")

    for name, a, b in (("train/cal", s.train, s.cal), ("cal/test", s.cal, s.test),
                       ("train/test", s.train, s.test)):
        shared = set(a["TransactionID"]) & set(b["TransactionID"])
        if shared:
            raise AssertionError(f"{name} share {len(shared)} TransactionIDs")


def releasable_at(df: pd.DataFrame, now: float, delay_seconds: int) -> pd.Series:
    """Which TEST labels a system at time `now` would legitimately already know.

    The ACI update consumes labels through this filter and no other path. It is the difference
    between simulating verification latency and merely describing it.
    """
    return df[TIME] + delay_seconds <= now
