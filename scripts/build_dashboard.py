"""Build the standalone dashboard.

    python scripts/build_dashboard.py     ->  app/dashboard.html

One self-contained HTML file, data inlined. No server, no framework, no network access.

WHAT IT IS FOR. Not a results viewer -- an integration surface. Someone evaluating this needs to
answer two questions in ninety seconds: *what does it do to my losses*, and *how do I put it in
front of my model*. So the page leads with the pipeline position, carries a capacity control, and
ends with the actual three-line API, the measured per-decision latency, and a real audit record.

THE DEMO GESTURE is the capacity slider: drag it and the four escalation signals separate, band
pulling away while conformal stalls and random goes negative. Escalation pays, the choice of
cases is the entire value, and the fashionable method is not the one that wins.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dhruva import config

TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Risk Gate — decision layer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{
  --bg:#080C15;--panel:#0F1626;--panel2:#161F33;--panel3:#1D2942;
  --rule:#1C2740;--rule2:#2A3A5C;
  --ink:#EAF0FA;--ink2:#93A6C4;--ink3:#5E7290;
  --brand:#2E7BF6;--brand2:#5B9BFF;--brand-dim:#16345F;
  --good:#34D399;--warn:#FBBF24;--bad:#F87171;--mute:#4A5B78;
  --mono:"IBM Plex Mono",ui-monospace,monospace;--sans:"IBM Plex Sans",-apple-system,sans-serif;
}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;
  -webkit-font-smoothing:antialiased;overflow-x:hidden;
  background-image:radial-gradient(1100px 520px at 76% -12%,rgba(46,123,246,.10),transparent 62%)}
.wrap{max-width:1580px;margin:0 auto;padding:18px 26px 44px;display:flex;flex-direction:column;gap:13px}

/* ---------- topbar ---------- */
.top{display:flex;align-items:center;gap:18px;flex-wrap:wrap;border-bottom:1px solid var(--rule);padding-bottom:13px}
.brand{display:flex;align-items:center;gap:10px;font-size:1.16rem;font-weight:600;letter-spacing:-.02em}
.dot{width:9px;height:9px;border-radius:50%;background:var(--brand);box-shadow:0 0 0 4px rgba(46,123,246,.16)}
.meta{display:flex;gap:20px;flex-wrap:wrap;flex:1;font-size:.72rem;color:var(--ink3)}
.meta b{color:var(--ink2);font-weight:500;font-family:var(--mono)}
.chip{font-family:var(--mono);font-size:.58rem;letter-spacing:.13em;text-transform:uppercase;
  padding:5px 10px;border-radius:3px;background:#0E2A1F;color:var(--good);white-space:nowrap;
  border:1px solid rgba(52,211,153,.22)}
.chip.dev{background:#2A2312;color:var(--warn);border-color:rgba(251,191,36,.25)}

/* ---------- pipeline ---------- */
.pipe{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:15px 20px;
  display:flex;align-items:center;gap:11px;flex-wrap:wrap}
.node{padding:9px 15px;border-radius:5px;border:1px solid var(--rule2);background:var(--panel2);
  font-size:.79rem;color:var(--ink2);white-space:nowrap}
.node i{font-style:normal;display:block;font-family:var(--mono);font-size:.55rem;
  letter-spacing:.1em;text-transform:uppercase;color:var(--ink3);margin-top:3px}
/* Greek mu survives text-transform:uppercase as a capital Mu, which reads as a Latin M.
   Same trap as alpha. Exempt the element that carries a unit rather than dropping the
   uppercase treatment from every caption. */
#pipeLat{text-transform:none;letter-spacing:.06em}
.node.us{border-color:var(--brand);background:linear-gradient(180deg,rgba(46,123,246,.17),rgba(46,123,246,.05));
  color:var(--ink);font-weight:600;box-shadow:0 0 0 3px rgba(46,123,246,.10)}
.node.us i{color:var(--brand2)}
.arrow{color:var(--ink3);font-size:1rem}
.outs{display:flex;gap:7px;flex-wrap:wrap}
.out{padding:7px 12px;border-radius:4px;font-family:var(--mono);font-size:.63rem;letter-spacing:.09em;font-weight:600}
.o-a{background:#0E2A1F;color:var(--good)}.o-r{background:#2A2312;color:var(--warn)}.o-b{background:#2C1618;color:var(--bad)}
.pipe .tag{margin-left:auto;font-size:.71rem;color:var(--ink3);max-width:340px;line-height:1.5}

/* ---------- control ---------- */
.ctl{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:15px 20px;
  display:grid;grid-template-columns:1fr 280px;gap:24px;align-items:center}
@media(max-width:900px){.ctl{grid-template-columns:1fr}}
.lab{font-family:var(--mono);font-size:.58rem;letter-spacing:.13em;text-transform:uppercase;color:var(--ink3);margin-bottom:8px}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:24px;background:transparent;cursor:pointer;display:block}
input[type=range]::-webkit-slider-runnable-track{height:5px;border-radius:3px;
  background:linear-gradient(90deg,var(--brand) 0%,var(--brand) var(--pct,0%),var(--rule2) var(--pct,0%),var(--rule2) 100%)}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;
  background:#fff;border:4px solid var(--bg);margin-top:-6.5px;box-shadow:0 0 0 1.5px var(--brand),0 2px 9px rgba(0,0,0,.6)}
input[type=range]::-moz-range-track{height:5px;border-radius:3px;background:var(--rule2)}
input[type=range]::-moz-range-thumb{width:18px;height:18px;border-radius:50%;background:#fff;border:4px solid var(--bg)}
input[type=range]:focus-visible{outline:2px solid var(--brand);outline-offset:5px;border-radius:4px}
.ticks{display:flex;justify-content:space-between;font-family:var(--mono);font-size:.6rem;color:var(--ink3);margin-top:2px}
.now{font-family:var(--mono);font-size:2rem;font-weight:600;letter-spacing:-.03em;line-height:1}
.nnote{font-size:.71rem;color:var(--ink3);line-height:1.5;margin-top:6px}

/* ---------- tiles ---------- */
.tiles{display:grid;grid-template-columns:repeat(6,1fr);gap:11px}
@media(max-width:1250px){.tiles{grid-template-columns:repeat(3,1fr)}}
@media(max-width:700px){.tiles{grid-template-columns:repeat(2,1fr)}}
.tile{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:12px 14px}
.tile .k{font-family:var(--mono);font-size:.55rem;letter-spacing:.13em;text-transform:uppercase;color:var(--ink3);margin-bottom:6px}
.tile .v{font-family:var(--mono);font-size:1.42rem;font-weight:600;letter-spacing:-.03em;line-height:1}
.tile .d{font-family:var(--mono);font-size:.63rem;margin-top:5px;color:var(--ink3)}
.tile.hero{border-color:rgba(52,211,153,.3);background:linear-gradient(180deg,rgba(52,211,153,.09),transparent)}

/* ---------- panels ---------- */
.grid{display:grid;grid-template-columns:1.06fr 1fr;gap:13px}
@media(max-width:1150px){.grid{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:15px 19px}
.ptitle{font-family:var(--mono);font-size:.58rem;letter-spacing:.13em;text-transform:uppercase;color:var(--ink3);
  margin-bottom:15px;display:flex;justify-content:space-between;align-items:center;gap:12px}
.ptitle span{letter-spacing:.05em;text-transform:none;font-size:.64rem;color:var(--ink3)}
.note{font-size:.71rem;color:var(--ink3);line-height:1.55;margin-top:13px}.note b{color:var(--ink2)}

/* ---------- race ---------- */
.race{display:flex;flex-direction:column;gap:13px}
.rrow{display:grid;grid-template-columns:128px 1fr 118px;gap:12px;align-items:center}
.rname{font-size:.8rem;color:var(--ink2)}
.rname i{font-style:normal;display:block;font-family:var(--mono);font-size:.55rem;color:var(--ink3);margin-top:2px}
.rtrack{position:relative;height:22px;background:var(--panel2);border-radius:3px}
.rzero{position:absolute;top:-4px;bottom:-4px;width:1.5px;background:var(--ink3);opacity:.65}
.rfill{position:absolute;top:0;bottom:0;border-radius:2px;
  transition:left .45s cubic-bezier(.22,1,.36,1),width .45s cubic-bezier(.22,1,.36,1)}
.rval{font-family:var(--mono);font-size:1rem;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
svg{display:block;width:100%;overflow:visible}
.ax{font-family:var(--mono);font-size:9.5px;fill:var(--ink3)}.gl{stroke:var(--rule);stroke-width:1}

/* ---------- integration ---------- */
.grid3{display:grid;grid-template-columns:1.15fr 1fr;gap:13px}
@media(max-width:1150px){.grid3{grid-template-columns:1fr}}
pre.code{font-family:var(--mono);font-size:12.1px;line-height:1.62;background:#070B13;
  border:1px solid var(--rule);border-radius:5px;padding:14px 16px;overflow-x:auto;margin:0;color:var(--ink2)}
pre.code b{color:var(--brand2);font-weight:600}
pre.code em{font-style:normal;color:var(--ink3)}
pre.code u{text-decoration:none;color:var(--good)}
.kv{display:grid;grid-template-columns:1fr auto;gap:5px 14px;font-family:var(--mono);font-size:.72rem;margin-top:12px}
.kv div:nth-child(odd){color:var(--ink3)}
.kv div:nth-child(even){color:var(--ink);font-variant-numeric:tabular-nums;text-align:right}
table{border-collapse:collapse;width:100%;font-size:.74rem}
th{font-family:var(--mono);font-size:.53rem;letter-spacing:.11em;text-transform:uppercase;color:var(--ink3);
  text-align:left;font-weight:600;padding:6px 8px;border-bottom:1px solid var(--rule2)}
td{padding:5px 8px;border-bottom:1px solid var(--rule);color:var(--ink2)}
td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right}
.scroll{max-height:206px;overflow-y:auto}
.scroll::-webkit-scrollbar{width:7px}.scroll::-webkit-scrollbar-thumb{background:var(--rule2);border-radius:4px}
.act{font-family:var(--mono);font-size:.6rem;letter-spacing:.06em;padding:2px 6px;border-radius:3px}
.APPROVE{background:#0E2A1F;color:var(--good)}.REVIEW{background:#2A2312;color:var(--warn)}.BLOCK{background:#2C1618;color:var(--bad)}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body><div class="wrap">

<div class="top">
  <div class="brand"><span class="dot"></span>Risk Gate</div>
  <div class="meta">
    <div>held out <b id="mN"></b></div><div>fraud <b id="mF"></b></div>
    <div>volume <b id="mV"></b></div><div>baseline loss <b id="mB"></b></div>
    <div>seeds <b id="mS"></b></div>
  </div>
  <div class="chip" id="chip"></div>
</div>

<div class="pipe">
  <div class="node">your scorer<i>unchanged</i></div>
  <div class="arrow">→</div>
  <div class="node">P(fraud), amount<i>the only inputs</i></div>
  <div class="arrow">→</div>
  <div class="node us">RISK GATE<i id="pipeLat">— per decision</i></div>
  <div class="arrow">→</div>
  <div class="outs">
    <div class="out o-a">APPROVE</div><div class="out o-r">REVIEW</div><div class="out o-b">BLOCK</div>
  </div>
  <div class="tag">Sits between the model you already run and the decision you already make.
    No retraining, no features, no model call.</div>
</div>

<div class="ctl">
  <div><div class="lab">Analyst review capacity — the share of transactions a human can actually see</div>
    <input type="range" id="sl" min="0" max="3" step="1" value="3">
    <div class="ticks" id="ticks"></div></div>
  <div><div class="lab">capacity</div><div class="now" id="cNow"></div>
    <div class="nnote">An operational fact, not a hyperparameter. Measure it; don't tune it.</div></div>
</div>

<div class="tiles" id="tiles"></div>

<div class="grid">
  <div class="panel">
    <div class="ptitle">Which cases to escalate <span id="raceSub"></span></div>
    <div class="race" id="race"></div>
    <div class="note">Escalation volume is <b>identical across all four</b> — only the choice of
      cases differs. Random escalation <b>loses money</b>, so the value is not in reviewing more.
      It is in reviewing the right ones.</div>
  </div>
  <div class="panel">
    <div class="ptitle">Net benefit vs the threshold <span>by capacity</span></div>
    <svg id="curve" viewBox="0 0 560 250" style="height:250px"></svg>
    <div class="note"><b>Band</b> scales cleanly. <b>Conformal</b> peaks at 5% and falls — it runs
      out of genuinely ambiguous cases and pads the queue.</div>
  </div>
</div>

<div class="grid3">
  <div class="panel">
    <div class="ptitle">Integration <span>three lines, no retraining</span></div>
    <pre class="code" id="code"></pre>
    <div class="kv" id="perf"></div>
    <div class="note">Labels are <b>not</b> needed to fit — the cutoff is a quantile of an
      unlabelled ranking, so it refits on recent traffic without waiting weeks for chargebacks.</div>
  </div>
  <div class="panel">
    <div class="ptitle">Audit record <span>every decision, explainable</span></div>
    <pre class="code" id="audit"></pre>
    <div class="note">Returned by <b>gate.explain()</b> rather than logged, so the caller decides
      what to persist. A decision layer that cannot say why it escalated is not reviewable.</div>
  </div>
</div>

<div class="grid3">
  <div class="panel"><div class="ptitle">Where the money goes</div>
    <svg id="money" viewBox="0 0 400 112" style="height:112px"></svg></div>
  <div class="panel"><div class="ptitle">Decision stream <span id="revN"></span></div>
    <div class="scroll"><table id="stream"></table></div></div>
</div>
</div>

<script>
const D=__DATA__,G_=__GATE__,$=i=>document.getElementById(i);
const inr=v=>(v<0?"-":"")+"₹"+Math.round(Math.abs(v)).toLocaleString("en-IN");
const G=D.grid,CAPS=D.caps,N=G.length;
const SIG=[["band","distance to threshold","#2E7BF6"],["disagree","ensemble disagreement","#FBBF24"],
           ["conformal","conformal sets","#F87171"],["random","random escalation","#4A5B78"]];
$("mN").textContent=D.test_n.toLocaleString("en-IN");
$("mF").textContent=D.test_fraud.toLocaleString("en-IN");
$("mV").textContent="₹"+(D.test_volume/1e6).toFixed(1)+"M";
$("mB").textContent=inr(D.b1.total);$("mS").textContent=D.seeds;
const real=D.data_source==="ieee-cis";
$("chip").textContent=real?"TEST REPLAY · HELD-OUT DATA":"DEV DATA · NOT REPORTABLE";
if(!real)$("chip").classList.add("dev");
$("ticks").innerHTML=CAPS.map(c=>`<span>${(c*100).toFixed(0)}%</span>`).join("");
$("sl").max=N-1;
$("pipeLat").textContent=`${G_.p50_us.toFixed(1)} µs p50 · ${G_.p99_us.toFixed(0)} µs p99`;

const mean=(s,c)=>{const a=D.net[s][String(c)];return a.reduce((x,y)=>x+y,0)/a.length;};
const allN=SIG.flatMap(([s])=>CAPS.map(c=>mean(s,c)));
const lo=Math.min(...allN,0),hi=Math.max(...allN);

function tiles(r){
  const t=[["realised loss",inr(r.cost),"baseline "+inr(D.b1.total),""],
    ["loss removed",(r.net/D.b1.total*100).toFixed(1)+"%",inr(r.net),"hero"],
    ["fraud recall",(r.recall*100).toFixed(1)+"%","baseline "+(D.b1.fraud_recall*100).toFixed(1)+"%",""],
    ["false positives",(r.fpr*100).toFixed(2)+"%","baseline "+(D.b1.fpr*100).toFixed(2)+"%",""],
    ["escalated",(r.review_rate*100).toFixed(1)+"%","of "+D.test_n.toLocaleString("en-IN"),""],
    ["decision latency",G_.p50_us.toFixed(1)+" µs","p99 "+G_.p99_us.toFixed(0)+" µs",""]];
  $("tiles").innerHTML=t.map(([k,v,d,cls])=>`<div class="tile ${cls}"><div class="k">${k}</div>
    <div class="v" style="color:${cls==="hero"?"#34D399":"var(--ink)"}">${v}</div>
    <div class="d">${d}</div></div>`).join("");
}
function race(cap){
  const span=hi-lo||1,zero=(0-lo)/span*100;
  $("raceSub").textContent="net vs threshold at "+(cap*100).toFixed(0)+"% capacity";
  $("race").innerHTML=SIG.map(([s,desc,col])=>{
    const v=mean(s,cap),x=(v-lo)/span*100,left=v>=0?zero:x,w=Math.abs(x-zero);
    return `<div class="rrow"><div class="rname">${s}<i>${desc}</i></div>
      <div class="rtrack"><div class="rzero" style="left:${zero}%"></div>
      <div class="rfill" style="left:${left}%;width:${w}%;background:${col}"></div></div>
      <div class="rval" style="color:${col}">${inr(v)}</div></div>`;}).join("");
}
const W=560,H=250,P={l:56,r:58,t:14,b:28};
const cx=i=>P.l+i/(N-1)*(W-P.l-P.r), cy=v=>H-P.b-(v-lo)/((hi-lo)||1)*(H-P.t-P.b);
function curve(ci){
  let g="";
  for(let i=0;i<=4;i++){const val=lo+(hi-lo)*i/4,y=cy(val);
    g+=`<line class="gl" x1="${P.l}" y1="${y}" x2="${W-P.r}" y2="${y}"/>
        <text class="ax" x="${P.l-8}" y="${y+3}" text-anchor="end">${(val/1e6).toFixed(2)}M</text>`;}
  g+=`<line x1="${P.l}" y1="${cy(0)}" x2="${W-P.r}" y2="${cy(0)}" stroke="#5E7290" stroke-width="1.2" stroke-dasharray="4 4"/>`;
  CAPS.forEach((c,i)=>g+=`<text class="ax" x="${cx(i)}" y="${H-P.b+15}" text-anchor="middle">${(c*100).toFixed(0)}%</text>`);
  SIG.forEach(([s,,col])=>{
    const pts=CAPS.map((c,i)=>[cx(i),cy(mean(s,c))]);
    g+=`<path d="${pts.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1)).join(" ")}"
        fill="none" stroke="${col}" stroke-width="2.2" stroke-linejoin="round" opacity=".93"/>`;
    pts.forEach((p,i)=>g+=`<circle cx="${p[0]}" cy="${p[1]}" r="${i===ci?6:3}" fill="${col}"
        stroke="#080C15" stroke-width="${i===ci?2.5:0}"/>`);
    g+=`<text class="ax" x="${pts[N-1][0]+8}" y="${pts[N-1][1]+3}" fill="${col}">${s}</text>`;});
  $("curve").innerHTML=g;
}
function money(r){
  const parts=[["missed fraud",r.missed_fraud,"#F87171"],["blocked legitimate",r.blocked_legit,"#FBBF24"],["review",r.review_cost,"#2E7BF6"]];
  const tot=parts.reduce((a,p)=>a+p[1],0)||1;let x=0,s="",lg="";
  parts.forEach(([n,v,c],i)=>{const w=v/tot*400;
    s+=`<rect x="${x.toFixed(1)}" y="8" width="${Math.max(w,0).toFixed(1)}" height="28" fill="${c}"><title>${n}: ${inr(v)}</title></rect>`;
    lg+=`<g transform="translate(${i*135},62)"><rect width="8" height="8" y="-7" fill="${c}" rx="1"/>
      <text class="ax" x="13" y="0">${n}</text><text class="ax" x="13" y="14" fill="#93A6C4">${inr(v)}</text></g>`;x+=w;});
  $("money").innerHTML=s+lg;
}
function stream(cap){
  const A=["APPROVE","REVIEW","BLOCK"],acts=D.sample_actions[String(cap)]||[];
  $("stream").innerHTML=`<thead><tr><th style="text-align:right">amount</th><th>seg</th>
    <th style="text-align:right">P(fraud)</th><th>decision</th><th>actual</th></tr></thead><tbody>`+
    acts.slice(0,60).map((a,i)=>`<tr><td class="n">${inr(D.sample_amount[i])}</td>
      <td>${D.sample_segment[i]}</td><td class="n">${D.sample_p[i].toFixed(3)}</td>
      <td><span class="act ${A[a]}">${A[a]}</span></td>
      <td>${D.sample_label[i]?"fraud":"legit"}</td></tr>`).join("")+`</tbody>`;
  $("revN").textContent=acts.filter(a=>a===1).length+" of "+acts.length+" escalated";
}
function integration(cap){
  $("code").innerHTML=
`<em># your scorer is untouched — it just emits P(fraud)</em>
scores = <b>your_model</b>.predict_proba(txns)[:, 1]

<em># fit once on a held-out period. no labels required.</em>
gate = <b>Gate.fit</b>(scores_cal, amounts_cal, capacity=<u>${cap.toFixed(2)}</u>)

<em># then, per transaction</em>
action = <b>gate.decide</b>(score, amount)   <em># APPROVE | REVIEW | BLOCK</em>`;
  $("perf").innerHTML=[
    ["fitted on",G_.n_cal.toLocaleString("en-IN")+" rows"],
    ["p50 latency",G_.p50_us.toFixed(2)+" µs"],
    ["p99 latency",G_.p99_us.toFixed(2)+" µs"],
    ["batch throughput",(1e6/G_.batch_us_per_txn/1e6).toFixed(1)+"M txn/s"],
    ["model calls",'0'],["retraining",'none'],
  ].map(([k,v])=>`<div>${k}</div><div>${v}</div>`).join("");
}
$("audit").innerHTML=Object.entries(G_.example||{}).map(([k,v])=>
  `<em>${k.padEnd(23)}</em> ${typeof v==="number"?(Math.abs(v)>=1?v.toFixed(2):v.toFixed(6)):`<u>${v}</u>`}`).join("\n");

function render(){
  const i=+$("sl").value,r=G[i],cap=CAPS[i];
  $("sl").style.setProperty("--pct",(i/(N-1)*100)+"%");
  $("cNow").textContent=(cap*100).toFixed(0)+"%";
  tiles(r);race(cap);curve(i);money(r);stream(cap);integration(cap);
}
$("sl").addEventListener("input",render);
document.addEventListener("keydown",e=>{if(e.key==="ArrowLeft"||e.key==="ArrowRight"){
  $("sl").value=Math.max(0,Math.min(N-1,+$("sl").value+(e.key==="ArrowRight"?1:-1)));render();}});
render();
</script></body></html>
"""


def main() -> int:
    cfg = config.load()
    src = cfg.results_dir() / "console_data.json"
    gate_src = cfg.results_dir() / "gate_integration.json"
    if not src.exists():
        print("results/console_data.json missing — run scripts/export_console.py first")
        return 1
    if not gate_src.exists():
        print("results/gate_integration.json missing — run scripts/measure_gate.py first")
        return 1

    data = json.loads(src.read_text(encoding="utf-8"))
    gate = json.loads(gate_src.read_text(encoding="utf-8"))
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__GATE__", json.dumps(gate, separators=(",", ":"))))

    out = config.REPO_ROOT / "app" / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"written app/dashboard.html  ({out.stat().st_size/1e3:.0f} KB, "
          f"{len(data['caps'])} capacity points, source={data['data_source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
