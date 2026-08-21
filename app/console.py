"""Dhruva risk console -- TEST REPLAY.

    streamlit run app/console.py

Reads results/console_data.json and nothing else. Never trains, never scores, never touches live
data. Everything on screen is precomputed held-out IEEE-CIS, replayed. The header says TEST
REPLAY for that reason -- calling it LIVE invites "live from what?", and the honest answer costs
more credibility than the word buys.

THE ONE INTERACTION is the alpha_legit slider. Drag it right: the false-positive rate and the
cost climb hard while fraud coverage sits perfectly still. Two error budgets, independent. The
conventional alpha = 0.10 spends nearly all of it on the class that can least afford it.

The layout is built so that gesture reads from the back of a room: the two coverage bars are the
largest thing on screen, and the fraud bar is the one that does not move.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "results" / "console_data.json"
ACTIONS = {0: "APPROVE", 1: "REVIEW", 2: "BLOCK"}

INK, INK2, INK3 = "#E7EEEF", "#A6B7BC", "#7A8C92"
BG, SURF, RULE = "#0B1113", "#131B1E", "#263438"
TEAL, AMBER, RED, GREEN = "#3FC4BC", "#D8AC52", "#E28272", "#79C295"

st.set_page_config(page_title="Dhruva — risk console", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
  .stApp {{ background:{BG}; }}
  #MainMenu, footer, header {{ visibility:hidden; }}
  .block-container {{ padding-top:1.4rem; padding-bottom:2rem; max-width:1500px; }}
  html, body, [class*="css"] {{ font-family:"IBM Plex Sans",-apple-system,sans-serif; }}

  .hdr {{ display:flex; align-items:center; gap:18px; border-bottom:1px solid {RULE};
          padding-bottom:12px; margin-bottom:18px; flex-wrap:wrap; }}
  .hdr .mark {{ font-size:1.5rem; font-weight:600; color:{INK}; letter-spacing:-.02em; }}
  .hdr .sub {{ color:{INK3}; font-size:.76rem; flex:1; min-width:200px; }}
  .chip {{ font-family:"IBM Plex Mono",monospace; font-size:.62rem; letter-spacing:.11em;
           text-transform:uppercase; padding:4px 9px; border-radius:2px; white-space:nowrap; }}
  .real {{ background:#15281f; color:{GREEN}; }}
  .devd {{ background:#2A2415; color:{AMBER}; }}

  .tile {{ background:{SURF}; border:1px solid {RULE}; border-radius:4px; padding:13px 15px;
           height:100%; }}
  .tile .k {{ font-family:"IBM Plex Mono",monospace; font-size:.58rem; letter-spacing:.12em;
              text-transform:uppercase; color:{INK3}; margin-bottom:5px; }}
  .tile .v {{ font-size:1.72rem; font-weight:600; color:{INK}; line-height:1;
              font-variant-numeric:tabular-nums; letter-spacing:-.02em; }}
  .tile .d {{ font-size:.7rem; margin-top:5px; font-variant-numeric:tabular-nums; }}
  .up {{ color:{RED}; }} .dn {{ color:{GREEN}; }} .flat {{ color:{INK3}; }}

  .panel {{ background:{SURF}; border:1px solid {RULE}; border-radius:4px; padding:15px 18px; }}
  .plabel {{ font-family:"IBM Plex Mono",monospace; font-size:.6rem; letter-spacing:.12em;
             text-transform:uppercase; color:{INK3}; margin-bottom:11px; }}
  .note {{ color:{INK3}; font-size:.73rem; line-height:1.5; }}
  .big {{ font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums;
          font-size:2.6rem; font-weight:600; line-height:1; letter-spacing:-.03em; }}

  .stSlider [data-baseweb="slider"] {{ padding-top:4px; }}
  div[data-testid="stMetricValue"] {{ font-variant-numeric:tabular-nums; }}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load():
    return json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else None


d = load()
if d is None:
    st.error("results/console_data.json not found — run `python scripts/export_console.py` first.")
    st.stop()

real = d["data_source"] == "ieee-cis"
chip = (f'<span class="chip real">TEST REPLAY · IEEE-CIS</span>' if real else
        f'<span class="chip devd">DEV DATA · {d["data_source"]} · NOT REPORTABLE</span>')

st.markdown(
    f'<div class="hdr"><span class="mark">Dhruva</span>'
    f'<span class="sub">segment-conditional risk gate &nbsp;·&nbsp; {d["test_n"]:,} held-out '
    f'transactions &nbsp;·&nbsp; {d["test_fraud"]:,} fraud &nbsp;·&nbsp; '
    f'₹{d["test_volume"]/1e6:.1f}M volume &nbsp;·&nbsp; α_fraud pinned at {d["alpha_fraud"]}'
    f'</span>{chip}</div>', unsafe_allow_html=True)

grid = pd.DataFrame(d["grid"])
alphas = grid["alpha_legit"].tolist()
derived = d["alpha_derived"]
b1 = d["b1"]

# ---------------------------------------------------------------- control
c1, c2 = st.columns([3.4, 1], gap="large")
with c1:
    a = st.select_slider(
        "α_legit — miscoverage budget on legitimate traffic",
        options=alphas, value=min(alphas, key=lambda v: abs(v - derived)),
        format_func=lambda v: f"{v:.4f}",
    )
with c2:
    st.markdown(
        f'<div class="note" style="padding-top:26px">Method uses <b style="color:{TEAL}">'
        f'{derived:.5f}</b> &nbsp;·&nbsp; convention was <b style="color:{RED}">0.10</b></div>',
        unsafe_allow_html=True)

row = grid[grid["alpha_legit"] == a].iloc[0]
cells = row["cells"]
legit_cov = [v for k, v in cells.items() if k.endswith("|0") and v is not None]
fraud_cov = [v for k, v in cells.items() if k.endswith("|1") and v is not None]
mean_legit = sum(legit_cov) / len(legit_cov) if legit_cov else float("nan")
mean_fraud = sum(fraud_cov) / len(fraud_cov) if fraud_cov else float("nan")
net = row["net"]

# ---------------------------------------------------------------- tiles
tiles = [
    ("realised cost", f"₹{row['cost']/1e6:.3f}M", f"{net:+,.0f} vs baseline",
     "dn" if net > 0 else "up"),
    ("false-positive rate", f"{row['fpr']:.2%}", f"baseline {b1['fpr']:.2%}",
     "up" if row["fpr"] > b1["fpr"] else "dn"),
    ("fraud recall", f"{row['recall']:.1%}", f"baseline {b1['fraud_recall']:.1%}",
     "dn" if row["recall"] > b1["fraud_recall"] else "up"),
    ("escalated", f"{row['review_rate']:.1%}", f"capacity {d['capacity']:.0%}", "flat"),
    ("truncated", f"{row['truncated']:.0%}", "fell back to threshold", "flat"),
]
for col, (k, v, delta, cls) in zip(st.columns(5, gap="small"), tiles):
    col.markdown(f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div>'
                 f'<div class="d {cls}">{delta}</div></div>', unsafe_allow_html=True)

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------- the moment
left, right = st.columns([1.05, 1], gap="large")

with left:
    st.markdown('<div class="panel"><div class="plabel">Coverage — the two budgets</div>',
                unsafe_allow_html=True)

    fig = go.Figure()
    for name, val, colour in (("legitimate", mean_legit, TEAL), ("fraud", mean_fraud, AMBER)):
        fig.add_trace(go.Bar(
            y=[name], x=[val], orientation="h", marker_color=colour, width=.52,
            text=[f"  {val:.3f}"], textposition="outside",
            textfont=dict(size=26, color=INK, family="IBM Plex Mono"),
            hovertemplate=f"{name}: %{{x:.3f}}<extra></extra>",
        ))
    fig.add_vline(x=.90, line=dict(color=INK3, dash="dash", width=1.5))
    fig.add_annotation(x=.90, y=1.62, text="target 0.90", showarrow=False,
                       font=dict(size=11, color=INK3, family="IBM Plex Mono"))
    fig.update_layout(
        height=230, margin=dict(l=0, r=70, t=22, b=8), showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 1.06], showgrid=True, gridcolor=RULE, zeroline=False,
                   tickfont=dict(color=INK3, size=11), tickformat=".1f"),
        yaxis=dict(tickfont=dict(color=INK2, size=15)),
        bargap=.42,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        f'<div class="note">Drag α. The <b style="color:{TEAL}">legitimate</b> bar moves. The '
        f'<b style="color:{AMBER}">fraud</b> bar does not — its budget is pinned separately at '
        f'α_fraud = {d["alpha_fraud"]}. That independence is the finding.</div></div>',
        unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel"><div class="plabel">Cost against the legitimate budget</div>',
                unsafe_allow_html=True)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=grid["alpha_legit"], y=grid["cost"], mode="lines+markers",
        line=dict(color=TEAL, width=2.5), marker=dict(size=6, color=TEAL),
        fill="tozeroy", fillcolor="rgba(63,196,188,.09)", name="gate",
        hovertemplate="α=%{x:.4f}<br>₹%{y:,.0f}<extra></extra>"))
    fig2.add_trace(go.Scatter(
        x=[a], y=[row["cost"]], mode="markers",
        marker=dict(size=15, color=AMBER, line=dict(color=BG, width=2)),
        name="now", hoverinfo="skip"))
    fig2.add_hline(y=b1["total"], line=dict(color=RED, dash="dash", width=1.5))
    fig2.add_annotation(x=grid["alpha_legit"].max(), y=b1["total"], text="plain threshold",
                        showarrow=False, yshift=13, xanchor="right",
                        font=dict(size=10.5, color=RED, family="IBM Plex Mono"))
    fig2.add_vline(x=derived, line=dict(color=INK3, dash="dot", width=1))
    fig2.update_layout(
        height=230, margin=dict(l=0, r=8, t=22, b=8), showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(type="log", showgrid=True, gridcolor=RULE, zeroline=False,
                   tickfont=dict(color=INK3, size=10.5), title=None),
        yaxis=dict(showgrid=True, gridcolor=RULE, zeroline=False,
                   tickfont=dict(color=INK3, size=10.5), tickformat=".2s"))
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        '<div class="note">Shallow to the left, steep to the right: tightening the legitimate '
        'budget is nearly free, loosening it is not. Dotted line is the capacity derivation.'
        '</div></div>', unsafe_allow_html=True)

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------- lower row
lo, mid, hi = st.columns([1.1, 1, 1.25], gap="large")

with lo:
    st.markdown('<div class="panel"><div class="plabel">Where the money goes</div>',
                unsafe_allow_html=True)
    parts = [("missed fraud", row["missed_fraud"], RED),
             ("blocked legitimate", row["blocked_legit"], AMBER),
             ("review", row["review_cost"], TEAL)]
    fig3 = go.Figure()
    for name, val, colour in parts:
        fig3.add_trace(go.Bar(x=[val], y=["cost"], orientation="h", name=name,
                              marker_color=colour, width=.4,
                              hovertemplate=f"{name}: ₹%{{x:,.0f}}<extra></extra>"))
    fig3.update_layout(barmode="stack", height=118,
                       margin=dict(l=0, r=6, t=4, b=26),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       legend=dict(orientation="h", y=-.55, font=dict(color=INK3, size=10.5)),
                       xaxis=dict(showgrid=True, gridcolor=RULE, zeroline=False,
                                  tickfont=dict(color=INK3, size=10), tickformat=".2s"),
                       yaxis=dict(showticklabels=False))
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
    st.markdown('<div class="note">Blocked-legitimate is what kills the conventional setting — '
                'not missed fraud.</div></div>', unsafe_allow_html=True)

with mid:
    st.markdown('<div class="panel"><div class="plabel">Coverage per segment</div>',
                unsafe_allow_html=True)
    rows = []
    for key in sorted(cells):
        seg, cls = key.split("|")
        val = cells[key]
        n = row["cell_n"].get(key, 0)
        tgt = 1 - (a if cls == "0" else d["alpha_fraud"])
        rows.append({
            "seg": seg, "class": "fraud" if cls == "1" else "legit",
            "n": n,
            "coverage": "thin" if val is None else f"{val:.3f}",
            "": "—" if val is None else ("●" if abs(val - tgt) <= .03 else "▲"),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, height=196,
                 use_container_width=True)
    st.markdown('<div class="note">● in band · ▲ out of band · thin = calibration cell below '
                'n≥100, not reported.</div></div>', unsafe_allow_html=True)

with hi:
    st.markdown('<div class="panel"><div class="plabel">Decision stream</div>',
                unsafe_allow_html=True)
    acts = d["sample_actions"][str(a)]
    stream = pd.DataFrame({
        "₹": [f"{v:,.0f}" for v in d["sample_amount"]],
        "seg": d["sample_segment"],
        "P(fraud)": [f"{p:.3f}" for p in d["sample_p"]],
        "decision": [ACTIONS[x] for x in acts],
        "actual": ["fraud" if y else "legit" for y in d["sample_label"]],
    })
    only = st.checkbox("escalations only", value=False)
    view = stream[stream["decision"] == "REVIEW"] if only else stream
    st.dataframe(view.head(40), hide_index=True, height=196, use_container_width=True)
    n_rev = sum(1 for x in acts if x == 1)
    st.markdown(f'<div class="note">400-row sample of scored held-out transactions in timestamp '
                f'order · {n_rev} escalated at this α.</div></div>', unsafe_allow_html=True)
