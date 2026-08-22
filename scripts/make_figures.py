"""Generate the primary figure from Block 9.

    python scripts/make_figures.py   ->  results/figures/graph5_triage.png

This is the figure the talk is built on, and the one to fall back to if the dashboard fails.
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

STYLE = {
    "band": ("#0A6570", "distance to threshold"),
    "disagree": ("#B8860B", "ensemble disagreement"),
    "conformal": ("#9C382C", "conformal sets"),
    "random": ("#8A9AA0", "random"),
}


def main() -> int:
    cfg = config.load()
    b9 = json.loads((cfg.results_dir() / "block9_triage.json").read_text(encoding="utf-8"))
    caps, b1 = b9["caps"], b9["b1_mean"]
    mean = lambda s, c: float(np.mean(b9["net"][s][str(c)]))
    err = lambda s, c: float(np.std(b9["net"][s][str(c)]))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.6))

    # ---- left: how each signal scales with capacity -------------------------------------
    x = np.arange(len(caps))
    for sig, (col, lab) in STYLE.items():
        ys = [mean(sig, c) for c in caps]
        es = [err(sig, c) for c in caps]
        ax1.errorbar(x, ys, yerr=es, marker="o", ms=5, lw=2.1, capsize=3,
                     color=col, label=f"{sig} — {lab}")
    ax1.axhline(0, color="#444", lw=1.1, ls="--")
    ax1.set_xticks(x); ax1.set_xticklabels([f"{c:.0%}" for c in caps])
    ax1.set_xlabel("analyst review capacity (share of transactions)")
    ax1.set_ylabel("net benefit vs cost-optimal threshold (₹)")
    ax1.set_title("Which cases to escalate, and what it is worth", fontsize=10.5)
    ax1.yaxis.set_major_formatter(lambda v, _: f"{v/1e6:.1f}M")
    ax1.legend(fontsize=8, loc="upper left"); ax1.grid(alpha=.25)
    # Annotate INSIDE the axes: placing it below the random line pushed the text onto the
    # x-axis label and the two overlapped.
    ax1.annotate("random escalation\nLOSES money", xy=(2.9, mean("random", caps[-1])),
                 xytext=(1.1, mean("random", caps[-1]) * 0.62), fontsize=8.5, color="#5F7178",
                 ha="center", va="center",
                 arrowprops=dict(arrowstyle="->", color="#8A9AA0", lw=1,
                                 connectionstyle="arc3,rad=-0.15"))

    # ---- right: share of merchant loss removed -------------------------------------------
    ys = [mean("band", c) / b1 * 100 for c in caps]
    bars = ax2.bar(x, ys, color="#0A6570", width=.56)
    for b, v in zip(bars, ys):
        ax2.text(b.get_x() + b.get_width() / 2, v + .55, f"{v:.1f}%",
                 ha="center", fontsize=9.5, weight="bold", color="#0A6570")
    conf = [mean("conformal", c) / b1 * 100 for c in caps]
    ax2.plot(x, conf, "o--", color="#9C382C", lw=1.7, ms=4.5, label="conformal, for contrast")
    ax2.set_xticks(x); ax2.set_xticklabels([f"{c:.0%}" for c in caps])
    ax2.set_xlabel("analyst review capacity")
    ax2.set_ylabel("share of merchant loss removed (%)")
    ax2.set_title("Band: 28.4% of loss removed at 10% capacity", fontsize=10.5)
    ax2.legend(fontsize=8); ax2.grid(alpha=.25, axis="y")

    fig.suptitle(
        f"Escalation under capacity — IEEE-CIS held out, {b9['seeds']} seeds, "
        f"baseline loss ₹{b1:,.0f}", fontsize=10.5)
    fig.tight_layout()
    out = cfg.results_dir() / "figures" / "graph5_triage.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print(f"written results/figures/{out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
