# Submission checklist — Project Dhruva

Razorpay AI Buildathon, **Track 02 — AI Risk Manager**. Applications close **5 September 2026**.

Every box was verified, not assumed. Where a check runs mechanically, the command is given so anyone can repeat it.

---

## Repository

- [x] **`README.md` judge-ready and under 200 lines** — 170 lines. One-sentence opener, TL;DR box with the three findings, quick start in three commands, all 14 blocks tabulated, an explicit *"what this is NOT"* section, and reproducibility. Every internal link across every document resolves.
- [x] **All 14 block scripts exist and are listed in `RESULTS.md` §12** — 14 on disk, 14 in the README table, 14 in §12. No gaps in any direction.
  `ls scripts/ | grep -c "^block"` → 14
- [x] **22 tests pass, and need no data download** — they run on synthetic fixtures, so a judge who clones the repo can verify it in thirty seconds.
  `python -m pytest tests/ -q` → `22 passed`
- [x] **A fresh clone runs with no edits** — `config.yaml` holds no absolute path; the default is the gitignored `data/`, with `DHRUVA_DATA` as an override.
- [x] **`.gitignore` complete and safe** — hides nothing already tracked.
  `git ls-files -i -c --exclude-standard` → empty
- [x] **`requirements.txt` documents the verified reproduction environment** — Python 3.12.10 and all eight exact package versions, as floors plus documentation rather than hard pins that would break another platform.

## Demo

- [x] **The dashboard opens** — `app/dashboard.html`, double-click, no server and no build step.
- [x] **Header reads `TEST REPLAY · HELD-OUT DATA`**, never "LIVE".
- [x] **Fallbacks exist** — `results/figures/graph5_triage.png` carries the whole talk, and `RESULTS.md` §0 carries it in tables.

> ⚠️ **Corrected from an earlier draft.** This checklist once called for verifying `streamlit run app/console.py`. **That file was deleted.** It was built around the conformal α slider Block 9 retired, so it contradicted §0 — and it crashed on launch, because `export_console.py` had stopped exporting three `alpha_*` keys it read. Removing it also dropped `streamlit` and `plotly`; nothing else imported them. **The demo is `app/dashboard.html`. Do not reinstate the console.**

## Numbers and claims

- [x] **The 28% headline is retired everywhere** — it survives only in sentences that explicitly retire it.
- [x] **Razorpay claims verified against source.** ✅ *Vulcan* — 5× more fraudulent or disputed transactions "without increasing the number of alerts", accurate and now cited. ❌ *Bumblebee* — the old "~175 human review hours" was wrong twice: the real figure is **10,000–12,000 reviews a month, ~700–800 hours**, and it is the **merchant-website** queue, not a transaction queue. Both corrected with links.
- [x] **Every external citation audited** — five of six exact. `arXiv:2607.18088` had the wrong domain *and* a paraphrase inside quotation marks; both fixed. Two residual imprecisions labelled rather than removed.
- [x] **No phantom numbers.** Every figure traces to a block script and a JSON in `results/`.
- [x] **All caveats stated, not hidden** — selective labels (§8), the prevalence floor and failed ULB validation (§5), n = 3 transfer evidence with two broken models (§9), the baseline being 0.6% favourable (§0b), two of five bugs without regression tests (§7), and the analyst-accuracy condition (§9b).
- [x] **Protocol hash documented** — `results/protocol.lock`, config hash `d38888c9d05d398c`, frozen at commit `559c8fa` before any result existed. Scripts refuse to run if a frozen constant moves.

> ⚠️ **Corrected from an earlier draft.** This checklist once called for confirming the `+₹513,576 … +₹1,409,008` range **"is gone."** That is now backwards, and following it would delete a real result. The range *was* a phantom, was correctly struck, and has **since been measured** — `band` shows no sign flips on any of the four cost constants and lands on exactly that range. **The number was right and its evidence was missing; those are not the same thing.** It belongs in `RESULTS.md` §1.

## Block 13, added last

- [x] **Interpretations pre-registered before the run** — commit `98f651e` contains the docstring and no results, with the decision rule encoded in `verdict()` as code.
- [x] **A learned rejector was tried and did not win** — 0.0165 points short of a statistical tie at 2% capacity, inside the tie band everywhere else. The claim made is the weaker reading: **level, never ahead.** Never quote "band wins" without the margin.
- [x] **The analyst-accuracy condition is stated wherever the claim is** — README, Runbook, study guide and §0 all now say the recall-up/FPR-down pair assumes 95% accuracy and **inverts below ~90%**.

---

## Before you present

- [ ] Read `RESULTS.md` §0 and §10 — the result, and the "never say this" table
- [ ] Read `RUNBOOK.html` end to end once
- [ ] Drag the dashboard slider **10% → 2%** three times until the narration is automatic
- [ ] Set `$env:DHRUVA_DATA` if you intend to re-run a block live *(it does not persist between terminals)*
- [ ] Know cold: **7.9% at 2%** · **₹405,514** · **score-sorting loses money at 1–2%** · **14.6 µs**
- [ ] Rehearse the three answers that matter most:
  - *"How would you know it was working in production?"* → **you couldn't** — selective labels, offline replay
  - *"Six to eight percent isn't much."* → it is 6–8% **over the policy you run today**, for a sort-order change
  - *"Did you try learning the ranking?"* → **yes, and it lost** — by 0.0165 points, so *level, never ahead*

## Still open — say these before a judge finds them

| Gap | Status |
|---|---|
| The §0 margin is unswept | The cost sweep covers benefit over the *no-queue* baseline, not the 7.9% margin over rival queue policies. |
| The rejector target ignores magnitude | It classifies the *sign* of escalation value, so ₹1 ranks with ₹50,000. A magnitude-aware regressor is the obvious next attempt. |
| One dataset for the positive result | ULB fails entirely below ~0.1% prevalence. |
| Transfer evidence is n = 3 | Two of the three are **broken** models. Reproducible, but directional — not proof. |
| Bugs 4 and 5 have no regression test | Found by inspection; they would not be caught again automatically. |
| Analyst accuracy never measured | 95% is declared. The dominance claim inverts below ~90%. |
| **Track 02 rubric wording unverified** | Nobody has read the submission form. **This is still step one.** |
