"""Build a standalone dashboard from the precomputed Block 9 data.

    python scripts/build_dashboard.py     ->  app/dashboard.html

One self-contained HTML file with the data inlined. No server, no framework, no build step.
It cannot train, score, or reach the network.

WHAT THE DEMO IS NOW. Block 9 killed the conformal framing: a one-line rule beat it 22x. So the
control is a CAPACITY slider, not an alpha slider, and the hero is a race between four escalation
signals. Drag capacity upward and `band` pulls away while `conformal` stalls and `random` goes
negative -- which says the three things that matter in one gesture: escalation pays, the choice
of cases is the entire value, and the sophisticated method is not the one that wins.

Keeping the losing method at the centre of the demo would have been the dishonest choice and also
the less interesting one.
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
<title>Dhruva — risk console</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap">
<style>
:root{--bg:#080D0F;--panel:#0F171A;--panel2:#162126;--rule:#1E2C31;--rule2:#2A3B41;
--ink:#E9F0F1;--ink2:#93A6AC;--ink3:#64777E;
--teal:#35C9BE;--amber:#E0A63F;--red:#E8776A;--green:#6FC48E;--grey:#4A5C63;
--mono:"IBM Plex Mono",ui-monospace,monospace;--sans:"IBM Plex Sans",-apple-system,sans-serif;}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;
-webkit-font-smoothing:antialiased;overflow-x:hidden}
.wrap{max-width:1560px;margin:0 auto;padding:20px 26px 40px;display:flex;flex-direction:column;gap:14px}
.top{display:flex;align-items:center;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--rule);padding-bottom:14px}
.brand{font-size:1.34rem;font-weight:600;letter-spacing:-.024em}.brand em{font-style:normal;color:var(--teal)}
.meta{display:flex;gap:22px;flex-wrap:wrap;flex:1;font-size:.74rem;color:var(--ink3)}
.meta b{color:var(--ink2);font-weight:500;font-family:var(--mono)}
.chip{font-family:var(--mono);font-size:.6rem;letter-spacing:.13em;text-transform:uppercase;
padding:5px 10px;border-radius:2px;background:#12271F;color:var(--green);white-space:nowrap}
.chip.dev{background:#2A2312;color:var(--amber)}
.ctl{background:var(--panel);border:1px solid var(--rule);border-radius:5px;padding:16px 20px;
display:grid;grid-template-columns:1fr 300px;gap:26px;align-items:center}
@media(max-width:900px){.ctl{grid-template-columns:1fr}}
.lab{font-family:var(--mono);font-size:.6rem;letter-spacing:.13em;text-transform:uppercase;color:var(--ink3);margin-bottom:9px}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:26px;background:transparent;cursor:pointer;display:block}
input[type=range]::-webkit-slider-runnable-track{height:5px;border-radius:3px;
background:linear-gradient(90deg,var(--teal) 0%,var(--teal) var(--pct,0%),var(--rule2) var(--pct,0%),var(--rule2) 100%)}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:19px;height:19px;border-radius:50%;
background:var(--ink);border:4px solid var(--bg);margin-top:-7px;box-shadow:0 0 0 1.5px var(--teal),0 3px 10px rgba(0,0,0,.6)}
input[type=range]::-moz-range-track{height:5px;border-radius:3px;background:var(--rule2)}
input[type=range]::-moz-range-thumb{width:19px;height:19px;border-radius:50%;background:var(--ink);border:4px solid var(--bg)}
input[type=range]:focus-visible{outline:2px solid var(--teal);outline-offset:6px;border-radius:4px}
.ticks{display:flex;justify-content:space-between;font-family:var(--mono);font-size:.62rem;color:var(--ink3);margin-top:3px}
.now{font-family:var(--mono);font-size:2.1rem;font-weight:600;letter-spacing:-.03em;line-height:1}
.nnote{font-size:.73rem;color:var(--ink3);line-height:1.5;margin-top:7px}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
@media(max-width:1100px){.tiles{grid-template-columns:repeat(2,1fr)}}
.tile{background:var(--panel);border:1px solid var(--rule);border-radius:5px;padding:13px 15px}
.tile .k{font-family:var(--mono);font-size:.57rem;letter-spacing:.13em;text-transform:uppercase;color:var(--ink3);margin-bottom:7px}
.tile .v{font-family:var(--mono);font-size:1.62rem;font-weight:600;letter-spacing:-.03em;line-height:1}
.tile .d{font-family:var(--mono);font-size:.67rem;margin-top:6px;color:var(--ink3)}
.grid{display:grid;grid-template-columns:1.1fr 1fr;gap:14px}
@media(max-width:1100px){.grid{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--rule);border-radius:5px;padding:16px 20px}
.ptitle{font-family:var(--mono);font-size:.6rem;letter-spacing:.13em;text-transform:uppercase;color:var(--ink3);
margin-bottom:16px;display:flex;justify-content:space-between;align-items:center}
.ptitle span{letter-spacing:.06em;text-transform:none;font-size:.66rem}
.note{font-size:.72rem;color:var(--ink3);line-height:1.55;margin-top:14px}.note b{color:var(--ink2)}
.race{display:flex;flex-direction:column;gap:15px}
.rrow{display:grid;grid-template-columns:132px 1fr 128px;gap:13px;align-items:center}
.rname{font-size:.83rem;color:var(--ink2)}
.rname i{font-style:normal;display:block;font-family:var(--mono);font-size:.58rem;color:var(--ink3);margin-top:2px}
.rtrack{position:relative;height:23px;background:var(--panel2);border-radius:3px}
.rzero{position:absolute;top:-5px;bottom:-5px;width:1.5px;background:var(--ink3);opacity:.7}
.rfill{position:absolute;top:0;bottom:0;border-radius:2px;transition:left .45s cubic-bezier(.22,1,.36,1),width .45s cubic-bezier(.22,1,.36,1)}
.rval{font-family:var(--mono);font-size:1.05rem;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
svg{display:block;width:100%;overflow:visible}
.ax{font-family:var(--mono);font-size:9.5px;fill:var(--ink3)}.gl{stroke:var(--rule);stroke-width:1}
.grid3{display:grid;grid-template-columns:1fr 1.3fr;gap:14px}
@media(max-width:1100px){.grid3{grid-template-columns:1fr}}
table{border-collapse:collapse;width:100%;font-size:.76rem}
th{font-family:var(--mono);font-size:.55rem;letter-spacing:.11em;text-transform:uppercase;color:var(--ink3);
text-align:left;font-weight:600;padding:6px 8px;border-bottom:1px solid var(--rule2)}
td{padding:5px 8px;border-bottom:1px solid var(--rule);color:var(--ink2)}
td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right}
.scroll{max-height:216px;overflow-y:auto}
.scroll::-webkit-scrollbar{width:7px}.scroll::-webkit-scrollbar-thumb{background:var(--rule2);border-radius:4px}
.act{font-family:var(--mono);font-size:.62rem;letter-spacing:.06em;padding:2px 6px;border-radius:2px}
.APPROVE{background:#12271F;color:var(--green)}.REVIEW{background:#2A2312;color:var(--amber)}.BLOCK{background:#2A1614;color:var(--red)}
.pull{font-family:"Newsreader",Georgia,serif;font-size:1.02rem;line-height:1.5;color:var(--ink2);
border-left:2px solid var(--teal);padding-left:15px;margin:16px 0 0}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body><div class="wrap">

<div class="top">
  <div class="brand">Dhruva<em>.</em></div>
  <div class="meta">
    <div>held out <b id="mN"></b></div><div>fraud <b id="mF"></b></div>
    <div>volume <b id="mV"></b></div><div>baseline loss <b id="mB"></b></div>
    <div>seeds <b id="mS"></b></div>
  </div>
  <div class="chip" id="chip"></div>
</div>

<div class="ctl">
  <div><div class="lab">Analyst review capacity — share of transactions a human can see</div>
    <input type="range" id="sl" min="0" max="3" step="1" value="3">
    <div class="ticks" id="ticks"></div></div>
  <div><div class="lab">capacity</div><div class="now" id="cNow"></div>
    <div class="nnote">Escalation volume is <b>identical across signals</b>. Only the choice of
    cases differs.</div></div>
</div>

<div class="tiles" id="tiles"></div>

<div class="grid">
  <div class="panel">
    <div class="ptitle">Which cases to escalate <span id="raceSub"></span></div>
    <div class="race" id="race"></div>
    <p class="pull">Random escalation loses money. The value is not in reviewing more — it is in
    reviewing the right ones. Conformal prediction, the method the 2026 literature is built on,
    finishes second-to-last.</p>
  </div>
  <div class="panel">
    <div class="ptitle">Net benefit against the threshold <span>by capacity</span></div>
    <svg id="curve" viewBox="0 0 560 262" style="height:262px"></svg>
    <div class="note"><b>Band</b> scales cleanly with capacity. <b>Conformal</b> peaks at 5% and
    falls — it runs out of genuinely ambiguous cases and starts padding the queue.</div>
  </div>
</div>

<div class="grid3">
  <div class="panel"><div class="ptitle">Where the money goes</div>
    <svg id="money" viewBox="0 0 400 116" style="height:116px"></svg>
    <div class="note">Escalation converts <b>blocked-legitimate</b> losses into review cost at a
    favourable exchange rate.</div></div>
  <div class="panel"><div class="ptitle">Decision stream <span id="revN"></span></div>
    <div class="scroll"><table id="stream"></table></div></div>
</div>
</div>

<script>
const D=__DATA__,$=i=>document.getElementById(i);
const inr=v=>(v<0?"-":"")+"₹"+Math.round(Math.abs(v)).toLocaleString("en-IN");
const G=D.grid,CAPS=D.caps,N=G.length;
const SIG=[["band","distance to threshold","var(--teal)"],
           ["disagree","ensemble disagreement","var(--amber)"],
           ["conformal","conformal sets","var(--red)"],
           ["random","random escalation","var(--grey)"]];
$("mN").textContent=D.test_n.toLocaleString("en-IN");
$("mF").textContent=D.test_fraud.toLocaleString("en-IN");
$("mV").textContent="₹"+(D.test_volume/1e6).toFixed(1)+"M";
$("mB").textContent=inr(D.b1.total);
$("mS").textContent=D.seeds;
const real=D.data_source==="ieee-cis";
$("chip").textContent=real?"TEST REPLAY · IEEE-CIS":"DEV DATA · NOT REPORTABLE";
if(!real)$("chip").classList.add("dev");
$("sl").max=N-1;
$("ticks").innerHTML=CAPS.map(c=>`<span>${(c*100).toFixed(0)}%</span>`).join("");

const allNet=SIG.flatMap(([s])=>CAPS.map(c=>D.net[s][String(c)].reduce((a,b)=>a+b,0)/D.net[s][String(c)].length));
const lo=Math.min(...allNet,0),hi=Math.max(...allNet);
const mean=(s,c)=>{const a=D.net[s][String(c)];return a.reduce((x,y)=>x+y,0)/a.length;};

function tiles(r){
  const t=[["realised loss",inr(r.cost),"baseline "+inr(D.b1.total)],
    ["saved vs threshold",inr(r.net),(r.net/D.b1.total*100).toFixed(1)+"% of loss"],
    ["false-positive rate",(r.fpr*100).toFixed(2)+"%","baseline "+(D.b1.fpr*100).toFixed(2)+"%"],
    ["fraud recall",(r.recall*100).toFixed(1)+"%","baseline "+(D.b1.fraud_recall*100).toFixed(1)+"%"],
    ["escalated",(r.review_rate*100).toFixed(1)+"%","of "+D.test_n.toLocaleString("en-IN")]];
  $("tiles").innerHTML=t.map(([k,v,d],i)=>`<div class="tile"><div class="k">${k}</div>
    <div class="v" style="color:${i===1?"var(--green)":"var(--ink)"}">${v}</div>
    <div class="d">${d}</div></div>`).join("");
}
function race(cap){
  const span=hi-lo||1,zero=(0-lo)/span*100;
  $("raceSub").textContent="net vs threshold at "+(cap*100).toFixed(0)+"% capacity";
  $("race").innerHTML=SIG.map(([s,desc,col])=>{
    const v=mean(s,cap),x=(v-lo)/span*100;
    const left=v>=0?zero:x,w=Math.abs(x-zero);
    return `<div class="rrow"><div class="rname">${s}<i>${desc}</i></div>
      <div class="rtrack"><div class="rzero" style="left:${zero}%"></div>
      <div class="rfill" style="left:${left}%;width:${w}%;background:${col}"></div></div>
      <div class="rval" style="color:${col}">${inr(v)}</div></div>`;}).join("");
}
const W=560,H=262,P={l:58,r:16,t:16,b:30};
const cx=i=>P.l+i/(N-1)*(W-P.l-P.r);
const cy=v=>{const span=hi-lo||1;return H-P.b-(v-lo)/span*(H-P.t-P.b);};
function curve(ci){
  let g="";
  for(let i=0;i<=4;i++){const val=lo+(hi-lo)*i/4,y=cy(val);
    g+=`<line class="gl" x1="${P.l}" y1="${y}" x2="${W-P.r}" y2="${y}"/>
        <text class="ax" x="${P.l-8}" y="${y+3}" text-anchor="end">${(val/1e6).toFixed(2)}M</text>`;}
  g+=`<line x1="${P.l}" y1="${cy(0)}" x2="${W-P.r}" y2="${cy(0)}" stroke="#64777E" stroke-width="1.3" stroke-dasharray="4 4"/>`;
  CAPS.forEach((c,i)=>{g+=`<text class="ax" x="${cx(i)}" y="${H-P.b+16}" text-anchor="middle">${(c*100).toFixed(0)}%</text>`;});
  SIG.forEach(([s,,col])=>{
    const pts=CAPS.map((c,i)=>[cx(i),cy(mean(s,c))]);
    g+=`<path d="${pts.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1)).join(" ")}"
        fill="none" stroke="${col.replace('var(--','').replace(')','')==='grey'?'#4A5C63':col}"
        stroke-width="2.2" stroke-linejoin="round" opacity=".92"/>`;
    pts.forEach((p,i)=>{g+=`<circle cx="${p[0]}" cy="${p[1]}" r="${i===ci?6:3.2}"
        fill="${col}" stroke="#080D0F" stroke-width="${i===ci?2.5:0}"/>`;});
    g+=`<text class="ax" x="${pts[N-1][0]+7}" y="${pts[N-1][1]+3}" fill="${col}">${s}</text>`;});
  $("curve").innerHTML=g;
}
function money(r){
  const parts=[["missed fraud",r.missed_fraud,"#E8776A"],["blocked legitimate",r.blocked_legit,"#E0A63F"],["review",r.review_cost,"#35C9BE"]];
  const tot=parts.reduce((a,p)=>a+p[1],0)||1;let x=0,s="",lg="";
  parts.forEach(([n,v,c],i)=>{const w=v/tot*400;
    s+=`<rect x="${x.toFixed(1)}" y="10" width="${Math.max(w,0).toFixed(1)}" height="30" fill="${c}"><title>${n}: ${inr(v)}</title></rect>`;
    lg+=`<g transform="translate(${i*135},64)"><rect width="8" height="8" y="-7" fill="${c}" rx="1"/>
      <text class="ax" x="13" y="0">${n}</text><text class="ax" x="13" y="14" fill="#93A6AC">${inr(v)}</text></g>`;x+=w;});
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
function render(){
  const i=+$("sl").value,r=G[i],cap=CAPS[i];
  $("sl").style.setProperty("--pct",(i/(N-1)*100)+"%");
  $("cNow").textContent=(cap*100).toFixed(0)+"%";
  tiles(r);race(cap);curve(i);money(r);stream(cap);
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
    if not src.exists():
        print("results/console_data.json missing — run scripts/export_console.py first")
        return 1
    data = json.loads(src.read_text(encoding="utf-8"))
    out = config.REPO_ROOT / "app" / "dashboard.html"
    out.write_text(TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":"))),
                   encoding="utf-8")
    print(f"written app/dashboard.html  ({out.stat().st_size/1e3:.0f} KB, "
          f"{len(data['caps'])} capacity points, source={data['data_source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
