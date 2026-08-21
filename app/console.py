"""Dhruva risk console -- TEST REPLAY.

    streamlit run app/console.py

Reads results/console_data.json and nothing else. It never trains, never scores, and never
touches live data. Everything on screen is precomputed held-out IEEE-CIS, replayed. The header
says TEST REPLAY for that reason: calling it LIVE invites "live from what?", and the honest
answer costs more credibility than the word buys.

THE ONE INTERACTION THAT MATTERS is the alpha_legit slider. Drag it right and watch the
false-positive rate and the cost climb while fraud coverage sits perfectly still. That is the
whole finding in one gesture: the two error budgets are independent, and the pre-registered
alpha = 0.10 spends almost the entire budget on the class that can least afford it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "results" / "console_data.json"
ACTIONS = {0: "APPROVE", 1: "REVIEW", 2: "BLOCK"}

st.set_page_config(page_title="Dhruva — risk console", layout="wide")

CSS = """
<style>
  .stApp { background: #0c1214; }
  html, body, [class*="css"] { font-family: "IBM Plex Sans", -apple-system, sans-serif; }
  .hdr { display:flex; align-items:baseline; gap:16px; border-bottom:1px solid #263438;
         padding-bottom:10px; margin-bottom:6px; }
  .hdr h1 { font-size:1.35rem; margin:0; color:#e7eeef; letter-spacing:-.01em; }
  .hdr .sub { color:#7a8c92; font-size:.78rem; }
  .chip { font-family:"IBM Plex Mono",monospace; font-size:.66rem; letter-spacing:.1em;
          text-transform:uppercase; padding:3px 8px; border-radius:2px; }
  .replay { background:#2a2415; color:#d8ac52; }
  .real   { background:#15281f; color:#79c295; }
  .metric { background:#131b1e; border:1px solid #263438; border-radius:3px;
            padding:12px 14px; }
  .metric .k { font-family:"IBM Plex Mono",monospace; font-size:.6rem; letter-spacing:.11em;
               text-transform:uppercase; color:#7a8c92; margin-bottom:4px; }
  .metric .v { font-size:1.5rem; font-weight:600; color:#e7eeef;
               font-variant-numeric:tabular-nums; line-height:1.1; }
  .metric .d { font-size:.72rem; margin-top:3px; font-variant-numeric:tabular-nums; }
  .up { color:#e28272; } .dn { color:#79c295; } .flat { color:#7a8c92; }
  .note { color:#7a8c92; font-size:.76rem; line-height:1.5; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data
def load():
    if not DATA.exists():
        return None
    return json.loads(DATA.read_text(encoding="utf-8"))


d = load()
if d is None:
    st.error("results/console_data.json not found. Run `python scripts/export_console.py` first.")
    st.stop()

real = d["data_source"] == "ieee-cis"
chip = ('<span class="chip real">TEST REPLAY · IEEE-CIS</span>' if real
        else f'<span class="chip replay">DEV DATA · {d["data_source"]} · NOT REPORTABLE</span>')

st.markdown(
    f'<div class="hdr"><h1>Dhruva</h1>'
    f'<span class="sub">segment-conditional risk gate &nbsp;·&nbsp; '
    f'{d["test_n"]:,} held-out transactions &nbsp;·&nbsp; '
    f'{d["test_fraud"]:,} fraud &nbsp;·&nbsp; α_fraud fixed at {d["alpha_fraud"]}</span>'
    f'{chip}</div>', unsafe_allow_html=True)

grid = pd.DataFrame(d["grid"])
alphas = grid["alpha_legit"].tolist()
derived = d["alpha_derived"]

left, right = st.columns([1, 3.1], gap="large")

with left:
    st.markdown("###### Legitimate-class budget")
    a = st.select_slider(
        "α_legit", options=alphas,
        value=min(alphas, key=lambda v: abs(v - derived)),
        format_func=lambda v: f"{v:.4f}",
        label_visibility="collapsed",
    )
    row = grid[grid["alpha_legit"] == a].iloc[0]

    st.caption(
        f"Promising {1 - a:.1%} coverage on legitimate traffic. "
        f"Capacity-derived value is **{derived:.4f}**; pre-registered was **0.10**."
    )
    st.markdown(
        '<div class="note">α_legit is the share of legitimate transactions the gate is '
        'allowed to miscover. Every one of those gets pushed toward block or review, so this '
        'slider is really the merchant\'s false-positive budget.</div>',
        unsafe_allow_html=True)

    st.markdown("###### Review queue")
    st.caption(f"Capacity {d['capacity']:.0%} of volume · "
               f"{row['truncated']:.0%} of escalations truncated at this α")

    st.divider()
    st.markdown(
        f'<div class="note"><b>Baseline (B1)</b> is a per-transaction cost-optimal Bayes '
        f'threshold: ₹{d["b1"]["total"]:,.0f}, recall {d["b1"]["fraud_recall"]:.1%}, '
        f'FPR {d["b1"]["fpr"]:.2%}. It states no coverage level at all — that is what the '
        f'gate buys.</div>', unsafe_allow_html=True)

with right:
    b1 = d["b1"]
    net = row["net"]
    cols = st.columns(4)
    tiles = [
        ("realised cost", f"₹{row['cost']:,.0f}",
         f"{net:+,.0f} vs baseline", "dn" if net > 0 else "up"),
        ("false-positive rate", f"{row['fpr']:.2%}",
         f"baseline {b1['fpr']:.2%}", "up" if row["fpr"] > b1["fpr"] else "dn"),
        ("fraud recall", f"{row['recall']:.1%}",
         f"baseline {b1['fraud_recall']:.1%}", "dn" if row["recall"] > b1["fraud_recall"] else "up"),
        ("escalated", f"{row['review_rate']:.1%}",
         f"cap {d['capacity']:.0%}", "flat"),
    ]
    for c, (k, v, delta, cls) in zip(cols, tiles):
        c.markdown(f'<div class="metric"><div class="k">{k}</div><div class="v">{v}</div>'
                   f'<div class="d {cls}">{delta}</div></div>', unsafe_allow_html=True)

    st.markdown("")
    g1, g2 = st.columns([1.25, 1], gap="medium")

    with g1:
        st.markdown("###### Cost against the legitimate budget")
        chart = grid[["alpha_legit", "cost"]].copy()
        chart["baseline"] = b1["total"]
        chart = chart.rename(columns={"cost": "conformal gate"}).set_index("alpha_legit")
        st.line_chart(chart, height=250)
        st.caption("The basin is shallow and the right-hand climb is steep: loosening the "
                   "legitimate budget is expensive, tightening it is nearly free.")

    with g2:
        st.markdown("###### Coverage per segment × class")
        cells = row["cells"]
        rows = []
        for key, val in sorted(cells.items()):
            seg, cls = key.split("|")
            n = row["cell_n"].get(key, 0)
            rows.append({
                "segment": seg,
                "class": "fraud" if cls == "1" else "legit",
                "n (cal)": n,
                "coverage": "—" if val is None else f"{val:.3f}",
                "state": "thin" if val is None else
                         ("ok" if abs(val - (1 - (a if cls == "0" else d["alpha_fraud"]))) <= .03
                          else "out"),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, height=250,
                     use_container_width=True)
        st.caption("`thin` = calibration cell below the n≥100 floor; coverage is not reported "
                   "rather than estimated from too few points.")

    st.markdown("###### Where the money goes")
    money = pd.DataFrame([{
        "missed fraud": row["missed_fraud"],
        "blocked legitimate": row["blocked_legit"],
        "review": row["review_cost"],
    }])
    st.bar_chart(money, height=180)

    st.markdown("###### Decision stream")
    acts = d["sample_actions"][str(a)]
    stream = pd.DataFrame({
        "₹ amount": d["sample_amount"],
        "segment": d["sample_segment"],
        "P(fraud)": [round(p, 4) for p in d["sample_p"]],
        "decision": [ACTIONS[x] for x in acts],
        "actual": ["fraud" if y else "legit" for y in d["sample_label"]],
    })
    only = st.checkbox("show escalations only", value=False)
    view = stream[stream["decision"] == "REVIEW"] if only else stream
    st.dataframe(view.head(60), hide_index=True, height=260, use_container_width=True)
    st.caption(f"A 400-row sample of scored held-out transactions, in timestamp order. "
               f"{sum(1 for x in acts if x == 1)} of {len(acts)} escalated at this α.")
