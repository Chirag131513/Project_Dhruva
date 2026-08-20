"""Property tests for the conformal core -- validation checkpoint V1.

These run on synthetic data in seconds, need no Kaggle download, and answer the question that
decides whether the project has a mechanism at all:

    Does marginal conformal prediction under-cover the minority class,
    and does conditioning the quantile on the class restore it?

If these fail, the implementation is wrong. If they pass, the mechanism the whole project rests
on is real and correctly coded, and everything after this is about measuring it on real data.

Run:  python -m pytest tests/ -v
"""

from __future__ import annotations

import numpy as np
import pytest

from dhruva.conformal import (
    FRAUD,
    LEGIT,
    Calibration,
    aci_update,
    calibrate,
    coverage,
    nonconformity,
    predict_set,
)

ALPHA = 0.10
TARGET = 1.0 - ALPHA


def make_imbalanced(n=40_000, prevalence=0.035, legit_sep=2.2, fraud_sep=0.2,
                    fraud_scale=1.6, seed=0):
    """An imbalanced population that a scorer handles ASYMMETRICALLY.

    The asymmetry is the whole point, and it corrects a tempting misconception: marginal
    conformal prediction does not under-cover the minority class merely because that class is
    rare. Rarity means the majority determines the pooled quantile. Under-coverage bites when the
    minority's nonconformity distribution sits *higher* than the majority's -- i.e. when the model
    is differentially worse on it. Rarity plus differential difficulty is what breaks pooling; if
    you generate both classes with equal separation, pooled CP covers both correctly and there is
    nothing to fix.

    Real fraud data has both properties, which is why the literature reports the failure.

        legit_sep    how confidently the model rejects legitimate rows (high = easy)
        fraud_sep    how confidently it identifies fraud (near 0 = the model is unsure)
        fraud_scale  extra variance on fraud scores (the model is also less consistent)
    """
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < prevalence).astype(int)
    loc = np.where(y == 1, fraud_sep, -legit_sep)
    scale = np.where(y == 1, fraud_scale, 1.0)
    p_fraud = 1.0 / (1.0 + np.exp(-rng.normal(loc=loc, scale=scale)))
    return p_fraud, y


def split_half(*arrays, seed=0):
    n = arrays[0].size
    idx = np.random.default_rng(seed).permutation(n)
    a, b = idx[: n // 2], idx[n // 2 :]
    return [(arr[a], arr[b]) for arr in arrays]


# --------------------------------------------------------------------------------------
# The core claim
# --------------------------------------------------------------------------------------

def test_marginal_conformal_undercovers_the_minority_class():
    """B2: a single pooled quantile hits its target on average while failing the rare class.

    This is the failure the strategy brief cites at 0.5% coverage in the literature. Reproducing
    it here on our own code proves we have implemented the thing that is supposed to be broken,
    which is a precondition for claiming we fixed it.
    """
    p, y = make_imbalanced(seed=1)
    (p_cal, p_test), (y_cal, y_test) = split_half(p, y, seed=1)
    pop_cal = np.full(y_cal.size, "ALL")
    pop_test = np.full(y_test.size, "ALL")

    cal = calibrate(
        nonconformity(p_cal), y_cal, pop_cal, ALPHA,
        class_conditional=False, population_conditional=False,
    )
    sets = predict_set(nonconformity(p_test), pop_test, cal)
    cov = coverage(sets, y_test, pop_test, cal)

    marginal = sets[np.arange(y_test.size), y_test].mean()
    assert marginal == pytest.approx(TARGET, abs=0.02), (
        f"marginal coverage should hold overall, got {marginal:.3f}"
    )

    fraud_cov = cov[("ALL", FRAUD)]
    assert fraud_cov < TARGET - 0.05, (
        f"expected the minority class to be under-covered by pooled CP, got {fraud_cov:.3f}. "
        "If this fails the test population is too easy -- lower `sep`."
    )


def test_class_conditional_restores_minority_coverage():
    """B3/D1: conditioning the quantile on the class restores coverage for BOTH classes.

    This is H3a's mechanism in isolation, with no payments data and no agent model involved.
    """
    p, y = make_imbalanced(seed=2)
    (p_cal, p_test), (y_cal, y_test) = split_half(p, y, seed=2)
    pop_cal = np.full(y_cal.size, "ALL")
    pop_test = np.full(y_test.size, "ALL")

    cal = calibrate(
        nonconformity(p_cal), y_cal, pop_cal, ALPHA,
        class_conditional=True, population_conditional=False,
    )
    sets = predict_set(nonconformity(p_test), pop_test, cal)
    cov = coverage(sets, y_test, pop_test, cal)

    for cls, name in ((LEGIT, "legit"), (FRAUD, "fraud")):
        c = cov[("ALL", cls)]
        assert c == pytest.approx(TARGET, abs=0.04), (
            f"class-conditional coverage for {name} was {c:.3f}, expected ~{TARGET}"
        )


def test_population_conditioning_restores_coverage_under_signal_loss():
    """D1 vs B3: the project's actual contribution, on synthetic data.

    Two sub-populations share a label distribution but not a score distribution -- SHIFTED is
    scored by a degraded model, exactly what signal loss produces. Class-only conditioning pools
    the two score distributions and mis-covers at least one; adding the population to the cell
    key fixes it.
    """
    rng = np.random.default_rng(3)
    n = 60_000
    y = (rng.random(n) < 0.035).astype(int)
    is_shifted = rng.random(n) < 0.4

    # Degraded scoring for the shifted population: weaker separation, more noise.
    sep = np.where(is_shifted, 0.5, 1.6)
    scale = np.where(is_shifted, 1.5, 1.0)
    logit = rng.normal(loc=np.where(y == 1, sep, -sep), scale=scale)
    p = 1.0 / (1.0 + np.exp(-logit))
    pop = np.where(is_shifted, "SHIFTED", "BASE")

    idx = rng.permutation(n)
    c, t = idx[: n // 2], idx[n // 2 :]

    pooled = calibrate(
        nonconformity(p[c]), y[c], pop[c], ALPHA,
        class_conditional=True, population_conditional=False,
    )
    split = calibrate(
        nonconformity(p[c]), y[c], pop[c], ALPHA,
        class_conditional=True, population_conditional=True,
    )

    cov_pooled = coverage(predict_set(nonconformity(p[t]), pop[t], pooled), y[t], pop[t], pooled)
    cov_split = coverage(predict_set(nonconformity(p[t]), pop[t], split), y[t], pop[t], split)

    worst_pooled = min(v for v in cov_pooled.values() if not np.isnan(v))
    assert worst_pooled < TARGET - 0.03, (
        f"expected class-only conditioning to mis-cover some cell, worst was {worst_pooled:.3f}"
    )

    for cell, v in cov_split.items():
        if np.isnan(v):
            continue
        assert v == pytest.approx(TARGET, abs=0.05), (
            f"(population x class) conditioning left cell {cell} at {v:.3f}"
        )


# --------------------------------------------------------------------------------------
# Guards against reporting numbers we should not report
# --------------------------------------------------------------------------------------

def test_thin_cells_are_not_reportable():
    """PROTOCOL section 12 stop rule, enforced in code rather than in the write-up.

    A cell below min_cell_n must come back NaN, so no table or figure can present a coverage
    number derived from a handful of calibration points.
    """
    p, y = make_imbalanced(n=800, prevalence=0.01, seed=4)
    pop = np.full(y.size, "ALL")
    cal = calibrate(nonconformity(p), y, pop, ALPHA, min_cell_n=100)

    assert ("ALL", FRAUD) in cal.thin_cells(), "a ~1% fraud cell in 800 rows must be flagged thin"
    assert not cal.reportable("ALL", FRAUD)
    cov = coverage(predict_set(nonconformity(p), pop, cal), y, pop, cal)
    assert np.isnan(cov[("ALL", FRAUD)]), "thin cells must report NaN, never a number"


def test_empty_calibration_cell_yields_trivial_set_not_a_crash():
    """With no calibration data the honest quantile is +inf: admit everything, cover trivially."""
    cal = Calibration(q={}, n={}, alpha={}, min_cell_n=100)
    sets = predict_set(nonconformity(np.array([0.3, 0.7])), np.array(["X", "X"]), cal)
    assert sets.all(), "an uncalibrated cell must admit every label rather than silently exclude"


def test_coverage_increases_monotonically_as_alpha_falls():
    """Sanity: asking for more coverage must not give you less."""
    p, y = make_imbalanced(seed=5)
    (p_cal, p_test), (y_cal, y_test) = split_half(p, y, seed=5)
    pop_cal, pop_test = np.full(y_cal.size, "ALL"), np.full(y_test.size, "ALL")

    seen = []
    for alpha in (0.30, 0.20, 0.10, 0.05):
        cal = calibrate(nonconformity(p_cal), y_cal, pop_cal, alpha)
        sets = predict_set(nonconformity(p_test), pop_test, cal)
        seen.append(sets[np.arange(y_test.size), y_test].mean())
    assert all(b >= a - 0.01 for a, b in zip(seen, seen[1:])), f"non-monotone coverage: {seen}"


# --------------------------------------------------------------------------------------
# ACI
# --------------------------------------------------------------------------------------

def test_aci_moves_alpha_in_the_correcting_direction():
    """A miss must widen future sets; a hit must tighten them."""
    assert aci_update(0.10, covered=False, gamma=0.01, target_alpha=ALPHA) < 0.10
    assert aci_update(0.10, covered=True, gamma=0.01, target_alpha=ALPHA) > 0.10


def test_aci_alpha_stays_in_bounds_under_pathological_streaks():
    """Unclipped, a long run of one outcome drives alpha somewhere it cannot return from."""
    a = 0.10
    for _ in range(10_000):
        a = aci_update(a, covered=False, gamma=0.05, target_alpha=ALPHA)
    assert 0.001 <= a <= 0.5

    a = 0.10
    for _ in range(10_000):
        a = aci_update(a, covered=True, gamma=0.05, target_alpha=ALPHA)
    assert 0.001 <= a <= 0.5


def test_aci_tracks_target_coverage_under_drift_where_static_fails():
    """H3b's mechanism: a static quantile drifts off target; the ACI-updated one tracks it.

    The score distribution shifts steadily mid-stream. Nothing announces the change -- which is
    the entire point, and the reason a static quantile expires silently.
    """
    rng = np.random.default_rng(6)
    n_cal, n_test = 4_000, 12_000

    cal_scores = rng.normal(0.0, 1.0, n_cal)
    static_q = np.sort(cal_scores)[int(np.ceil((n_cal + 1) * TARGET)) - 1]

    drift = np.linspace(0.0, 2.0, n_test)
    test_scores = rng.normal(drift, 1.0)

    static_hits = test_scores <= static_q

    alpha, adaptive_hits = ALPHA, []
    for s in test_scores:
        q = np.quantile(cal_scores, 1.0 - alpha)
        hit = s <= q
        adaptive_hits.append(hit)
        alpha = aci_update(alpha, covered=bool(hit), gamma=0.02, target_alpha=ALPHA)

    tail = slice(-4_000, None)
    static_tail = static_hits[tail].mean()
    adaptive_tail = np.array(adaptive_hits)[tail].mean()

    assert static_tail < TARGET - 0.10, (
        f"static quantile should have drifted off target, got {static_tail:.3f}"
    )
    assert abs(adaptive_tail - TARGET) < abs(static_tail - TARGET), (
        f"ACI ({adaptive_tail:.3f}) should track {TARGET} better than static ({static_tail:.3f})"
    )


def test_determinism():
    """Same seed, same numbers. Required before any result is worth reporting."""
    a = calibrate(*_fixture(seed=7), ALPHA)
    b = calibrate(*_fixture(seed=7), ALPHA)
    assert a.q == b.q and a.n == b.n


def _fixture(seed):
    p, y = make_imbalanced(n=10_000, seed=seed)
    return nonconformity(p), y, np.full(y.size, "ALL")
