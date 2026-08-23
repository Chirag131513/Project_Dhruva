# Start here

You don't need to understand the code to run it or present it. This file assumes you know
nothing about the project and gets you to a working demo.

**If you have 10 minutes before you present, read only Part 1 and Part 5.**

---

## Part 0 — Open a terminal in the right place

Everything below happens in one place. Open **PowerShell** and paste this once:

```powershell
cd "C:\Users\Chirag V Rao\OneDrive\ドキュメント\dhruva"
```

Your prompt should now end in `\dhruva>`. If it doesn't, nothing else will work — fix this first.

**Check the project is healthy:**

```powershell
python -m pytest tests/ -q
```

You want to see `22 passed`. It takes about 30 seconds. If you see that, everything is fine.

---

## Part 1 — Run the demo (this is the only thing you *need*)

**If `app\dashboard.html` already exists, just double-click it — you are done.** The three
commands below only rebuild it, and are needed only after the data or experiments change.

```powershell
python scripts/export_console.py
```

~2 min. Prints four lines like `cap 10%  cost 2,657,816  net +1,060,714`.

```powershell
python scripts/measure_gate.py
```

~2 min. Measures the deployable Gate end to end and times it. Prints the saving, the p50/p99
latency, and a real audit record. **`build_dashboard.py` will refuse to run without this.**

```powershell
python scripts/build_dashboard.py
```

Writes `app\dashboard.html`. **Double-click it.** No server — it opens as an ordinary file.

**Check the top-right says `TEST REPLAY · HELD-OUT DATA`.** If it says `DEV DATA`, stop — the
real data isn't loading, see Part 6.

### What you're looking at

- **Pipeline strip:** where the layer sits — your scorer → the gate → approve/review/block.
- **Top:** a slider for **analyst review capacity**. The only control that matters.
- **Tiles:** loss, money saved, false-positive rate, fraud recall, escalation rate.
- **Left panel:** four bars racing — the four ways of choosing which cases a human sees.
- **Right panel:** how each signal scales as capacity grows.
- **Integration panel:** the real three-line API, measured latency, and an audit record.
- **Bottom:** where the money goes, and a stream of individual decisions.

### The one thing to do on stage

Drag the capacity slider from 1% to 10%. Watch the four bars race:

1. **band pulls away** — ₹214k → ₹1,061,079 saved.
2. **conformal stalls** — peaks at 5%, then falls.
3. **random goes negative** — escalating the wrong cases *loses* money.

That is the finding. Escalation pays, the *choice* of cases is the entire value, and the
fashionable method is not the one that wins.

The dashboard is a plain file — just close the tab. Nothing runs in the background.

---

## Part 2 — Re-run the experiments (only if you want to)

You do **not** need to do this. The results are already saved in `results/`. Run these only if
you want to see the numbers appear, or if someone asks you to prove it reproduces.

Run them in order. Each prints a table and saves a file.

| # | Command | Time | What it shows |
|---|---|---|---|
| 0 | `python scripts/block0_audit.py` | 1 min | The data is real: 590,540 transactions, 24.4% have device data |
| 1 | `python scripts/block1_baseline.py` | 2 min | The fraud model works: PR-AUC 0.523 |
| 2 | `python scripts/block2_conformal.py` | 2 min | Why conformal looks healthy: 89.1% overall, 13.9% on fraud |
| 3 | `python scripts/block3_shift.py --seeds 3` | 8 min | Hypothesis 1 fails — reports it honestly |
| 4 | `python scripts/block4_cost.py` | 2 min | The money. Hypothesis 4 fails too |
| 5 | `python scripts/block5_segments.py` | 2 min | Which grouping actually works |
| 6 | `python scripts/block6_amendment.py` | 2 min | The fix, and what it's worth |
| 7 | `python scripts/block7_alpha_sweep.py` | 5 min | The curve, and the failure on a second dataset |
| 8 | `python scripts/block8_agnostic.py` | 12 min | The failure gets worse as the model gets better |
| 9 | `python scripts/block9_triage.py --seeds 10` | 25 min | **THE RESULT — the kill test that fired** |

**The most important one is Block 9.** If you only run one, run that.

---

## Part 3 — What to read, in order

| Read | When | Why |
|---|---|---|
| **This file** | now | you're here |
| **The Runbook** ([link](https://claude.ai/code/artifact/3d4cfb2f-f0ce-4aa1-ad81-1a5cbb4d060d)) | before presenting | your six-minute script, word for word, plus the ten questions judges will ask with the answers |
| **`RESULTS.md` §0** | before presenting | the result, on one page |
| **`RESULTS.md` in full** | if you have an hour | every number, every limitation |
| **`RESULTS.md` §10** | before writing any slide | the "never say this" table |
| **`PROTOCOL.md`** | only if asked about method | what was decided before any result existed |
| **`HANDOFF.md`** | if you come back after a break | where things stand and what's optional |

**Skip entirely unless you're changing code:** `IMPLEMENTATION.md`, everything in `dhruva/`,
everything in `scripts/`.

---

## Part 4 — The three sentences that matter

If you remember nothing else:

1. **"Under a capacity limit, choosing which cases a human sees is worth 28% of the loss."**
   ₹1,061,079 saved at 10% capacity, monotone in capacity, no sign flips under ±50% on any cost
   constant.

2. **"Random escalation loses money."**
   The signal is the whole value, not the reviewing. Band beats random by ₹1.32M, p = 0.0020.

3. **"A one-line rule beat conformal prediction 22×."**
   We implemented the 2026 literature, pre-registered a kill test, and it fired. Say this
   plainly — it is the most memorable thing in the submission.

---

## Part 5 — What to say if you're put on the spot

Full answers are in the Runbook. The short versions:

- **"Why not just retrain?"** — Fraud labels arrive weeks late. During the window that matters,
  retraining isn't available and recalibration is.
- **"Does it save money?"** — Yes, 28% of realised loss at 10% capacity, and the sign holds under ±50% sweeps on all four cost constants. The *conformal* arm did not; that's why we don't use it.
- **"Did you tune it?"** — No. The setting was frozen and hashed before any result existed;
  `git log` proves it. The one change is recorded as an amendment with its prediction written
  down beforehand.
- **"Does it generalise?"** — Not below ~0.1% fraud. It failed on a second dataset and that
  failure is in the write-up.
- **"Anything you got wrong?"** — Yes. We retracted one of our own results after finding it was
  measuring itself. It's in the commit history.

**If you don't know:** say "we didn't measure that," and say what you'd measure. Never invent a
number out loud — one made-up figure poisons every real one next to it.

---

## Part 6 — If something breaks

**`python` isn't recognised** — Python isn't on your PATH. Try `py` instead of `python`.

**`ModuleNotFoundError`** — a package is missing:
```powershell
python -m pip install -r requirements.txt
```

**Console says `DEV DATA` instead of `TEST REPLAY`** — the real data isn't being found. Check
these two files exist:
```powershell
dir "C:\Users\Chirag V Rao\dhruva-data\*.csv"
```
You need `train_transaction.csv` (683 MB) and `train_identity.csv` (27 MB). If they're missing,
re-download:
```powershell
python scripts/fetch_data.py
```

**Dashboard won't open** — you can give the whole talk from the table in `RESULTS.md` §0.
It has the four signals × four capacities, which is the entire finding.
`results\figures\` also holds the earlier plots if you want a picture.

**A script says `FROZEN CONFIG CHANGED`** — someone edited `config.yaml`. Undo it:
```powershell
git checkout config.yaml
```

**Everything looks broken** — reset to the last known-good state:
```powershell
git checkout .
```
This throws away uncommitted changes and restores the committed version. Then re-run the pytest
check from Part 0.

---

## Part 7 — What this project actually is, in plain words

A fraud model gives every transaction a score, and you act on it: approve or block. But a
merchant also has a small team of analysts who can look at a few cases by hand and get them
right. **Which cases should they look at?**

That question has a budget attached — maybe 2% of transactions, maybe 10%, never all of them.
We tested four ways of choosing, on real card-fraud data, holding the number of escalated cases
identical so that only the *choice* differed.

**The choice is worth 28% of the merchant's losses.** Picking cases at *random* actually loses
money — so it isn't the reviewing that helps, it's the picking.

And the winner was the simplest rule we wrote: send the analyst the cases sitting closest to the
decision boundary. It beat **conformal prediction** — the sophisticated method the 2026 research
literature is built around, and the one this project was originally designed to showcase — by a
factor of 22.

We wrote down in advance what result would make us abandon that method. Then it happened, and we
reported it.

Along the way we tested five predictions; two survived. We retracted one of our own results after
finding it was measuring itself. That is not a weakness in the submission. It is the submission.
