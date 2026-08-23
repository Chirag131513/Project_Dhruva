"""Generate the primary figure from Block 12.

    python scripts/make_figures.py   ->  results/figures/graph5_triage.png

This is the figure the talk is built on, and the one to fall back to if the dashboard fails.

It draws the QUEUE-POLICY race, not the Block 9 signal race. Block 9 compared four escalation
signals against a baseline that ran no review queue at all -- a baseline no merchant has. Block 12
replaced it with the comparison that matters: four ways of filling a queue every team already
runs, each escalating the same volume. Reading this file against the old one is the clearest
statement of what the reframe changed.

The earlier graphs (1-4) are kept: they still support the mechanism section and the ULB failure,
both of which remain in RESULTS. Only the headline moved, not the supporting evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from dhruva import config

# Mine first so it wins the legend order; the two that go negative are the point of the panel.
STYLE = {
    "band":   ("#0A6570", "-",  "nearest the cost-optimal cut  (this project)"),
    "score":  ("#9C382C", "--", "most suspicious first  (the obvious policy)"),
    "amount": ("#B8860B", "--", "biggest amount first"),
    "stake":  ("#8A9AA0", "--", "most rupees at stake"),
}

SHORT = {"amount": "amount-sort", "score": "score-sort",
         "stake": "stake-sort", "band": "this project"}


def main() -> int:
    cfg = config.load()
    b12 = json.loads((cfg.results_dir() / "block12_policies.json").read_text(encoding="utf-8"))
    caps, b1, adv = b12["caps"], b12["b1_mean"], b12["advantage"]
    mean = lambda s, c: float(np.mean(b12["policies"][s][str(c)]))
    err = lambda s, c: float(np.std(b12["policies"][s][str(c)]))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.6))
    x = np.arange(len(caps))

    # ---- left: the race ------------------------------------------------------------------
    for sig, (col, ls, lab) in STYLE.items():
        ys = [mean(sig, c) for c in caps]
        es = [err(sig, c) for c in caps]
        ax1.errorbar(x, ys, yerr=es, marker="o", ms=5, lw=2.3 if sig == "band" else 1.7,
                     ls=ls, capsize=3, color=col, label=lab,
                     zorder=3 if sig == "band" else 2)
    ax1.axhline(0, color="#444", lw=1.1, ls="--", zorder=1)

    # Shade the region where the standard policies are underwater. This is the finding, so it
    # gets the only fill in the figure.
    ax1.axvspan(-0.25, 1.25, color="#9C382C", alpha=.055, zorder=0)
    # Keep this text INSIDE the axes and clear of the x-axis label: the empty lower-right
    # quadrant is the only place it does not collide with a series or the axis furniture.
    ax1.annotate("at the capacity teams actually staff,\nsorting by score or by rupees at stake\nLOSES money",
                 xy=(0.62, -88_000), xytext=(2.55, -300_000), fontsize=8.3, color="#9C382C",
                 ha="center", va="center",
                 arrowprops=dict(arrowstyle="->", color="#9C382C", lw=1,
                                 connectionstyle="arc3,rad=-0.22"))

    ax1.set_xticks(x); ax1.set_xticklabels([f"{c:.0%}" for c in caps])
    ax1.set_xlim(-0.35, len(caps) - 0.65)
    ax1.set_ylim(bottom=-460_000)
    ax1.set_xlabel("analyst review capacity (share of transactions)")
    ax1.set_ylabel("net benefit vs cost-optimal threshold (Rs)")
    ax1.set_title("Four ways to fill a review queue, same volume escalated", fontsize=10.5)
    ax1.yaxis.set_major_formatter(lambda v, _: f"{v/1e6:.1f}M")
    ax1.legend(fontsize=7.6, loc="upper left"); ax1.grid(alpha=.25)

    # ---- right: advantage over the BEST rival at each capacity ----------------------------
    ys = [adv[str(c)]["share"] * 100 for c in caps]
    cols = ["#0A6570" if v == max(ys) else "#5F8E95" for v in ys]
    bars = ax2.bar(x, ys, color=cols, width=.56)
    for b, v in zip(bars, ys):
        ax2.text(b.get_x() + b.get_width() / 2, v + .16, f"{v:.1f}%",
                 ha="center", fontsize=9.5, weight="bold", color="#0A6570")

    # Which rival is being beaten changes with capacity, so it belongs on the tick, not in the
    # bar -- an in-bar label is unreadable on the 0.9% bar.
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{c:.0%}\nvs {SHORT[adv[str(c)]['rival']]}" for c in caps],
                        fontsize=8.6)
    ax2.set_xlabel("analyst review capacity", labelpad=8)
    ax2.set_ylabel("advantage over the best rival policy (% of loss)")
    ax2.set_title("Peaks at 2% capacity, gone by 10%", fontsize=10.5)
    ax2.set_ylim(0, max(ys) * 1.24)
    ax2.grid(alpha=.25, axis="y")

    fig.suptitle(
        f"Queue composition under capacity - IEEE-CIS held out, {b12['seeds']} seeds, "
        f"baseline loss Rs {b1:,.0f} (no queue)", fontsize=10.5)
    fig.tight_layout()
    out = cfg.results_dir() / "figures" / "graph5_triage.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print(f"written results/figures/{out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
