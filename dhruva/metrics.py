"""Evaluation metrics.

WHAT IS DELIBERATELY ABSENT

  accuracy   At 3.5% fraud, predicting "legitimate" for everything scores 96.5%. Accuracy
             measures the base rate, not the model. It is not computed here, so it cannot
             accidentally reach a slide.

  roc_auc    Available via `roc_auc` but never a headline. Under extreme imbalance the false-
             positive axis is dominated by the negative class, so a large absolute change in the
             number of false positives -- which is what a merchant actually feels -- barely moves
             the curve. PR-AUC and Precision@k respond to it. If asked for ROC-AUC, give it and
             explain why it is the wrong instrument.

THE H1 MEASUREMENT

`degradation_ratio` computes R = (relative ECE degradation) / (relative PR-AUC degradation).
H1 predicts R > 1 and rising in lambda: calibration decays faster than discrimination. The ratio
is the point. "One curve looks stable and the other looks bad" is an eyeball judgement, and
eyeballing two curves until one of them supports the hypothesis is the failure mode the whole
pre-registration exists to prevent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


@dataclass
class Detection:
    pr_auc: float
    roc_auc: float
    precision_at_k: float
    recall_at_k: float
    n: int
    n_positive: int

    def as_dict(self) -> dict:
        return asdict(self)


def detection(y: np.ndarray, p: np.ndarray, k_frac: float = 0.02) -> Detection:
    """Discrimination metrics. `k_frac` is the analyst review capacity as a share of volume."""
    y = np.asarray(y).astype(int).ravel()
    p = np.asarray(p, dtype=float).ravel()
    n_pos = int(y.sum())

    if n_pos == 0 or n_pos == y.size:
        return Detection(float("nan"), float("nan"), float("nan"), float("nan"), y.size, n_pos)

    k = max(1, int(round(k_frac * y.size)))
    top = np.argsort(-p)[:k]
    hits = int(y[top].sum())

    return Detection(
        pr_auc=float(average_precision_score(y, p)),
        roc_auc=float(roc_auc_score(y, p)),
        precision_at_k=hits / k,
        recall_at_k=hits / n_pos,
        n=y.size,
        n_positive=n_pos,
    )


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 15) -> float:
    """ECE over equal-MASS bins.

    Equal-mass rather than equal-width: with fraud scores piled up near zero, equal-width bins
    leave most of the range nearly empty and the statistic becomes dominated by a handful of
    points in the tail. Equal-mass keeps every bin's estimate comparably reliable.
    """
    y = np.asarray(y).astype(float).ravel()
    p = np.asarray(p, dtype=float).ravel()
    if y.size == 0:
        return float("nan")

    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    idx = np.digitize(p, edges[1:-1], right=True)

    total = 0.0
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        total += (m.mean()) * abs(p[m].mean() - y[m].mean())
    return float(total)


def calibration(y: np.ndarray, p: np.ndarray, n_bins: int = 15) -> dict:
    y = np.asarray(y).astype(int).ravel()
    p = np.asarray(p, dtype=float).ravel()
    return {
        "ece": expected_calibration_error(y, p, n_bins),
        "brier": float(brier_score_loss(y, p)) if y.size and 0 < y.sum() < y.size else float("nan"),
        "mean_predicted": float(p.mean()) if p.size else float("nan"),
        "observed_rate": float(y.mean()) if y.size else float("nan"),
    }


def reliability_curve(y: np.ndarray, p: np.ndarray, n_bins: int = 15):
    """(mean predicted, observed rate, bin weight) per equal-mass bin, for the console."""
    y = np.asarray(y).astype(float).ravel()
    p = np.asarray(p, dtype=float).ravel()
    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    idx = np.digitize(p, edges[1:-1], right=True)

    pred, obs, w = [], [], []
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        pred.append(float(p[m].mean()))
        obs.append(float(y[m].mean()))
        w.append(float(m.mean()))
    return np.array(pred), np.array(obs), np.array(w)


def degradation_ratio(baseline: dict, shifted: dict) -> float:
    """R = relative ECE degradation / relative PR-AUC degradation.  H1 predicts R > 1.

    Both inputs are dicts carrying "ece" and "pr_auc" at lambda=0 and at the shifted lambda.
    Returns +inf when discrimination is unchanged but calibration is not -- the cleanest possible
    version of the hypothesis -- and NaN when neither moved.
    """
    ece0, ece1 = float(baseline["ece"]), float(shifted["ece"])
    pr0, pr1 = float(baseline["pr_auc"]), float(shifted["pr_auc"])
    if ece0 <= 0 or pr0 <= 0:
        return float("nan")

    rel_ece = (ece1 - ece0) / ece0          # positive = calibration got worse
    rel_pr = (pr0 - pr1) / pr0              # positive = discrimination got worse

    if abs(rel_pr) < 1e-9:
        return float("inf") if rel_ece > 1e-9 else float("nan")
    return float(rel_ece / rel_pr)


def summarise(y: np.ndarray, p: np.ndarray, k_frac: float = 0.02) -> dict:
    """One row of results: detection + calibration together, as the 2026 review asks for."""
    d = detection(y, p, k_frac).as_dict()
    d.update(calibration(y, p))
    return d
