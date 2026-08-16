# 31 — Technical Debt

**Audience:** engineers (and the honest version of ourselves).
**Scope:** the known weaknesses of the system as of 2026-08-16, each verified against
the repo — no aspirational framing. Structure of the codebase:
[`30-code-organization.md`](30-code-organization.md). Why the deliberate constraints
exist (which are *not* debt):
[`35-architecture-decisions.md`](35-architecture-decisions.md).

A deliberate design constraint with a recorded rationale is an ADR; an unpaid cost with
no rationale is debt. This file lists the second kind, roughly ordered by how much it
should worry you.

## 1. Single laptop, no backup of the raw data

The entire system — code, venv, raw exports, every run, every delivered workbook — lives
on one Windows machine (5.9 GB RAM, ~1 GB free). Git protects the code, but `.gitignore`
deliberately excludes `input_data/` ("Proprietary input data — never commit"), `data/`,
`output/runs/`, and most of `output/`. There is **no backup mechanism anywhere in the
repo** for the raw platform exports or the run history. A disk failure loses the raw
Epigamia feeds and all 45 run folders under `output/runs/`; the feeds may not be
re-downloadable from the platform later.

*Path out:* an encrypted off-machine copy of `input_data/` and `output/DISCOUNT_PLAN/`
after each feed drop. Cheap, unglamorous, not done yet.

## 2. The feedback loop has never closed on real actuals

The weekly loop (predict → KAM executes → actuals return → scorecard/kill-switch) is
fully built and *simulated* end-to-end: `scripts/tracker/verify_loop.py` replays a
historical week as a fake "fresh export" and asserts the scorecard and kill-switch fire.
But no wave has yet completed against genuinely new data. Wave 1
(`output/DISCOUNT_PLAN/wave1_issued.csv` — 7 cuts + 15 tests) is issued for Monday
2026-08-17; its actuals arrive only with the next platform export. Until then, every
accuracy claim rests on holdouts within the training feed, and the kill-switch
(`scripts/tracker/killswitch.py`, two-strikes-and-revert with confounders excused) has
never fired for real.

*Path out:* nothing to build — this retires only by running the loop. First real scored
week is the single most valuable artifact the system can produce.

## 3. The 10-week feed makes the rolling backtest unscoreable

`scripts/validation/backtest_rolling.py` requires `MIN_TRAIN_WEEKS = 12` per fold; the
current feed provides 10 usable weeks (`plan_summary.json`: `"weeks": 10`, after
edge-week trimming). Every fold is skipped and the backtest reports **FAIL, honestly** —
the dashboard shows the failure rather than a stale pass (the FAIL-report writing in
`ui/app.py` exists precisely for this). Consequence: the champion's out-of-time,
multi-week-ahead forecasting skill (`champion_recursive` vs the naive benchmarks) is
currently *unmeasured*. The OOS R² 0.965 is a within-feed holdout, a weaker claim.

*Path out:* time. At ~4 usable weeks per monthly export, the backtest becomes scoreable
around two more feed drops. Do not lower `MIN_TRAIN_WEEKS` to force a pass.

## 4. `scenario_menu.py` runs for hours on this hardware

The negotiation menu re-runs the differential-evolution optimizer stack once per
scenario across every (category × city) group. The module has a real runtime guard
(`build_problem` built once per group and shared; DE `maxiter`/`popsize` CLI-tunable)
and a documented "fast mode" was used for the Epigamia menu (commit `255270a`), but a
full-effort menu is a multi-hour job on the 5.9 GB machine. This makes "re-run the menu
with the counterpart's constraints" an overnight operation, not an in-the-room one.

*Path out:* profile the DE inner loop; consider caching fitted demand models across
scenarios (only the objective config varies) or a coarse-then-fine search. Until then,
plan menu runs the day before a negotiation.

## 5. Stale documentation pinned to the previous engagement (24 Mantra)

The repo carries three layers of docs and two of them predate the Epigamia engagement:

- `docs/legacy/` — entirely 24 Mantra era (e.g. `ARCHITECTURE.md` quotes 24 Mantra MAPE;
  `COMPLETE_FLOW.md` walks "4 SKUs of 24 Mantra Organic … 11 cities").
- Parts of `docs/reference/` — `OPERATIONS_MANUAL.md` and `COMPLETE_SYSTEM_GUIDE.md` are
  flagged in `docs/README.md` as "pinned to the earlier 24 Mantra engagement — read for
  mechanism, not for current numbers".
- Additional stale spots found while auditing: `output/DISCOUNT_PLAN/PLAN.md` still
  opens "24 Mantra Organic (Blinkit) … validated C1–C6 PASS" and quotes the retired ₹5 L
  target (run `20260705_161703`) even though the folder's other artifacts
  (`WEEKLY_READOUT.md`, `wave1_issued.csv`) are current Epigamia; and
  `scripts/README.md` says experiment harnesses read from `v4_outputs/`, a location
  `.gitignore` itself marks as legacy (run store is `output/runs/` now).

Risk: an engineer or a prospect quoting a stale number as current. The mitigation so far
is the routing rule in `docs/README.md` (numbers only from the live dashboard and latest
workbook), not cleanup.

*Path out:* regenerate or delete `output/DISCOUNT_PLAN/PLAN.md`; fix the two lines in
`scripts/README.md`; leave `docs/legacy` clearly labeled rather than deleted (it
documents real decisions).

## 6. pandas FutureWarnings, silenced globally

Two verified deprecation sites will break on a future pandas major:

- `stage4_model/elasticity.py:117` — `regular.groupby("sku_city",
  group_keys=False).apply(...)`: pandas 2.2 warns that `DataFrameGroupBy.apply`
  operating on the grouping columns is deprecated.
- `scripts/tracker/weekly_tracker.py:332` — `pd.concat([hist, new], ...)` where `hist`
  is legitimately empty on the first week: concat with empty/all-NA entries is
  deprecated behavior.

Both are currently invisible because the analysis scripts open with
`warnings.simplefilter("ignore")` (e.g. `discount_plan.py`, `challenger.py`,
`dml_estimate.py`, and inside `_fit_category*`). The blanket ignore is itself debt: it
also swallows *new* warnings the pinned stack would otherwise surface. The pin
(`pandas==2.2.2` in `requirements.txt`) makes this safe today, not forever.

*Path out:* fix the two call sites (select the value column after `groupby`; guard the
empty-history concat), then narrow the filters to specific known-noisy warnings.

## 7. Diagnostics scripts frozen with old-era constants

`scripts/diagnostics/` still hardcodes the previous engagement: `diag2.py` reads a
literal `input_data/24 Mantra X Jaggery Powder 500G X 1 Year X BlinkIT.xlsx` (a file
that no longer exists); `data_diagnostic.py`, `diag3.py`, `diag4.py` filter
`BRAND.str.contains('24 Mantra')`. Running them today produces empty or crashing
results. They are catalogued as disposable in `scripts/README.md` and
`validate_report.py`/`unlock_estimate.py` are explicitly "frozen probes from the 5L era"
(commit `b9408ec`), so this is contained — but a new engineer *will* try to run them.

*Path out:* either parameterize the brand from `v4_config` (five-minute fix each) or
move the dead ones to `archive/`.

## 8. Competitor RPI direct coverage is ~6%

The champion's competitive control `rpi_w` (our price / competitor median price per
category × grammage × city × week) matches the current feed **directly on only 6% of
cell-weeks** (verified by rebuilding the panel: `[plan] competitor RPI (Mother Dairy,
Amul, Milky Mist): 6% of cell-weeks matched directly`). The remaining 94% are filled
with the cell's median RPI, then neutral parity 1.0. Under 24 Mantra the same
construction had 82% direct coverage (commit `83f8d1c`); the collapse comes from
grammage/category granularity mismatches between Epigamia's pack sizes and the
competitor rows in the export. Consequence: the competitive control is close to a
constant for most cells, so "competition explains this cell" conclusions (challenger
flips, defense holds) rest on thin data. The defense-hold credibility guard
([ADR-7](35-architecture-decisions.md#adr-7--defense-hold-credibility-guard)) exists
partly because of this.

*Path out:* fuzzy grammage matching (nearest pack size within the category) and/or
widening `COMPETITOR_BRANDS`; report per-cell RPI coverage in `all_cells.csv` so
downstream consumers can see which cells actually have a competitive signal.

## 9. "Others" city aggregation ambiguity

The raw platform export uses a literal city value `Others` — the platform's own residual
bucket over all non-named cities (verified in `input_data/*.csv`: Ahmedabad … Pune, plus
`Others`). The engine models it like any other city, so `Others` cells (e.g. cut cell
`126995_500g_Others`) carry recommendations. But the KAM's execution console may not
expose an "Others" lever — `scripts/reports/build_wave_kam_sheet.py:141` has to attach
the note "aggregated residual cities — if the console has no 'Others' [bucket…]". Two
unknowns: whether a discount change can be *executed* for the residual bucket at all,
and whether the platform's definition of which cities fall in `Others` is stable week to
week (if it isn't, the panel's `Others` time series mixes compositions).

*Path out:* one question to the KAM answers the first unknown; a composition check
across monthly feeds (does a named city ever appear/disappear?) answers the second.
Until then, treat `Others` cells as lower-confidence than their statistics suggest.

## 10. Per-machine environment assumptions

The runtime environment is reproducible only by convention: `run.bat`/`launch_ui.bat`
prefer `.venv\Scripts\python.exe` and silently fall back to whatever `python` is on PATH
— an unpinned interpreter reproduces the 2026-07-11 incident (`requirements.txt` header:
the diverged RLM fit, OOS R² = −9.99, came from an unpinned environment). The pins are
exact but there is no hash-locked lockfile, no `python_requires`, no CI job that
rebuilds the env from scratch, and `.claude/launch.json` plus the absolute repo path
(`D:\1. PROJECT\Stat IQ Lab`, with a space) are assumed by the bat files' `cd /d
"%~dp0"` pattern. Moving to a second machine is a manual, error-prone afternoon.

*Path out:* a `make_env.bat` that creates `.venv` from `requirements.txt` and runs
`pytest -m "not slow"` as a smoke check; fail (don't fall back) when `.venv` is missing.

## Minor, recorded so they aren't rediscovered

- `stage8_monitoring/` is an empty vestigial package; the real stage 8 is
  `stage8_output/`. Delete or populate.
- `data/master/` and `data/processed/` are empty placeholders that suggest a data layout
  that never materialized.
- `v4_config.py` — the `v4_` prefix is a fossil of a rewrite; renaming it touches every
  import, so it stays for now.
- A stray Excel lock file (`SALES_KIT/.~lock.BLINKIT_OUTREACH_TRACKER.xlsx#`) and
  `output/~$OPTIMIZATION_REPORT.xlsx` show delivered workbooks get opened in place;
  harmless, but `build_stage_workbook.py` already grew an output-path override because a
  locked-open canonical file blocked a build once.

