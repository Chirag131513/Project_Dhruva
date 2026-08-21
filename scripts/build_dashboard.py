"""Build a standalone dashboard from the precomputed console data.

    python scripts/build_dashboard.py     ->  app/dashboard.html

One self-contained HTML file with the data inlined. No server, no framework, no build step --
open it by double-clicking, or hand the file to someone. It cannot train, score, or reach the
network, which is the same guarantee the Streamlit console gives but easier to demonstrate.

WHY NOT STREAMLIT. Streamlit imposes its own chrome and widget styling, and on a projector that
reads as a prototype rather than an instrument. The whole demo rests on one gesture -- drag alpha,
watch the fraud bar refuse to move -- so that gesture deserves a surface built for it.

THE GHOST MARKER is the one design idea worth naming. Each coverage bar carries a faint marker
pinned to where the conventional alpha = 0.10 would put it. The contrast between convention and
the capacity-derived setting is therefore always on screen, not something the audience has to
hold in memory from thirty seconds ago.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode alpha, the rupee sign, or the box
# characters these scripts print. Without this, a run that produced every artefact correctly
# still exits non-zero on its own success message.
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
:root{
  --bg:#080D0F; --panel:#0F171A; --panel2:#162126; --rule:#1E2C31; --rule2:#2A3B41;
  --ink:#E9F0F1; --ink2:#93A6AC; --ink3:#64777E;
  --teal:#35C9BE; --amber:#E0A63F; --red:#E8776A; --green:#6FC48E;
  --mono:"IBM Plex Mono",ui-monospace,monospace;
  --sans:"IBM Plex Sans",-apple-system,"Segoe UI",sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:15px;
  -webkit-font-smoothing:antialiased;overflow-x:hidden}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}

.wrap{max-width:1560px;margin:0 auto;padding:20px 26px 40px;
  display:flex;flex-direction:column;gap:14px}

/* ---- topbar ---- */
.top{display:flex;align-items:center;gap:20px;flex-wrap:wrap;
  border-bottom:1px solid var(--rule);padding-bottom:14px}
.brand{font-size:1.34rem;font-weight:600;letter-spacing:-.024em}
.brand em{font-style:normal;color:var(--teal)}
.meta{display:flex;gap:22px;flex-wrap:wrap;flex:1;font-size:.74rem;color:var(--ink3)}
.meta b{color:var(--ink2);font-weight:500;font-family:var(--mono)}
.chip{font-family:var(--mono);font-size:.6rem;letter-spacing:.13em;text-transform:uppercase;
  padding:5px 10px;border-radius:2px;background:#12271F;color:var(--green);white-space:nowrap}
.chip.dev{background:#2A2312;color:var(--amber)}

/* ---- control ---- */
.ctl{background:var(--panel);border:1px solid var(--rule);border-radius:5px;padding:16px 20px;
  display:grid;grid-template-columns:1fr 320px;gap:26px;align-items:center}
@media(max-width:900px){.ctl{grid-template-columns:1fr}}
.lab{font-family:var(--mono);font-size:.6rem;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink3);margin-bottom:9px}
.lab .g,.ptitle .g{text-transform:none}
input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:26px;
  background:transparent;cursor:pointer;display:block}
input[type=range]::-webkit-slider-runnable-track{height:5px;border-radius:3px;
  background:linear-gradient(90deg,var(--teal) 0%,var(--teal) var(--pct,20%),var(--rule2) var(--pct,20%),var(--rule2) 100%)}
input[type=range]::-moz-range-track{height:5px;border-radius:3px;background:var(--rule2)}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:19px;height:19px;
  border-radius:50%;background:var(--ink);border:4px solid var(--bg);margin-top:-7px;
  box-shadow:0 0 0 1.5px var(--teal),0 3px 10px rgba(0,0,0,.6)}
input[type=range]::-moz-range-thumb{width:19px;height:19px;border-radius:50%;background:var(--ink);
  border:4px solid var(--bg);box-shadow:0 0 0 1.5px var(--teal)}
input[type=range]:focus-visible{outline:2px solid var(--teal);outline-offset:6px;border-radius:4px}
.ticks{display:flex;justify-content:space-between;font-family:var(--mono);font-size:.62rem;
  color:var(--ink3);margin-top:3px}
.alphaNow{font-family:var(--mono);font-size:2.1rem;font-weight:600;letter-spacing:-.03em;
  line-height:1;color:var(--ink)}
.alphaNote{font-size:.73rem;color:var(--ink3);line-height:1.5;margin-top:7px}
.alphaNote b{color:var(--teal)} .alphaNote i{font-style:normal;color:var(--red)}

/* ---- tiles ---- */
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
@media(max-width:1100px){.tiles{grid-template-columns:repeat(2,1fr)}}
.tile{background:var(--panel);border:1px solid var(--rule);border-radius:5px;padding:13px 15px}
.tile .k{font-family:var(--mono);font-size:.57rem;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink3);margin-bottom:7px}
.tile .v{font-family:var(--mono);font-size:1.62rem;font-weight:600;letter-spacing:-.03em;
  line-height:1;transition:color .25s}
.tile .d{font-family:var(--mono);font-size:.67rem;margin-top:6px;color:var(--ink3)}
.tile .d.up{color:var(--red)} .tile .d.dn{color:var(--green)}

/* ---- main grid ---- */
.grid{display:grid;grid-template-columns:1.15fr 1fr;gap:14px}
@media(max-width:1100px){.grid{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--rule);border-radius:5px;padding:16px 20px}
.ptitle{font-family:var(--mono);font-size:.6rem;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink3);margin-bottom:16px;display:flex;justify-content:space-between;align-items:center}
.ptitle span{color:var(--ink3);letter-spacing:.06em;text-transform:none;font-size:.66rem}
.note{font-size:.72rem;color:var(--ink3);line-height:1.55;margin-top:14px}
.note b{color:var(--ink2)}

/* ---- coverage bars ---- */
.bar{margin-bottom:22px;position:relative}
.bar:last-of-type{margin-bottom:6px}
.barhead{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px}
.barname{font-size:.86rem;color:var(--ink2);font-weight:500}
.barval{font-family:var(--mono);font-size:1.72rem;font-weight:600;letter-spacing:-.03em;line-height:1}
.track{position:relative;height:26px;background:var(--panel2);border-radius:3px;overflow:visible}
.fill{position:absolute;left:0;top:0;bottom:0;border-radius:3px;
  transition:width .42s cubic-bezier(.22,1,.36,1),background .3s}
.ghost{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--ink3);opacity:.55}
.ghost::after{content:attr(data-l);position:absolute;top:-15px;left:50%;transform:translateX(-50%);
  font-family:var(--mono);font-size:.55rem;letter-spacing:.08em;color:var(--ink3);white-space:nowrap}
.tgt{position:absolute;top:-7px;bottom:-7px;width:1.5px;background:var(--ink2);
  border-radius:1px}
.tgt::after{content:"target 0.90";position:absolute;top:-16px;left:50%;transform:translateX(-50%);
  font-family:var(--mono);font-size:.55rem;letter-spacing:.06em;color:var(--ink2);white-space:nowrap}
.pinned{font-family:var(--mono);font-size:.6rem;color:var(--amber);letter-spacing:.06em}

/* ---- charts ---- */
svg{display:block;width:100%;overflow:visible}
.gl{stroke:var(--rule);stroke-width:1}
.ax{font-family:var(--mono);font-size:9.5px;fill:var(--ink3)}

/* ---- lower ---- */
.grid3{display:grid;grid-template-columns:1fr 1fr 1.25fr;gap:14px}
@media(max-width:1100px){.grid3{grid-template-columns:1fr}}
table{border-collapse:collapse;width:100%;font-size:.76rem}
th{font-family:var(--mono);font-size:.55rem;letter-spacing:.11em;text-transform:uppercase;
  color:var(--ink3);text-align:left;font-weight:600;padding:6px 8px;border-bottom:1px solid var(--rule2)}
td{padding:5px 8px;border-bottom:1px solid var(--rule);color:var(--ink2)}
tr:last-child td{border-bottom:0}
td.n{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%}
.ok{background:var(--green)} .out{background:var(--red)} .thin{background:var(--ink3)}
.scroll{max-height:210px;overflow-y:auto}
.scroll::-webkit-scrollbar{width:7px}
.scroll::-webkit-scrollbar-thumb{background:var(--rule2);border-radius:4px}
.act{font-family:var(--mono);font-size:.62rem;letter-spacing:.06em;padding:2px 6px;border-radius:2px}
.APPROVE{background:#12271F;color:var(--green)}
.REVIEW{background:#2A2312;color:var(--amber)}
.BLOCK{background:#2A1614;color:var(--red)}
.pull{font-family:"Newsreader",Georgia,serif;font-size:1.02rem;line-height:1.5;color:var(--ink2);
  border-left:2px solid var(--teal);padding-left:15px;margin:0}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body>
<div class="wrap">

  <div class="top">
    <div class="brand">Dhruva<em>.</em></div>
    <div class="meta">
      <div>held out <b id="mN"></b></div>
      <div>fraud <b id="mF"></b></div>
      <div>volume <b id="mV"></b></div>
      <div>α_fraud pinned <b id="mAF"></b></div>
      <div>capacity <b id="mC"></b></div>
    </div>
    <div class="chip" id="chip"></div>
  </div>

  <div class="ctl">
    <div>
      <div class="lab"><span class="g">α</span>_LEGIT — MISCOVERAGE BUDGET ON LEGITIMATE TRAFFIC</div>
      <input type="range" id="sl" min="0" max="10" step="1" value="3">
      <div class="ticks" id="ticks"></div>
    </div>
    <div>
      <div class="lab">current</div>
      <div class="alphaNow num" id="aNow"></div>
      <div class="alphaNote">method uses <b id="aDer"></b> · convention was <i>0.10</i></div>
    </div>
  </div>

  <div class="tiles" id="tiles"></div>

  <div class="grid">
    <div class="panel">
      <div class="ptitle">Coverage — the two budgets <span id="cvSub"></span></div>
      <div class="bar">
        <div class="barhead"><div class="barname">legitimate</div>
          <div class="barval num" id="vL" style="color:var(--teal)"></div></div>
        <div class="track"><div class="fill" id="fL" style="background:var(--teal)"></div>
          <div class="tgt" style="left:90%"></div>
          <div class="ghost" id="gL" data-l="α=0.10"></div></div>
      </div>
      <div class="bar">
        <div class="barhead"><div class="barname">fraud <span class="pinned">— budget pinned</span></div>
          <div class="barval num" id="vF" style="color:var(--amber)"></div></div>
        <div class="track"><div class="fill" id="fF" style="background:var(--amber)"></div>
          <div class="tgt" style="left:90%"></div>
          <div class="ghost" id="gF" data-l="α=0.10"></div></div>
      </div>
      <p class="pull">Drag α. The legitimate bar moves the whole width of the panel. The fraud
      bar does not move at all — its budget is set separately. That independence is the finding.</p>
    </div>

    <div class="panel">
      <div class="ptitle">Cost against the legitimate budget <span>log α</span></div>
      <svg id="curve" viewBox="0 0 560 250" preserveAspectRatio="none" style="height:250px"></svg>
      <div class="note">Shallow left, steep right: tightening the legitimate budget is nearly
      free, loosening it is not. <b>Dashed red</b> is the plain cost-optimal threshold — the thing
      to beat.</div>
    </div>
  </div>

  <div class="grid3">
    <div class="panel">
      <div class="ptitle">Where the money goes</div>
      <svg id="money" viewBox="0 0 400 116" style="height:116px"></svg>
      <div class="note"><b>Blocked-legitimate</b> is what kills the conventional setting — not
      missed fraud.</div>
    </div>
    <div class="panel">
      <div class="ptitle">Coverage per segment</div>
      <div class="scroll"><table id="cells"></table></div>
      <div class="note"><span class="dot ok"></span> in band ·
        <span class="dot out"></span> out · <span class="dot thin"></span> below n≥100, not
        reported.</div>
    </div>
    <div class="panel">
      <div class="ptitle">Decision stream <span id="revN"></span></div>
      <div class="scroll"><table id="stream"></table></div>
    </div>
  </div>
</div>

<script>
const D = __DATA__;
const $ = i => document.getElementById(i);
const inr = v => "₹" + Math.round(v).toLocaleString("en-IN");
const G = D.grid, N = G.length;

$("mN").textContent = D.test_n.toLocaleString("en-IN");
$("mF").textContent = D.test_fraud.toLocaleString("en-IN");
$("mV").textContent = "₹" + (D.test_volume/1e6).toFixed(1) + "M";
$("mAF").textContent = D.alpha_fraud;
$("mC").textContent = (D.capacity*100).toFixed(0) + "%";
$("aDer").textContent = D.alpha_derived.toFixed(5);
const real = D.data_source === "ieee-cis";
$("chip").textContent = real ? "TEST REPLAY · IEEE-CIS" : "DEV DATA · NOT REPORTABLE";
if(!real) $("chip").classList.add("dev");

$("ticks").innerHTML = "<span>" + G[0].alpha_legit.toFixed(4) + "</span><span>"
  + G[N-1].alpha_legit.toFixed(4) + "</span>";

// index of the conventional 0.10 and the derived value
const iConv = G.reduce((b,r,i)=>Math.abs(r.alpha_legit-0.10)<Math.abs(G[b].alpha_legit-0.10)?i:b,0);
const iDer  = G.reduce((b,r,i)=>Math.abs(r.alpha_legit-D.alpha_derived)<Math.abs(G[b].alpha_legit-D.alpha_derived)?i:b,0);
$("sl").max = N-1; $("sl").value = iDer;

const meanCov = (row, cls) => {
  const v = Object.entries(row.cells).filter(([k,x])=>k.endsWith("|"+cls)&&x!==null).map(([,x])=>x);
  return v.length ? v.reduce((a,b)=>a+b,0)/v.length : NaN;
};
const convL = meanCov(G[iConv],0), convF = meanCov(G[iConv],1);

function tiles(r){
  const b1=D.b1, t=[
    ["realised cost", inr(r.cost), (r.net>=0?"+":"") + Math.round(r.net).toLocaleString("en-IN") + " vs baseline", r.net>0?"dn":"up", r.net>0?"var(--green)":"var(--red)"],
    ["false-positive rate",(r.fpr*100).toFixed(2)+"%","baseline "+(b1.fpr*100).toFixed(2)+"%",r.fpr>b1.fpr?"up":"dn",r.fpr>b1.fpr?"var(--red)":"var(--green)"],
    ["fraud recall",(r.recall*100).toFixed(1)+"%","baseline "+(b1.fraud_recall*100).toFixed(1)+"%",r.recall>b1.fraud_recall?"dn":"up","var(--ink)"],
    ["escalated",(r.review_rate*100).toFixed(1)+"%","capacity "+(D.capacity*100).toFixed(0)+"%","","var(--ink)"],
    ["truncated",(r.truncated*100).toFixed(0)+"%","fell back to threshold","","var(--ink)"],
  ];
  $("tiles").innerHTML = t.map(([k,v,d,c,col])=>
    `<div class="tile"><div class="k">${k}</div><div class="v" style="color:${col}">${v}</div>
     <div class="d ${c}">${d}</div></div>`).join("");
}

function bars(r){
  const L=meanCov(r,0), F=meanCov(r,1);
  $("vL").textContent=L.toFixed(3); $("vF").textContent=F.toFixed(3);
  $("fL").style.width=(L*100)+"%"; $("fF").style.width=(F*100)+"%";
  $("gL").style.left=(convL*100)+"%"; $("gF").style.left=(convF*100)+"%";
  $("fL").style.background = Math.abs(L-(1-r.alpha_legit))<=.03 ? "var(--teal)" : "var(--red)";
  $("cvSub").textContent = "α_legit "+r.alpha_legit.toFixed(4)+" · α_fraud "+D.alpha_fraud;
}

const W=560,H=250,P={l:52,r:14,t:14,b:26};
const lx = a => P.l + (Math.log10(a)-Math.log10(G[0].alpha_legit))/
  (Math.log10(G[N-1].alpha_legit)-Math.log10(G[0].alpha_legit))*(W-P.l-P.r);
const maxC = Math.max(...G.map(r=>r.cost), D.b1.total)*1.06;
const ly = c => H-P.b - c/maxC*(H-P.t-P.b);

function curve(r){
  const pts=G.map(g=>[lx(g.alpha_legit),ly(g.cost)]);
  const path=pts.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1)).join(" ");
  const area=path+` L${pts[N-1][0].toFixed(1)} ${H-P.b} L${pts[0][0].toFixed(1)} ${H-P.b} Z`;
  let g="";
  for(let i=0;i<=4;i++){const y=P.t+i*(H-P.t-P.b)/4;
    g+=`<line class="gl" x1="${P.l}" y1="${y}" x2="${W-P.r}" y2="${y}"/>
        <text class="ax" x="${P.l-7}" y="${y+3}" text-anchor="end">${((maxC*(1-i/4))/1e6).toFixed(1)}M</text>`;}
  [G[0].alpha_legit,0.01,0.10,G[N-1].alpha_legit].forEach(a=>{
    g+=`<text class="ax" x="${lx(a)}" y="${H-P.b+15}" text-anchor="middle">${a}</text>`;});
  const cx=lx(r.alpha_legit), cy=ly(r.cost);
  $("curve").innerHTML=`
    <defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#35C9BE" stop-opacity=".24"/>
      <stop offset="100%" stop-color="#35C9BE" stop-opacity="0"/></linearGradient></defs>
    ${g}
    <path d="${area}" fill="url(#ag)"/>
    <path d="${path}" fill="none" stroke="#35C9BE" stroke-width="2.2" stroke-linejoin="round"/>
    <line x1="${P.l}" y1="${ly(D.b1.total)}" x2="${W-P.r}" y2="${ly(D.b1.total)}"
      stroke="#E8776A" stroke-width="1.4" stroke-dasharray="5 4"/>
    <text class="ax" x="${W-P.r}" y="${ly(D.b1.total)-7}" text-anchor="end"
      fill="#E8776A">plain threshold</text>
    <line x1="${lx(D.alpha_derived)}" y1="${P.t}" x2="${lx(D.alpha_derived)}" y2="${H-P.b}"
      stroke="#64777E" stroke-width="1" stroke-dasharray="2 3"/>
    <circle cx="${cx}" cy="${cy}" r="7.5" fill="#E0A63F" stroke="#080D0F" stroke-width="2.5"/>`;
}

function money(r){
  const parts=[["missed fraud",r.missed_fraud,"#E8776A"],
               ["blocked legitimate",r.blocked_legit,"#E0A63F"],
               ["review",r.review_cost,"#35C9BE"]];
  const tot=parts.reduce((a,p)=>a+p[1],0)||1; let x=0,s="",lg="";
  parts.forEach(([n,v,c],i)=>{const w=v/tot*400;
    s+=`<rect x="${x.toFixed(1)}" y="10" width="${Math.max(w,0).toFixed(1)}" height="30" fill="${c}"
        rx="${i===0?"2":"0"}"><title>${n}: ${inr(v)}</title></rect>`;
    lg+=`<g transform="translate(${i*135},64)"><rect width="8" height="8" y="-7" fill="${c}" rx="1"/>
        <text class="ax" x="13" y="0">${n}</text>
        <text class="ax" x="13" y="14" fill="#93A6AC">${inr(v)}</text></g>`; x+=w;});
  $("money").innerHTML=s+lg;
}

function cells(r){
  const rows=Object.keys(r.cells).sort().map(k=>{
    const [seg,cls]=k.split("|"), v=r.cells[k], n=r.cell_n[k]||0;
    const tgt=1-(cls==="0"?r.alpha_legit:D.alpha_fraud);
    const st=v===null?"thin":(Math.abs(v-tgt)<=.03?"ok":"out");
    return `<tr><td>${seg}</td><td>${cls==="1"?"fraud":"legit"}</td>
      <td class="n">${n.toLocaleString("en-IN")}</td>
      <td class="n">${v===null?"—":v.toFixed(3)}</td>
      <td><span class="dot ${st}"></span></td></tr>`;}).join("");
  $("cells").innerHTML=`<thead><tr><th>seg</th><th>class</th><th style="text-align:right">n</th>
    <th style="text-align:right">cov</th><th></th></tr></thead><tbody>${rows}</tbody>`;
}

function stream(r){
  const A=["APPROVE","REVIEW","BLOCK"], acts=D.sample_actions[String(r.alpha_legit)]||[];
  const rows=acts.slice(0,60).map((a,i)=>
    `<tr><td class="n">${inr(D.sample_amount[i])}</td><td>${D.sample_segment[i]}</td>
     <td class="n">${D.sample_p[i].toFixed(3)}</td>
     <td><span class="act ${A[a]}">${A[a]}</span></td>
     <td>${D.sample_label[i]?"fraud":"legit"}</td></tr>`).join("");
  $("stream").innerHTML=`<thead><tr><th style="text-align:right">amount</th><th>seg</th>
    <th style="text-align:right">P(fraud)</th><th>decision</th><th>actual</th></tr></thead>
    <tbody>${rows}</tbody>`;
  $("revN").textContent = acts.filter(a=>a===1).length + " of " + acts.length + " escalated";
}

function render(){
  const i=+$("sl").value, r=G[i];
  $("sl").style.setProperty("--pct",(i/(N-1)*100)+"%");
  $("aNow").textContent=r.alpha_legit.toFixed(4);
  tiles(r); bars(r); curve(r); money(r); cells(r); stream(r);
}
$("sl").addEventListener("input",render);
document.addEventListener("keydown",e=>{
  if(e.key==="ArrowLeft"||e.key==="ArrowRight"){
    $("sl").value=Math.max(0,Math.min(N-1,+$("sl").value+(e.key==="ArrowRight"?1:-1)));
    render();}});
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
    html = TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))

    out = config.REPO_ROOT / "app" / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"written app/dashboard.html  ({out.stat().st_size/1e3:.0f} KB, "
          f"{len(data['grid'])} α points, source={data['data_source']})")
    print("open it directly in a browser — no server needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
