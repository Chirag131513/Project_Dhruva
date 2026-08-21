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

Two commands. The first prepares the data the screen needs; the second opens the screen.

```powershell
python scripts/export_console.py
```

Takes ~2 minutes. It prints eleven lines like `alpha_legit=0.002  cost=3,681,959  fpr=1.36%`.
When it says `written results/console_data.json`, it worked.

```powershell
streamlit run app/console.py
```

Your browser opens automatically. **Check the top-right corner says `TEST REPLAY · IEEE-CIS`.**
If it says `DEV DATA`, stop — the real data isn't loading, see Part 6.

### What you're looking at

- **Left:** a slider labelled `α_legit`. This is the only control that matters.
- **Top row:** four numbers — cost, false-positive rate, fraud recall, escalation rate.
- **Middle:** a cost curve, and a coverage table per segment.
- **Bottom:** a stream of individual decisions.

### The one thing to do on stage

Drag the capacity slider from 1% to 10%. Watch the four bars race:

1. **band pulls away** — ₹214k → ₹1,061,079 saved.
2. **conformal stalls** — peaks at 5%, then falls.
3. **random goes negative** — escalating the wrong cases *loses* money.

That is the finding. Escalation pays, the *choice* of cases is the entire value, and the
fashionable method is not the one that wins.

To stop the console: press `Ctrl+C` in PowerShell.

---

## Part 2 — Re-run the experiments (only if you want to)

You do **not** need to do this. The results are already saved in `results/`. Run these only if
you want to see the numbers appear, or if someone asks you to prove it reproduces.

Run them in order. Each prints a table and saves a file.

| # | Command | Time | What it shows |
|---|---|---|---|
| 0 | `python scripts/block0_audit.py` | 1 min | The data is real: 590,540 transactions, 24.4% have device data |
| 1 | `python scripts/block1_baseline.py` | 2 min | The fraud model works: PR-AUC 0.523 |
| 2 | `python scripts/block2_conformal.py` | 2 min | **The headline: 89.1% overall, 13.9% on fraud** |
| 3 | `python scripts/block3_shift.py --seeds 3` | 8 min | Hypothesis 1 fails — reports it honestly |
| 4 | `python scripts/block4_cost.py` | 2 min | The money. Hypothesis 4 fails too |
| 5 | `python scripts/block5_segments.py` | 2 min | Which grouping actually works |
| 6 | `python scripts/block6_amendment.py` | 2 min | The fix, and what it's worth |
| 7 | `python scripts/block7_alpha_sweep.py` | 5 min | The curve, and the failure on a second dataset |

**The most important one is Block 2.** If you only run one, run that.

---

## Part 3 — What to read, in order

| Read | When | Why |
|---|---|---|
| **This file** | now | you're here |
| **The Runbook** ([link](https://claude.ai/code/artifact/3d4cfb2f-f0ce-4aa1-ad81-1a5cbb4d060d)) | before presenting | your six-minute script, word for word, plus the ten questions judges will ask with the answers |
| **`RESULTS.md` §2 and §4** | before presenting | the headline and what you're allowed to claim — two pages |
| **`RESULTS.md` in full** | if you have an hour | every number, every limitation |
| **`RESULTS.md` §9** | before writing any slide | the "never say this" table |
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

**Console won't open at all** — present from the picture instead. Open
`results\figures\graph4_alpha_sweep.png`. The left panel is the cost curve with the method's
setting marked; the right panel is the second dataset failing. You can give the entire talk from
that one image.

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

A fraud model gives every transaction a score. To use it you need a cutoff, and picking that
cutoff is normally guesswork.

There's a technique called **conformal prediction** that replaces guesswork with a promise:
*"90% of the time the right answer is in the set I give you."* It's just entering production
fraud systems — there's a paper from August 2026.

**We found that the promise can be kept on average and broken completely where it matters.**
On real card-fraud data the system keeps its 89% promise overall while covering 13.9% of actual
fraud, because 96% of transactions are legitimate and they dominate the average.

We showed why, showed how to fix it (calculate the budget from how many analysts you actually
have, rather than picking a round number), showed what the fix costs, and showed where it stops
working entirely.

Along the way we tested five specific predictions. Two survived. We reported the other three
anyway, and retracted one of our own results when we found it was flawed.

That last part is not a weakness in the submission. It is the submission.
