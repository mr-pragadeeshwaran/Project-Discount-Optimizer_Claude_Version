# 35 — Architecture Decision Records

**Audience:** engineers asking "why is it built this way?"
**Scope:** the load-bearing decisions, ADR-style. Each records context, the decision,
alternatives considered, the trade-off accepted, and the business impact. All are
**Accepted** and live in the code today. Structure:
[`30-code-organization.md`](30-code-organization.md) · costs we haven't paid down:
[`31-technical-debt.md`](31-technical-debt.md) · system shape:
[`../TECHNICAL/10-system-architecture.md`](../TECHNICAL/10-system-architecture.md).

Where a decision landed in a single commit, the hash is cited; several were made early
and are documented by the code itself.

---

## ADR-1 — File-based, no-database design

**Context.** One operator, one Windows laptop (5.9 GB RAM), a monthly CSV feed of a few
hundred thousand rows, and a client deliverable measured in weeks. Data volume never
approaches what needs indexing; the consumers of every artifact are pandas, Excel, and a
human.

**Decision.** No database. State is plain files with two conventions substituting for DB
guarantees: timestamped immutable run folders (`output/runs/<YYYYMMDD_HHMMSS>/`) act as
transactions, and every consumer resolves "latest complete run" itself (e.g.
`_latest_facttable()` in `scripts/analysis/discount_plan.py`). The filesystem is the
message bus; cross-engine interfaces are named CSVs with documented producers and
consumers (`agreement.csv`, `defense_hold.csv`).

**Alternatives.** SQLite (adds a schema-migration burden and hides state from Excel/`git
diff`), DuckDB (same, and another pin in a fragile env), Postgres (absurd for the
scale).

**Trade-off.** No concurrent writers, no referential integrity, join keys enforced only
by convention (the tracker normalizes ids specifically because `'532393.0'` vs
`'532393'` once broke an agreement join — `weekly_tracker.py:51`). Every table carrying
`product_id`+`cell_id` first is the discipline that keeps this workable.

**Business impact.** Zero infrastructure cost, every artifact inspectable and mailable
to a client as-is, and the whole audit trail survives as folders a non-engineer can
open.

## ADR-2 — Two-engine agreement before action

**Context.** Two independent stacks compute money answers: the champion waste model
(`discount_plan.py` + DML) and the pricing engine (`scripts/pricing/pricing_engine.py`,
elasticities + optimizer). Either alone can be wrong in its own characteristic way.

**Decision.** Act only where both agree. `pricing_engine.py` *produces*
`output/DISCOUNT_PLAN/pricing/agreement.csv` (its `_write_agreement`, ~line 220:
"PRODUCED here, CONSUMED by weekly_tracker"); `weekly_tracker.apply_agreement` holds any
cut the pricing engine disagrees with out of the executed wave. An absent file is
backward-compatible (behave as before); a present file is binding.

**Alternatives.** Ensemble the two estimates into one number (hides disagreement — the
most informative signal); trust the champion alone (single-method risk on a client's
revenue).

**Trade-off.** Fewer executable cuts and a second full stack to maintain. Disagreement
resolves to inaction, which can leave money on the table.

**Business impact.** "Two independent methods agree" is the single strongest sentence in
the client conversation, and held-for-disagreement cells become a visible, honest
category rather than silent noise.

## ADR-3 — Savings-target removal (the verdict channel was noise)

**Context.** The system originally graded its finding against a savings target (gate
C6). On 2026-08-11 the same ₹90,402/mo finding wore **three different verdicts in one
day** — BELOW an inherited ₹5 L bar, MEETS an operator-picked ₹75 k, BELOW a 5%-of-spend
prior (commit `b9408ec`). An intermediate fix (auto-derive the bar from observed spend,
`b670584`) was still a bar *chosen after seeing the data* — circular.

**Decision.** Remove the concept everywhere: no `SAVINGS_TARGET_*` knobs, no gate C6, no
MEETS/BELOW lines. The engine reports the confident amount **with spend-share context**
(₹90,402/mo ≈ 1.8% of ₹50 L/mo observed discount spend) and never grades sufficiency.
"Is it enough?" lives in the engagement contract, decided *before* a run. Gates keep
their historical numbering (C1–C5, C7, C8) so references stay valid;
`validate_plan.py`'s docstring records the removal.

**Alternatives.** Keep a configurable bar (every configuration was either inherited
noise or self-confirmation); keep C6 as advisory-only (a printed verdict is quoted as a
verdict regardless of a footnote).

**Trade-off.** Prospects who want a "did we hit the number?" line don't get one from the
engine; the salesperson must carry that framing.

**Business impact.** The engine's numbers became unimpeachable: nothing it prints can be
accused of grading itself. A disciplined client (Epigamia genuinely wastes little) gets
an honest small number instead of a manufactured verdict.

## ADR-4 — COGS removed from all user-facing surfaces

**Context.** Brands will not share COGS. Early report surfaces carried proxy-margin
columns built on assumed costs (COGS 50% of MRP etc.) — numbers a client could falsify
with one internal figure.

**Decision.** (Commit `dae7ad6`, breaking.) Every user-facing number is
**observable-space only**: discount spend, sales response, revenue-space ROI
(incremental revenue / trimmable-slice cost). The core engine never needed COGS —
pay-line, cuts, and DML are net-revenue math. Internal cost knobs (`DEFAULT_COGS_PCT` in
`v4_config.py`, stage 6/7 guardrails, `scenario_menu`'s optional profit KPIs) remain,
flagged as assumptions, and never reach delivered surfaces.

**Alternatives.** Ask clients for COGS (stalls every engagement at procurement); keep
proxy margins with disclaimers (a wrong number with a footnote is still a wrong number
in a screenshot).

**Trade-off.** The engine cannot make true profit claims — only revenue-space ones.
Margin-obsessed CFOs must do the last multiplication themselves.

**Business impact.** No deliverable contains a number the client can prove wrong from
their own books. Sales conversations shortened: nothing to negotiate about assumptions.

## ADR-5 — Within/FWL transform over the dummy fixed-effects matrix

**Context.** Stage 4 fits per-category regressions with cell fixed effects. With
hundreds of cells, `C(cell)` explodes into a dummy matrix that a 5.9 GB machine cannot
hold — the memory ceiling is real, not stylistic.

**Decision.** `stage4_model/elasticity.py`: when the projected dummy matrix exceeds
`_FE_DUMMY_BUDGET_MB = 32.0`, `_fit_category` routes to `_fit_category_within` — the
within (Frisch–Waugh–Lovell) transformation. Cell effects are absorbed by demeaning
within cell, which "yields IDENTICAL OLS coefficients" (comment at ~line 350) at a
fraction of the memory. The dummy path is kept for small categories where its richer
statsmodels output is convenient.

**Alternatives.** Sparse dummy matrices (statsmodels' formula path materializes dense);
chunked/out-of-core fitting (complexity for no statistical gain); dropping FE (confounds
cell identity with price — unacceptable).

**Trade-off.** Two code paths to keep equivalent, and the within path hand-rolls what
statsmodels would report for free (hence `_FEWithinModel`). The 32 MB budget is a tuned
constant, not a law.

**Business impact.** The full 699-cell, 8-category model fits on the actual hardware the
business owns. No cloud bill, no "works on a bigger machine" caveat.

## ADR-6 — Versioned, immutable deliverables

**Context.** A delivered workbook is evidence. Rebuilding `STATIQ_STAGE_REPORT.xlsx` in
place silently changes what a client already has — and once, a canonical file locked
open in Excel blocked a build outright.

**Decision.** (Commit `aefc81d`.) Delivered files are immutable history:
`scripts/reports/build_stage_workbook.py::_next_versioned_out` scans existing versions
and writes `STATIQ_STAGE_REPORT_v<N+1>.xlsx`; the original unversioned file counts as
v1. The convention is repo policy for every deliverable (`WAVE1_KAM_SHEET_v1/_v2.xlsx`
follow it), mirroring how run folders never overwrite each other.

**Alternatives.** Overwrite + git history (deliverables are git-ignored, so there is no
history); dates in filenames (two builds in a day collide; versions order trivially).

**Trade-off.** `output/` accumulates superseded workbooks (v1–v5 already), and "which
one is current" becomes "highest N" knowledge.

**Business impact.** What was sent can always be reproduced exactly; a dispute about
"the number you showed us" is settled by opening the version, not by memory.

## ADR-7 — Defense-hold credibility guard

**Context.** The challenger (Model B, champion + competitor controls) can flip a "waste"
cell to "competitive defense", which holds it out of the cut wave via
`defense_hold.csv`. But a *broken* Model B — degenerate fit, wrong-signed competitor
coefficient, categories too thin — also produces flips. Especially relevant while
competitor RPI direct coverage sits at ~6% ([debt item
8](31-technical-debt.md#8--competitor-rpi-direct-coverage-is-6)).

**Decision.** `scripts/analysis/challenger.py` (~lines 125–140): flips count as
defensive evidence **only when B is itself credible** — finite OOS R² ≥ 0.75, sane
competitor sign, healthy category fits (the adoption rule minus "must beat A"). A
non-credible B's flips are declared "noise, not evidence"; the code then writes an
**empty** hold file, which also releases prior holds under the retrain contract ("an
empty defense set … correctly releases any prior holds").

**Alternatives.** Honor all flips (a garbage model gets veto power over the plan — the
docstring's own warning: letting its flips hold the cut is "let noise reduce the plan");
ignore B entirely unless adopted (discards genuine warnings from a credible-but-second
model).

**Trade-off.** A real competitive-defense situation can go unprotected in the window
where B is legitimately unfittable (thin data). Chosen deliberately: false holds cost
credibility every week; a missed hold is caught by the kill-switch.

**Business impact.** The cut list can only shrink for reasons that survive the same
statistical bar the plan itself must pass. No unexplainable holds in front of the
client.

## ADR-8 — Challenger adoption by pre-registered rule

**Context.** When a promising model extension appears (competitor controls), the
temptation is to edit the validated champion. Post-hoc model selection — pick the spec
whose answer you like — is the classic way pricing analytics goes wrong.

**Decision.** The champion is never edited. `challenger.py` imports it read-only
(`importlib` pattern) and fits Model B alongside, then adopts B **only** on a rule fixed
before looking at results: (i) OOS R² ≥ 0.75, (ii) all category fits clear the same
floor as the C-gates, (iii) the competitor coefficient has the sane sign (rivals
discount more ⇒ our units down). Ties keep A. The same read-only-champion discipline
extends to `backtest_rolling.py` and `scenario_menu.py` ("NOTHING existing is edited or
overwritten").

**Alternatives.** Iterate on the champion directly (destroys the meaning of its
validation history); adopt on in-sample fit (guaranteed overfitting); human judgment per
case (unfalsifiable, and the human wants B to win).

**Trade-off.** Genuinely better models wait at the gate until they prove it
out-of-sample, and every challenger costs a full duplicate fit cycle.

**Business impact.** "The model changed" is always accompanied by "here is the
pre-registered rule it beat" — model churn can never be spun as cherry-picking. When the
champion *did* change (MODEL v2, commit `83f8d1c`), it was because a control was proven
circular by a falsification refit, not because a new spec looked better.

## ADR-9 — Local-only, no-auth dashboard

**Context.** The operator needs a Run Center and readouts; the data is a client's
proprietary sales feed; the machine is a personal laptop. A hosted dashboard means
accounts, TLS, a server bill, and an attack surface — for exactly one user.

**Decision.** `ui/app.py` is a stdlib `http.server` bound to `127.0.0.1` only (line
681), port `UI_PORT` default 8765, serving the single page `ui/index.html`. There is no
auth because there is no remote access: the network boundary *is* the auth. The run
endpoint accepts only step ids from the fixed `STEPS` allowlist — never arbitrary
commands — and steps run one at a time. Receipts are read from CURRENT-run artifacts
(the DML receipt reads `<run>/plan/dml_results.json` because "a top-level copy proved
able" to go stale — `ui/app.py` ~line 295), and a failing backtest renders as FAIL
rather than being hidden.

**Alternatives.** Hosted dashboard with login (cost + attack surface + the client's raw
data leaves the laptop, which the engagement terms don't allow); Streamlit/Flask
(dependency weight in an env where one unpinned package already produced a diverged
fit); plain Excel only (no Run Center, no one-click blessed order).

**Trade-off.** No remote or multi-user access — screen-share or exported workbooks are
the sharing mechanism. If the laptop is compromised, no second wall exists (consistent
with the single-machine posture; the real residual risk is [debt item
1](31-technical-debt.md#1--single-laptop-no-backup-of-the-raw-data)).

**Business impact.** The truthful sales line "your data never leaves the machine" is
enforced by architecture, not policy — and the operator gets a governed one-click flow
(blessed step order, stale-receipt-proof chips) with zero hosting cost.

