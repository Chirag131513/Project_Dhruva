# Submission checklist — Project Dhruva

Razorpay AI Buildathon, **Track 02 — AI Risk Manager**. Applications close **5 September 2026**.

Every box below was verified rather than assumed. Where a check could be run mechanically, the command is given so anyone can re-run it.

---

## Repository

- [x] **`README.md` is under 200 lines and judge-ready** — 166 lines. Opens with one sentence, carries a TL;DR box with the three findings, quick start in three commands, all 13 blocks tabulated, an explicit *"what this is NOT"* section, and reproducibility. Every internal link resolves.
- [x] **All 13 block scripts exist and are listed in `RESULTS.md` §12** — 13 on disk, 13 in §12, no gaps either way.
  `ls scripts/ | grep -c "^block"` → 13
- [x] **22 tests pass** — and they need **no data download**; they run on synthetic fixtures, so a judge who clones the repo can verify immediately.
  `python -m pytest tests/ -q` → `22 passed`
- [x] **A fresh clone runs without editing anything** — `config.yaml` no longer hardcodes an absolute data path. Default is the gitignored `data/`; `DHRUVA_DATA` overrides it.
- [x] **`.gitignore` covers data, caches, environments, editor and OS cruft** — and hides nothing already tracked.
  `git ls-files -i -c --exclude-standard` → empty
- [x] **`requirements.txt` documents the verified reproduction environment** — floors plus the exact tested versions of Python and all eight packages.

## Demo

- [x] **The dashboard opens** — `app/dashboard.html`, double-click, no server and no build step.
  Rebuild chain, all three in order: `export_console.py` → `measure_gate.py` → `build_dashboard.py`.
- [x] **Header reads `TEST REPLAY · HELD-OUT DATA`**, never "LIVE".
- [x] **Fallback exists if the dashboard fails** — `results/figures/graph5_triage.png` carries the whole talk, and `RESULTS.md` §0 carries it in tables.

> ⚠️ **Corrected from an earlier draft of this checklist.** It listed *"Dashboard runs (`streamlit run app/console.py`)"*. **`app/console.py` no longer exists.** It was the Streamlit console built around the conformal α slider that Block 9 retired — so it contradicted §0 — and by the time it was deleted it crashed on launch, because `export_console.py` had stopped exporting three `alpha_*` keys it read. Deleting it also dropped `streamlit` and `plotly` from `requirements.txt`; nothing else imported them. **The demo is `app/dashboard.html`. Do not reinstate the console.**

## Numbers and claims

- [x] **The 28% headline is retired everywhere** — it survives only in sentences that explicitly retire it (`README`, `RESULTS.md` §0, `START_HERE` Part 4, the runbook's *"Do not say 28%"* callout). It compared against a baseline with **no review queue**, which nobody runs.
- [x] **Razorpay claims verified against source.**
  - ✅ **Vulcan — verified.** Reported as identifying **5× more fraudulent or disputed transactions "without increasing the number of alerts"**. Quote accurate; now cited with a link.
  - ❌ **Bumblebee — was wrong twice, now corrected.** The write-up said *"~175 human review hours a month"*. Razorpay's own engineering blog reports **10,000–12,000 manual reviews a month, ~700–800 human hours** — understated fourfold. Worse, it is the **merchant-website** review queue, not a transaction queue, so citing it as evidence of transaction triage was a category error. Both fixed, with a source link.
- [x] **Every external citation audited** — five of six exact against source. `arXiv:2607.18088` had the wrong domain *and* a paraphrase presented inside quotation marks; both corrected. Two residual imprecisions are labelled rather than removed.
- [x] **All caveats stated, not hidden** — selective labels (§8), the prevalence floor and failed ULB validation (§5), n = 3 transfer evidence with two broken models (§9), the baseline being 0.6% favourable (§0b), and two of five bugs having no regression test (§7).
- [x] **Protocol hash documented** — `results/protocol.lock`, config hash `d38888c9d05d398c`, frozen at commit `559c8fa` before any result existed. Scripts refuse to run if a frozen constant changes.

> ⚠️ **Corrected from an earlier draft of this checklist.** It read: *"`RESULTS.md` has no phantom numbers (the ±513k–₹1.4M range is gone)."* **That instruction is now backwards and following it would delete a real result.**
>
> The range `+₹513,576 … +₹1,409,008` was indeed a phantom — asserted in the runbook with no code behind it, because the K5 sweep loop hardcoded the *conformal* arm. It was correctly struck. **It has since been measured.** The sweep now covers both arms, and `band` shows **no sign flips on any of the four cost constants**, landing on **exactly** that range.
>
> The number was right and its evidence was missing. Those are not the same thing — striking it was correct on the evidence then available, and restoring it is correct now that it reproduces. **The range belongs in `RESULTS.md` §1. Do not remove it.**

---

## Before you present

- [ ] Read `RESULTS.md` §0 and §10 — the result, and the "never say this" table
- [ ] Read `RUNBOOK.html` end to end once
- [ ] Open the dashboard and drag the slider **10% → 2%** three times until the narration is automatic
- [ ] `$env:DHRUVA_DATA` set if you intend to re-run any block live *(it does not persist between terminals)*
- [ ] Know cold: **7.9% at 2%** · **₹405,514** · **score-sorting loses money at 1–2%** · **14.6 µs**
- [ ] Rehearse the two answers that are hardest and matter most:
  - *"How would you know it was working in production?"* → **you couldn't** — selective labels, offline replay
  - *"Six to eight percent isn't much."* → it is 6–8% **over the policy you run today**, for a config change with no retraining

## Still open — say these before a judge finds them

| Gap | Status |
|---|---|
| The §0 margin itself is unswept | §1's sweep covers band's benefit over the *no-queue* baseline. The 7.9% margin over rival **queue policies** is not itself cost-swept. |
| One dataset for the positive result | ULB fails entirely below ~0.1% prevalence. |
| Transfer evidence is n = 3 | And two of the three are **broken** models, not weaker ones. Reproducible, but directional — not proof. |
| Bugs 4 and 5 have no regression test | Found by inspection; they would not be caught again automatically. |
| Track 02 rubric wording unverified | Nobody has read the submission form. **This is still step one.** |
