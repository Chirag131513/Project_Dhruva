"""Split conformal prediction, class-conditional (Mondrian) cells, and the ACI online update.

    from dhruva.conformal import calibrate, predict_set, coverage, aci_update

WHAT THIS PROVIDES, AND WHAT IT DOES NOT

It provides a *coverage* statement: for a cell g and target alpha, the prediction sets contain
the true label for at least (1 - alpha) of cell-g examples, PROVIDED calibration and test data
for that cell are exchangeable.

It does NOT provide guaranteed accuracy, and it does not survive arbitrary distribution shift.
Drift breaks exchangeability, which is precisely why `aci_update` exists. Every docstring and
every printed label in this module says "coverage", never "guarantee" -- see PROTOCOL section 13.

WHY MONDRIAN (per-class quantiles) AND NOT A SINGLE POOLED QUANTILE

A single pooled quantile satisfies coverage *marginally* -- averaged over all examples. With
3.5% fraud, a procedure can hit 90% marginal coverage while covering almost no fraud cases,
because the legitimate class dominates the average. Conditioning the quantile on the class
forces a separate promise per class. This is the same failure as reporting one aggregate number
when the per-bin numbers are what matter.

I extend the cell definition beyond class alone, to (population, class), where population is
derived from signal availability. That extension is the contribution; the Mondrian mechanism
itself is standard and is not claimed as novel.

REFERENCES
  Vovk et al., Algorithmic Learning in a Random World (Mondrian / class-conditional CP)
  Gibbs & Candes, Adaptive Conformal Inference Under Distribution Shift, NeurIPS 2021
      -> the alpha_{t+1} = alpha_t + gamma(alpha - err_t) update implemented in `aci_update`
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Class index convention, used throughout. Kept explicit so no caller has to guess.
LEGIT = 0
FRAUD = 1


def nonconformity(proba_fraud: np.ndarray) -> np.ndarray:
    """Nonconformity scores s(x, y) = 1 - p_hat(y | x), shape (n, 2).

    Larger = the label conforms less well to what the model expected. `proba_fraud` is the
    base scorer's P(fraud | x); I form both columns so callers never re-derive the convention.
    """
    p = np.asarray(proba_fraud, dtype=float).ravel()
    if p.ndim != 1:
        raise ValueError("proba_fraud must be 1-D")
    if np.any((p < 0.0) | (p > 1.0)):
        raise ValueError("proba_fraud must lie in [0, 1]")
    out = np.empty((p.size, 2), dtype=float)
    out[:, LEGIT] = 1.0 - (1.0 - p)   # = p
    out[:, FRAUD] = 1.0 - p
    return out


def _conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """The finite-sample split-conformal quantile.

    Takes the k-th smallest of n scores where k = ceil((n + 1)(1 - alpha)). The (n + 1) is not
    cosmetic: it is what makes coverage hold in finite samples rather than only asymptotically.
    When k > n the calibration set is too small to certify the requested level at all, and the
    honest answer is +inf -- a set containing everything, which trivially covers. Callers must
    check cell counts against `min_cell_n` rather than silently reporting such a cell.
    """
    n = scores.size
    if n == 0:
        return np.inf
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    if k > n:
        return np.inf
    return float(np.sort(scores)[k - 1])


@dataclass(frozen=True)
class Calibration:
    """Fitted per-cell quantiles plus the counts that decide whether they may be reported."""

    q: dict[tuple[str, int], float]
    n: dict[tuple[str, int], int]
    alpha: dict[tuple[str, int], float]
    min_cell_n: int

    def resolve(self, population: str, cls: int) -> tuple[str, int] | None:
        """Which calibration cell actually governs a (population, class) pair.

        The arms in PROTOCOL section 08 differ only in how coarsely they cell up, so a lookup has
        to fall back from the most specific key to the most general: (pop, class) for D1,
        (pop, 0) for a population-only split, ("ALL", class) for B3, ("ALL", 0) for B2. Returns
        None when nothing was calibrated at all.

        Both `predict_set` and `coverage` resolve through here, so a thinness check and the
        quantile it refers to can never disagree about which cell is in play.
        """
        for key in ((str(population), int(cls)), (str(population), 0),
                    ("ALL", int(cls)), ("ALL", 0)):
            if key in self.q:
                return key
        return None

    def reportable(self, population: str, cls: int) -> bool:
        """PROTOCOL section 12 stop rule.

        Asks whether the *governing calibration cell* holds enough points for its quantile to be
        worth reporting -- not whether this evaluation slice is large. Under the marginal arm the
        fraud rows are governed by a well-populated pooled cell, so their coverage is a real
        measurement of a real quantile even though no fraud-specific cell was ever fitted.
        """
        key = self.resolve(population, cls)
        return key is not None and self.n.get(key, 0) >= self.min_cell_n

    def thin_cells(self) -> list[tuple[str, int]]:
        """Fitted cells whose own count falls below the stop rule."""
        return sorted([c for c, n in self.n.items() if n < self.min_cell_n])


def resolve_alpha(alpha: float | dict[int, float], cls: int) -> float:
    """One alpha, or one per class.

    A scalar applies the same miscoverage budget to both classes. That is the conventional
    choice and it is wrong whenever the classes carry different costs AND different prevalence:
    promising 90% coverage of the legitimate class means excluding 10% of legitimate traffic BY
    CONSTRUCTION, and at 96.6% legitimate that is ~9.7% of all volume pushed toward block or
    review -- which no realistic analyst capacity can absorb. See Block 4.

    Passing a dict lets the budget follow the economics instead of convention.
    """
    if isinstance(alpha, dict):
        if cls not in alpha:
            raise KeyError(f"no alpha given for class {cls}; have {sorted(alpha)}")
        return float(alpha[cls])
    return float(alpha)


def calibrate(
    scores: np.ndarray,
    labels: np.ndarray,
    populations: np.ndarray,
    alpha: float | dict[int, float],
    min_cell_n: int = 100,
    class_conditional: bool = True,
    population_conditional: bool = True,
) -> Calibration:
    """Fit conformal quantiles on the calibration split.

    The two `*_conditional` flags select the arm, so every baseline in PROTOCOL section 08 comes
    from this one function rather than from divergent code paths that could differ by accident:

        class=False, population=False -> B2  marginal split conformal
        class=True,  population=False -> B3  static Mondrian, class only
        class=True,  population=True  -> D1  Dhruva, (population x class)

    `scores` is (n, 2) from `nonconformity`. Only the score of each row's TRUE label enters
    calibration -- that is what makes the resulting quantile a statement about the true label.
    """
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels).astype(int).ravel()
    populations = np.asarray(populations).astype(str).ravel()

    if scores.shape != (labels.size, 2):
        raise ValueError(f"scores must be ({labels.size}, 2), got {scores.shape}")
    if populations.size != labels.size:
        raise ValueError("populations and labels must be the same length")

    true_score = scores[np.arange(labels.size), labels]

    pop_keys = populations if population_conditional else np.full(labels.size, "ALL")
    cls_keys = labels if class_conditional else np.zeros(labels.size, dtype=int)

    q: dict[tuple[str, int], float] = {}
    n: dict[tuple[str, int], int] = {}
    a: dict[tuple[str, int], float] = {}
    for pk in np.unique(pop_keys):
        for ck in np.unique(cls_keys):
            mask = (pop_keys == pk) & (cls_keys == ck)
            cell = (str(pk), int(ck))
            # When class-marginal, the cell key is 0 for everything, so a per-class alpha is
            # meaningless -- fall back to the scalar rather than silently applying the legit
            # budget to a pooled cell.
            cell_alpha = (
                resolve_alpha(alpha, int(ck)) if class_conditional
                else (alpha if not isinstance(alpha, dict) else float(np.mean(list(alpha.values()))))
            )
            n[cell] = int(mask.sum())
            a[cell] = float(cell_alpha)
            q[cell] = _conformal_quantile(true_score[mask], cell_alpha)

    return Calibration(q=q, n=n, alpha=a, min_cell_n=min_cell_n)


def _cell_for(pop: np.ndarray, cls: int, cal: Calibration) -> np.ndarray:
    """Per-row quantile of the calibration cell governing the given candidate class.

    Resolution is delegated to Calibration.resolve so this and the stop-rule check cannot drift
    apart. An unresolvable cell yields +inf, which admits the label -- an uncalibrated cell must
    over-include rather than silently exclude.
    """
    lookup = {p: cal.q.get(cal.resolve(p, cls), np.inf) for p in np.unique(pop)}
    return np.array([lookup[p] for p in pop], dtype=float)


def predict_set(scores: np.ndarray, populations: np.ndarray, cal: Calibration) -> np.ndarray:
    """Prediction sets as a boolean (n, 2) membership matrix.

    A candidate label y is admitted when its nonconformity does not exceed the quantile of the
    cell that governs (population, y). Row sums of 1 are decisive; 2 means the evidence does not
    separate the classes and 0 means it fits neither -- both route to human review.
    """
    scores = np.asarray(scores, dtype=float)
    populations = np.asarray(populations).astype(str).ravel()
    members = np.zeros_like(scores, dtype=bool)
    for cls in (LEGIT, FRAUD):
        members[:, cls] = scores[:, cls] <= _cell_for(populations, cls, cal)
    return members


def coverage(
    members: np.ndarray,
    labels: np.ndarray,
    populations: np.ndarray,
    cal: Calibration | None = None,
) -> dict[tuple[str, int], float]:
    """Empirical coverage per (population, class): the fraction of rows whose set held the truth.

    Cells that fail the min_cell_n stop rule are returned as NaN rather than as a number, so a
    downstream table or plot cannot silently present a quantile estimated from too few points.
    """
    labels = np.asarray(labels).astype(int).ravel()
    populations = np.asarray(populations).astype(str).ravel()
    hit = members[np.arange(labels.size), labels]

    out: dict[tuple[str, int], float] = {}
    for p in np.unique(populations):
        for c in (LEGIT, FRAUD):
            mask = (populations == p) & (labels == c)
            cell = (str(p), int(c))
            if mask.sum() == 0:
                out[cell] = float("nan")
            elif cal is not None and not cal.reportable(str(p), int(c)):
                out[cell] = float("nan")
            else:
                out[cell] = float(hit[mask].mean())
    return out


def aci_update(alpha: float, covered: bool, gamma: float, target_alpha: float) -> float:
    """One Adaptive Conformal Inference step (Gibbs & Candes 2021).

        alpha <- alpha + gamma * (target_alpha - err),   err = 1[label not covered]

    NOTE THE UNITS. `target_alpha` is the target *miscoverage* -- 0.10 for 90% coverage -- not
    the target coverage. Passing 0.90 here inverts the controller: a hit would raise alpha by
    0.9*gamma while a miss lowered it by only 0.1*gamma, so alpha ratchets upward, the quantile
    collapses, and coverage converges to roughly 10% instead of 90%. That bug is silent in
    production because the sets still look plausible, which is why
    `test_aci_tracks_target_coverage_under_drift_where_static_fails` exists.

    With the correct units the controller balances: a miss pushes alpha down by 0.9*gamma, which
    raises the quantile and widens future sets; a hit nudges it up by 0.1*gamma and tightens
    them. Its fixed point is the alpha at which misses occur a target_alpha fraction of the time.

    It is a thermostat on observed miscoverage, and it is what holds coverage near target once
    drift has broken the exchangeability a static quantile silently depends on.

    Clipped to [0.001, 0.5]: unclipped, a long streak of either outcome drives alpha somewhere it
    cannot return from.
    """
    err = 0.0 if covered else 1.0
    return float(np.clip(alpha + gamma * (target_alpha - err), 0.001, 0.5))


@dataclass
class OnlineCalibrator:
    """Per-cell ACI wrapper.

    Holds one alpha per cell and refits that cell's quantile whenever its alpha moves. Labels are
    fed in only after the verification-latency window has elapsed -- enforced by the caller, since
    only the caller knows transaction timestamps. `history` records the alpha trajectory so the
    rolling-coverage figure can show adaptation actually happening rather than asserting it.
    """

    cal: Calibration
    gamma: float
    target_alpha: float          # target MISCOVERAGE, e.g. 0.10 for 90% coverage
    cal_scores: dict[tuple[str, int], np.ndarray] = field(default_factory=dict)
    history: list[tuple[tuple[str, int], float]] = field(default_factory=list)

    def observe(self, cell: tuple[str, int], covered: bool) -> None:
        if cell not in self.cal.alpha:
            return
        new_alpha = aci_update(self.cal.alpha[cell], covered, self.gamma, self.target_alpha)
        self.cal.alpha[cell] = new_alpha
        if cell in self.cal_scores:
            self.cal.q[cell] = _conformal_quantile(self.cal_scores[cell], new_alpha)
        self.history.append((cell, new_alpha))
