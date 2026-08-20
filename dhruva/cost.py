"""Instance-dependent cost model and the decision layer (PROTOCOL section 10).

WHY COSTS ARE PER-TRANSACTION, NOT PER-ERROR-TYPE

Blocking a legitimate 40,000 rupee order and blocking a legitimate 200 rupee order are not the
same mistake, and neither are the corresponding misses. Bahnsen et al. formalised fraud as an
EXAMPLE-DEPENDENT cost-sensitive problem for exactly this reason. A single confusion matrix
weighted by two constants cannot express it.

    c_FN(x) = amount + FEE_CB              missed fraud: goods gone, plus the dispute fee
    c_FP(x) = MARGIN * amount + GOODWILL    blocked legit: lost margin, plus friction
    c_REV   = REVIEW_COST                   flat analyst cost per escalation

THE BAYES THRESHOLD IS THEREFORE ALSO PER-TRANSACTION

Block when the expected cost of approving exceeds the expected cost of blocking:

    p * c_FN(x)  >  (1 - p) * c_FP(x)
    p            >  c_FP(x) / (c_FP(x) + c_FN(x))   =:  t(x)

t(x) is not 0.5 and it is not a tuned constant -- it falls out of the two costs, and it moves
with the amount. On this data it ranges from roughly 0.1 for large transactions to above 0.5 for
tiny ones: the system should be far more willing to block a big suspicious order than a small
one. That is arm B1, and it is a genuinely strong baseline, not a strawman.

WHAT REVIEW COSTS

A reviewed case costs analyst time AND carries the analyst's own error rate:

    E[cost | REVIEW] = c_REV + eps_hum * (c_FN if fraud else c_FP)

eps_hum is declared in config, not measured. It is an assumption and is swept in the sensitivity
analysis like every other constant.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

APPROVE, REVIEW, BLOCK = 0, 1, 2
ACTION_NAMES = {APPROVE: "APPROVE", REVIEW: "REVIEW", BLOCK: "BLOCK"}


@dataclass(frozen=True)
class Costs:
    fee_chargeback: float
    margin: float
    goodwill: float
    review_cost: float
    human_error_rate: float

    @classmethod
    def from_config(cls, cfg, scale: dict[str, float] | None = None) -> "Costs":
        f = cfg.frozen
        s = scale or {}
        return cls(
            fee_chargeback=float(f["fee_chargeback"]) * s.get("fee_chargeback", 1.0),
            margin=float(f["margin"]) * s.get("margin", 1.0),
            goodwill=float(f["goodwill"]) * s.get("goodwill", 1.0),
            review_cost=float(f["review_cost"]) * s.get("review_cost", 1.0),
            human_error_rate=float(f["human_error_rate"]),
        )

    def c_fn(self, amount: np.ndarray) -> np.ndarray:
        return np.asarray(amount, dtype=float) + self.fee_chargeback

    def c_fp(self, amount: np.ndarray) -> np.ndarray:
        return self.margin * np.asarray(amount, dtype=float) + self.goodwill

    def bayes_threshold(self, amount: np.ndarray) -> np.ndarray:
        """Per-transaction indifference point between approving and blocking."""
        fp, fn = self.c_fp(amount), self.c_fn(amount)
        return fp / (fp + fn)


def decide_bayes(p: np.ndarray, amount: np.ndarray, costs: Costs) -> np.ndarray:
    """Arm B1: two-way cost-optimal decision. No abstention, no review queue."""
    return np.where(np.asarray(p) > costs.bayes_threshold(amount), BLOCK, APPROVE)


def decide_conformal(
    members: np.ndarray, p: np.ndarray, amount: np.ndarray, costs: Costs
) -> np.ndarray:
    """Three-way decision from a conformal prediction set.

    A singleton set is decisive and acts. A set containing both labels means the evidence does
    not separate them; an empty set means it fits neither. Both are the model declining to
    decide, and both escalate. That abstention is the mechanism -- not a fallback.
    """
    n = members.shape[0]
    both = members[:, 0] & members[:, 1]
    empty = ~members[:, 0] & ~members[:, 1]
    only_fraud = members[:, 1] & ~members[:, 0]

    out = np.full(n, APPROVE)
    out[only_fraud] = BLOCK
    out[both | empty] = REVIEW
    return out


def apply_capacity(
    actions: np.ndarray,
    p: np.ndarray,
    amount: np.ndarray,
    costs: Costs,
    cap_frac: float,
) -> tuple[np.ndarray, float]:
    """Enforce a finite review queue.

    Conformal will escalate whatever it escalates; a merchant with two analysts cannot review
    20% of volume. Cases are ranked by the expected rupees at stake and the queue is filled to
    capacity. Everything truncated falls back to the cost-optimal two-way decision -- the system
    still has to answer, it just answers without a human.

    Returns the adjusted actions and the truncation rate, which is reported rather than hidden:
    it is a real operational cost of promising coverage you cannot staff.
    """
    actions = actions.copy()
    reviewing = np.flatnonzero(actions == REVIEW)
    budget = int(round(cap_frac * actions.size))
    if reviewing.size <= budget:
        return actions, 0.0

    p = np.asarray(p, dtype=float)
    stake = np.maximum(p[reviewing] * costs.c_fn(amount[reviewing]),
                       (1 - p[reviewing]) * costs.c_fp(amount[reviewing]))
    keep = reviewing[np.argsort(-stake)[:budget]]

    truncated = np.setdiff1d(reviewing, keep, assume_unique=False)
    actions[truncated] = decide_bayes(p[truncated], amount[truncated], costs)
    return actions, float(truncated.size / max(reviewing.size, 1))


def realised_cost(
    actions: np.ndarray, y: np.ndarray, amount: np.ndarray, costs: Costs
) -> dict[str, float]:
    """Rupees actually incurred on a scored set, decomposed by where they went.

    The decomposition matters more than the total: Razorpay's own engineering writing names
    false positives as a merchant-trust problem, so an intervention that only reduces missed
    fraud is answering a question they did not ask.
    """
    y = np.asarray(y).astype(int)
    amount = np.asarray(amount, dtype=float)
    fn, fp = costs.c_fn(amount), costs.c_fp(amount)

    missed = (actions == APPROVE) & (y == 1)
    blocked_good = (actions == BLOCK) & (y == 0)
    reviewed = actions == REVIEW

    cost_missed = float(fn[missed].sum())
    cost_blocked = float(fp[blocked_good].sum())
    cost_review = float(costs.review_cost * reviewed.sum())
    # The analyst is not infallible: a fraction of reviewed cases end in the wrong call anyway.
    cost_review_err = float(
        costs.human_error_rate * np.where(y[reviewed] == 1, fn[reviewed], fp[reviewed]).sum()
    )

    total = cost_missed + cost_blocked + cost_review + cost_review_err
    n = actions.size
    return {
        "total": total,
        "per_1000": total / n * 1000.0,
        "missed_fraud": cost_missed,
        "blocked_legit": cost_blocked,
        "review": cost_review + cost_review_err,
        "n_missed": int(missed.sum()),
        "n_blocked_legit": int(blocked_good.sum()),
        "n_reviewed": int(reviewed.sum()),
        "review_rate": float(reviewed.mean()),
        "fraud_recall": float(((actions != APPROVE) & (y == 1)).sum() / max(y.sum(), 1)),
        "fpr": float(blocked_good.sum() / max((y == 0).sum(), 1)),
    }
