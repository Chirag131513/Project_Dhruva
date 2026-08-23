"""The integration surface: wrap any fraud scorer in a capacity-aware decision layer.

    from dhruva.gate import Gate

    gate = Gate.fit(scores_cal, labels_cal, amounts_cal, capacity=0.10)
    action = gate.decide(score, amount)          # APPROVE | REVIEW | BLOCK

WHAT THIS IS FOR

Everything else in this package is experiment code. This file is the part someone else would
actually deploy. It takes a probability from a scorer you already run -- gradient boosting, a
neural net, a foundation model, anything that emits P(fraud) -- and turns it into one of three
actions under a review budget you actually staff.

It never trains, never sees features, and never touches your model. It needs three arrays from a
held-out calibration period and nothing else.

WHY IT IS SO SMALL

Because the measurement said so. Block 9 tested four escalation signals; the one that won ranks
by distance to the per-transaction cost-optimal threshold, and beat conformal prediction 22x. The
implementation is a subtraction and a sort. That is not a shortcut -- it is the result.

THE ONE MODELLING ASSUMPTION

Costs are example-dependent, not per-error-type: blocking a large legitimate order is not the
same mistake as blocking a small one. Defaults are declared and must be replaced with your own
before any number here means anything about your business.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

APPROVE, REVIEW, BLOCK = "APPROVE", "REVIEW", "BLOCK"


@dataclass
class Costs:
    """Per-transaction economics. Replace every default with your own figures."""

    chargeback_fee: float = 1500.0     # fee incurred when a missed fraud is disputed
    margin: float = 0.25               # contribution margin lost on a wrongly blocked order
    goodwill: float = 250.0            # friction cost of blocking a good customer
    review_cost: float = 40.0          # analyst time per escalated case
    reviewer_error_rate: float = 0.05  # how often the human also gets it wrong

    def miss(self, amount):
        """Cost of approving fraud: the goods, plus the dispute fee."""
        return np.asarray(amount, dtype=float) + self.chargeback_fee

    def block(self, amount):
        """Cost of declining a good customer: lost margin, plus friction."""
        return self.margin * np.asarray(amount, dtype=float) + self.goodwill

    def threshold(self, amount):
        """The score above which blocking is cheaper than approving, per transaction.

        Falls out of the two costs rather than being tuned: block when
        p * miss > (1 - p) * block, i.e. p > block / (block + miss). On payment data this sits
        near 0.15 and moves with the amount -- the system should be far readier to block a large
        suspicious order than a small one.
        """
        b, m = self.block(amount), self.miss(amount)
        return b / (b + m)


@dataclass
class Gate:
    """A fitted decision layer. Model-agnostic by construction."""

    capacity: float
    cutoff: float
    costs: Costs = field(default_factory=Costs)
    n_calibration: int = 0

    # ---------------------------------------------------------------- fit
    @classmethod
    def fit(cls, scores, amounts, capacity: float = 0.10, costs: Costs | None = None) -> "Gate":
        """Learn the escalation cutoff from a held-out calibration period.

        `scores` are P(fraud) from your model, `amounts` the transaction values. Labels are NOT
        required -- the cutoff is a quantile of an unlabelled ranking, which is why this can be
        refitted on recent traffic without waiting weeks for chargebacks to settle.

        `capacity` is the share of transactions your analysts can actually review. It is an
        operational fact, not a hyperparameter: measure it, do not tune it.
        """
        if not 0.0 <= capacity <= 1.0:
            raise ValueError(f"capacity must be a share in [0, 1], got {capacity}")
        costs = costs or Costs()
        scores = np.asarray(scores, dtype=float)
        amounts = np.asarray(amounts, dtype=float)
        if scores.shape != amounts.shape:
            raise ValueError("scores and amounts must align")

        ambiguity = -np.abs(scores - costs.threshold(amounts))
        # Escalate the most ambiguous `capacity` share; the cutoff is that quantile.
        cutoff = float(np.quantile(ambiguity, 1.0 - capacity)) if capacity > 0 else np.inf
        return cls(capacity=capacity, cutoff=cutoff, costs=costs, n_calibration=scores.size)

    # ---------------------------------------------------------------- decide
    def decide(self, score: float, amount: float) -> str:
        """One transaction in, one action out. No allocation, no lookup, no model call."""
        t = self.costs.threshold(amount)
        if -abs(score - t) >= self.cutoff:
            return REVIEW
        return BLOCK if score > t else APPROVE

    def decide_batch(self, scores, amounts) -> np.ndarray:
        """Vectorised form. Same decisions, one pass."""
        scores = np.asarray(scores, dtype=float)
        amounts = np.asarray(amounts, dtype=float)
        t = self.costs.threshold(amounts)
        act = np.where(scores > t, BLOCK, APPROVE)
        return np.where(-np.abs(scores - t) >= self.cutoff, REVIEW, act)

    # ---------------------------------------------------------------- explain
    def explain(self, score: float, amount: float) -> dict:
        """Why this transaction got this action. Every field is auditable.

        Returned rather than logged so the caller decides what to persist -- but persist it. A
        decision layer that cannot say why it escalated is not reviewable.
        """
        t = float(self.costs.threshold(amount))
        return {
            "action": self.decide(score, amount),
            "score": float(score),
            "amount": float(amount),
            "threshold": t,
            "distance_to_threshold": float(abs(score - t)),
            "escalation_cutoff": float(-self.cutoff),
            "cost_if_missed": float(self.costs.miss(amount)),
            "cost_if_blocked": float(self.costs.block(amount)),
            "capacity": self.capacity,
        }

    # ---------------------------------------------------------------- evaluate
    def evaluate(self, scores, amounts, labels) -> dict:
        """Realised cost on a labelled period, decomposed, against the no-review baseline.

        Run this on your own data before believing any number from our write-up.
        """
        scores = np.asarray(scores, dtype=float)
        amounts = np.asarray(amounts, dtype=float)
        labels = np.asarray(labels).astype(int)
        miss, blk = self.costs.miss(amounts), self.costs.block(amounts)

        def price(act):
            missed = (act == APPROVE) & (labels == 1)
            blocked = (act == BLOCK) & (labels == 0)
            reviewed = act == REVIEW
            human_err = self.costs.reviewer_error_rate * np.where(
                labels[reviewed] == 1, miss[reviewed], blk[reviewed]).sum()
            return {
                "total": float(miss[missed].sum() + blk[blocked].sum()
                               + self.costs.review_cost * reviewed.sum() + human_err),
                "missed_fraud": float(miss[missed].sum()),
                "blocked_legitimate": float(blk[blocked].sum()),
                "review": float(self.costs.review_cost * reviewed.sum() + human_err),
                "review_rate": float(reviewed.mean()),
                "recall": float(((act != APPROVE) & (labels == 1)).sum() / max(labels.sum(), 1)),
                "fpr": float(blocked.sum() / max((labels == 0).sum(), 1)),
            }

        t = self.costs.threshold(amounts)
        baseline = price(np.where(scores > t, BLOCK, APPROVE))
        gated = price(self.decide_batch(scores, amounts))
        return {
            "baseline": baseline, "gated": gated,
            "saved": baseline["total"] - gated["total"],
            "saved_share": (baseline["total"] - gated["total"]) / max(baseline["total"], 1e-9),
        }
