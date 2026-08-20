"""Base scorers.

DELIBERATELY NOT DEEP. Razorpay shipped a transformer foundation model trained on ~3 trillion
data points in August 2026; competing with it on modelling is not a contest we can win, and not
the contest this project entered. Dhruva's contribution is the layer ABOVE the scorer, and its
value is that it is model-agnostic -- which we demonstrate by running the same layer over three
very different base models (PROTOCOL section 08, experiment E7).

LightGBM is the primary because it handles missing values natively. That matters more here than
usual: tau works by MASKING features, and any imputation step would replace the signal loss we
are trying to study with an artefact of the imputer. Native NaN handling means an absent feature
is genuinely absent.

NO RESAMPLING. No SMOTE, no undersampling. Imbalance is handled by the cost model downstream.
Resampling before the split leaks duplicated minority rows across the boundary; resampling after
distorts the very score distribution the conformal layer calibrates against. Skipping it removes
an entire family of bugs and costs nothing we need.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Scorer:
    """Uniform wrapper so every arm calls the same three methods."""

    name: str
    model: object
    feature_names: list[str]

    def predict_proba_fraud(self, X: pd.DataFrame) -> np.ndarray:
        X = X[self.feature_names]
        p = self.model.predict_proba(X)[:, 1]
        return np.clip(p.astype(float), 1e-6, 1 - 1e-6)


def fit(X: pd.DataFrame, y: np.ndarray, kind: str = "lgbm", cfg=None, seed: int = 0) -> Scorer:
    """Fit a base scorer. `kind` in {lgbm, logreg, rf}."""
    y = np.asarray(y).astype(int)
    names = list(X.columns)

    if kind == "lgbm":
        import lightgbm as lgb

        params = dict((cfg.tuning.get("lgbm") if cfg else None) or {})
        params.setdefault("objective", "binary")
        params.setdefault("verbosity", -1)
        params["random_state"] = seed
        params["n_jobs"] = -1
        model = lgb.LGBMClassifier(**params)
        model.fit(X, y)

    elif kind == "logreg":
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        # Linear models cannot take NaN, so this arm must impute. That is a property of the
        # arm, not of the experiment -- and it is precisely why it is a secondary baseline:
        # imputation partially conceals the signal loss tau creates.
        model = make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed),
        )
        model.fit(X, y)

    elif kind == "rf":
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import make_pipeline

        model = make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            RandomForestClassifier(
                n_estimators=300, min_samples_leaf=20, n_jobs=-1,
                class_weight="balanced_subsample", random_state=seed,
            ),
        )
        model.fit(X, y)

    else:
        raise ValueError(f"unknown scorer kind: {kind!r}")

    return Scorer(name=kind, model=model, feature_names=names)


def importance(scorer: Scorer, top: int = 20) -> pd.DataFrame:
    """Feature importances where the model exposes them, annotated with their block.

    Used as a Block 1 sanity check: if block I contributes nothing to the fitted model, tau
    cannot possibly degrade anything, and H1 is dead before the experiment starts. Better to
    discover that here than in the results.
    """
    from .features import block_of

    m = scorer.model
    if hasattr(m, "feature_importances_"):
        vals = m.feature_importances_
    elif hasattr(m, "steps") and hasattr(m.steps[-1][1], "feature_importances_"):
        vals = m.steps[-1][1].feature_importances_
    elif hasattr(m, "steps") and hasattr(m.steps[-1][1], "coef_"):
        vals = np.abs(m.steps[-1][1].coef_.ravel())
    else:
        return pd.DataFrame(columns=["feature", "block", "importance"])

    df = pd.DataFrame({
        "feature": scorer.feature_names,
        "block": [block_of(c) or "?" for c in scorer.feature_names],
        "importance": vals.astype(float),
    })
    return df.sort_values("importance", ascending=False).head(top).reset_index(drop=True)


def block_importance(scorer: Scorer) -> pd.DataFrame:
    """Total importance per feature block, as a share. The Block 1 go/no-go signal."""
    full = importance(scorer, top=10**9)
    if full.empty:
        return full
    g = full.groupby("block")["importance"].sum().sort_values(ascending=False)
    return (g / g.sum()).rename("share").reset_index()
