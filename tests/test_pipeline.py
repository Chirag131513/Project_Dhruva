"""Pipeline integrity tests: encoding, splits, leakage.

These exist because of a bug that nearly shipped. `Encoder` detected categoricals with
`dtype == object`, which misses pandas 3.0's dedicated string dtype; the numeric coercion then
turned every string column into NaN. Nothing raised. The model trained, scored, and silently
ignored ~15 features including all of block M. Only a block-importance of exactly 0.0000 gave it
away.

The lesson generalises: silent feature destruction is invisible in every downstream metric, so
it has to be asserted against directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dhruva import config, data, features, splits
from dhruva.data import TARGET, TIME
from dhruva.features import NA_CODE, UNSEEN, Encoder


@pytest.fixture(scope="module")
def df():
    return data.load(Path("data"), dev=True, seed=7)


@pytest.fixture(scope="module")
def cfg():
    return config.load()


# --------------------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------------------

def test_string_columns_are_detected_as_categorical(df):
    """The regression test for the silent-destruction bug."""
    enc = Encoder().fit(df)
    for col in ["ProductCD", "card4", "card6", "M1", "P_emaildomain", "DeviceType"]:
        if col in df.columns:
            assert col in enc.categorical, (
                f"{col} (dtype {df[col].dtype}) was not detected as categorical. "
                "An object-only dtype check misses pandas 3.0 string columns."
            )


def test_no_feature_is_entirely_null_after_encoding(df):
    """A column that survives encoding as all-NaN has been destroyed, not encoded."""
    enc = Encoder().fit(df)
    out = enc.transform(df)
    dead = [c for c in out.columns if out[c].isna().all()]
    assert not dead, f"{len(dead)} columns are entirely null after encoding: {dead[:10]}"


def test_encoding_is_fitted_on_train_only(df, cfg):
    """Levels appearing only after TRAIN must map to UNSEEN, never gain their own code."""
    sp = splits.chronological(df, cfg)
    enc = Encoder().fit(sp.train)

    probe = sp.test.copy()
    cat = next(c for c in enc.categorical if c in probe.columns)
    probe.loc[probe.index[:5], cat] = "__NEVER_SEEN_IN_TRAINING__"

    out = enc.transform(probe)
    assert (out[cat].iloc[:5] == UNSEEN).all(), "unseen levels must map to the UNSEEN code"


def test_missing_values_are_preserved_not_imputed(df):
    """tau works by masking. An encoder that imputes would replace the signal loss I study."""
    enc = Encoder().fit(df)
    out = enc.transform(df)
    numeric = [c for c in out.columns if c not in enc.categorical]
    assert out[numeric].isna().to_numpy().any(), (
        "numeric NaNs vanished during encoding -- something is imputing"
    )
    cat_with_na = [c for c in enc.categorical if df[c].isna().any()]
    if cat_with_na:
        c = cat_with_na[0]
        assert (out.loc[df[c].isna(), c] == NA_CODE).all(), "categorical NaN must map to NA_CODE"


def test_transform_is_deterministic(df):
    enc = Encoder().fit(df)
    pd.testing.assert_frame_equal(enc.transform(df), enc.transform(df))


# --------------------------------------------------------------------------------------
# Splits and leakage
# --------------------------------------------------------------------------------------

def test_splits_are_ordered_and_disjoint(df, cfg):
    sp = splits.chronological(df, cfg)
    assert sp.train[TIME].max() < sp.cal[TIME].min()
    assert sp.cal[TIME].max() < sp.test[TIME].min()
    assert len(sp.train) and len(sp.cal) and len(sp.test)


def test_delay_window_is_actually_enforced(df, cfg):
    """The gap between TRAIN and CAL must be at least delay_days, and must drop rows."""
    sp = splits.chronological(df, cfg)
    gap_days = (sp.cal[TIME].min() - sp.train[TIME].max()) / splits.SECONDS_PER_DAY
    assert gap_days >= cfg.delay_days, f"gap {gap_days:.2f}d < required {cfg.delay_days}d"
    assert sp.dropped > 0, "no rows dropped -- the delay window is not doing anything"


def test_leakage_assertion_catches_a_deliberate_violation(df, cfg):
    """The guard must actually fire, not merely exist."""
    sp = splits.chronological(df, cfg)
    bad = splits.Splits(
        train=sp.train, cal=sp.train.copy(), test=sp.test,   # cal overlaps train exactly
        delay_seconds=sp.delay_seconds, dropped=sp.dropped,
    )
    with pytest.raises(AssertionError):
        splits.assert_no_leakage(bad)


def test_releasable_at_respects_verification_latency(df, cfg):
    """A label may only be consumed once delay_days have elapsed from its timestamp."""
    sp = splits.chronological(df, cfg)
    now = sp.test[TIME].min() + splits.SECONDS_PER_DAY * (cfg.delay_days + 1)
    ok = splits.releasable_at(sp.test, now, sp.delay_seconds)
    assert ok.any() and not ok.all(), "the filter should be selective, not all-or-nothing"
    assert (sp.test.loc[ok, TIME] + sp.delay_seconds <= now).all()


# --------------------------------------------------------------------------------------
# Fixture sanity
# --------------------------------------------------------------------------------------

def test_fixture_is_labelled_and_never_mistaken_for_real_data(df):
    assert df.attrs["data_source"] == "dev-fixture"
    assert not data.is_real(df)


def test_fixture_has_a_partial_identity_block(df):
    """E0's code path needs a genuinely partial identity population to exercise."""
    cov = data.identity_coverage(df)
    assert 0.05 < cov.coverage < 0.95, f"identity coverage {cov.coverage:.2%} is not partial"


def test_fixture_is_not_trivially_separable(df, cfg):
    """A fixture the model solves perfectly cannot exercise calibration logic at all.

    If PR-AUC approaches 1.0 there is no miscalibration to detect, no useful prediction set, and
    the conformal layer is never stressed. Fraud detection on real data lands far below this.
    """
    from dhruva import model
    sp = splits.chronological(df, cfg)
    enc, X = features.build(sp)
    sc = model.fit(X["train"], sp.train[TARGET].to_numpy(), kind="lgbm", cfg=cfg, seed=0)

    from dhruva.metrics import detection
    pr = detection(sp.test[TARGET].to_numpy(), sc.predict_proba_fraud(X["test"])).pr_auc
    assert pr < 0.90, (
        f"fixture PR-AUC is {pr:.4f} -- too easy to exercise the calibration path. "
        "Some fixture feature is leaking the label almost directly."
    )
