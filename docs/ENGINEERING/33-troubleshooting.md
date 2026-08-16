# 33 — Troubleshooting: real failure modes and their fixes

*Audience: engineers. Every failure below has actually happened (or is
explicitly coded for) in this repo. General background:
[32 — Change Guide](32-change-guide.md) for how to change things safely,
[34 — Onboarding](34-onboarding.md) for first-time setup,
`docs/TECHNICAL/13-api.md` for the dashboard internals.*

**First diagnostic everywhere:** the Run Center streams each step's full
stdout/stderr into the live log (`ui/app.py` job runner), ending in
`OK <label>` or `FAILED <label> (exit <rc>)`. Read the log before anything
else — the engine is fail-loud by design, so the message usually names the
offending file, key, or cell.

---

## 1. Settings file rejected — "…is not a setting this system has"

**Symptom:** uploading a settings file (or the next run after editing
`config/settings.xlsx`) raises `SettingsError`, e.g.:

```
config/settings.xlsx has 1 problem(s):
  'TRAIN_LOOKBACK_DAY' is not a setting this system has — did you mean TRAIN_LOOKBACK_DAYS?
```

**Why:** unknown keys are an **error, not a silent no-op** — a typo that ran
silently would quietly keep the default, which is far more expensive than a
crash (`settings_loader.py`, `_parse_settings`).

**Fix:** correct the key, or download a fresh template from the dashboard's
Inputs & Settings page (`GET /api/settings/template`) — the template is
generated from the code's `REGISTRY`, so its keys are correct by
construction. Notes: a **blank** value means "use the code default"; write
`none` for an explicitly empty list; the upload endpoint dry-run-validates in
a temp dir (`validate_bytes`), so a rejected file changes **nothing** — the
previous settings remain live.

## 2. "No own-brand rows matched patterns …"

**Symptom:** Stage 1 stops with:

```
No own-brand rows matched patterns ['epigamia'] ... Set BRAND_NAME / OWN_BRAND_PATTERNS in v4_config.py to match.
```

**Why:** the ingest filter (`stage1_ingestion/ingest.py::filter_own_brand`)
keeps only own-brand rows, matching on **word boundaries**, and refuses to
proceed with an empty result. The error lists the brand spellings it *did*
find in the data — use those.

**Fix:** set `BRAND_NAME` / `OWN_BRAND_PATTERNS` in the **settings file**
(the error text's mention of `v4_config.py` predates the settings registry;
the file override is the right lever — see [32 §1](32-change-guide.md)).
`OWN_BRAND_PATTERNS` must contain *every* spelling of the brand present in
the export, pipe-separated. Related failure in the same function: if a
pattern also matches a competitor (the classic `'Sun'` catching `'Sunfeast'`),
the over-match guard fails loud too — tighten the patterns, or set
`STRICT_OWN_BRAND_MATCH = no` only if you genuinely own several distinct
brand strings.

## 3. `MemoryError` on a big category (Stage 4)

**Symptom:** historically, `MemoryError: Unable to allocate …` while fitting
a category with many cells; on this 5.9GB-RAM machine (~1GB actually free)
the fixed-effects dummy matrix simply cannot be allocated.

**Why & the built-in fix:** `stage4_model/elasticity.py` budgets the dummy
matrix at `_FE_DUMMY_BUDGET_MB = 32.0`. Any category whose matrix would
exceed that — and any fit that still raises `MemoryError` — is automatically
refit via the **within (FWL) transform** (`_fit_category_within`): cell
effects absorbed by demeaning, which yields *identical* OLS coefficients
without materialising the dummies. So a modern run should self-heal; the log
line to look for is "using the within-FE transform".

**If you still hit it:** close Excel and the browser during builds (they are
the other RAM consumers), and never "fix" it by upgrading the numeric stack —
`requirements.txt` pins `numpy==1.26.4` for binary compatibility, and the one
unpinned environment this repo saw produced a diverged RLM fit
(OOS R² = −9.99). Reinstall the pinned set instead.

## 4. Port 8765 busy — dashboard won't start

**Symptom:** `ui/app.py` dies at startup with `OSError: [WinError 10048]`
(only one usage of each socket address).

**Why:** an instance is already running — typically `launch_ui.bat` was
double-clicked twice. The server binds `127.0.0.1:8765`
(`ThreadingHTTPServer` in `ui/app.py::main`; port from env `UI_PORT`,
default 8765).

**Fix:** usually nothing to fix — open http://localhost:8765; the running
instance is fine (it serves fresh state per request, no restart needed after
a run). To genuinely run a second instance, start it with a different port:
`set UI_PORT=8766` then `python -X utf8 ui/app.py`. Related non-error: the
run endpoint returns *"A job is already running — wait for it to finish."* —
one job at a time is a design rule, not a fault.

## 5. Excel file locked — a build fails

**Symptom:** a step fails with `PermissionError: [Errno 13]` while saving an
`.xlsx` — most often `output/DISCOUNT_PLAN/WEEKLY_TRACKER.xlsx`, which the
tracker writes to a **fixed** path (`scripts/tracker/workbook.py`) while
someone has it open in Excel.

**Fix:** close the workbook in Excel/LibreOffice and rerun the step. Marker
files like `~$Foo.xlsx` or `.~lock.Foo.xlsx#` are the telltale (ingestion
already skips `~`-prefixed files for exactly this reason).

**The policy that prevents this class of failure:** delivered reports use
**versioned outputs** — `scripts/reports/build_stage_workbook.py`
(`_next_versioned_out`, writing `STATIQ_STAGE_REPORT_v<N+1>.xlsx`) and
`scripts/reports/build_wave_kam_sheet.py` never overwrite an existing file,
so an open copy can never block a build. New reports must follow the same
pattern ([32 §3](32-change-guide.md)); working-state files like the weekly
tracker are the deliberate exception, because they *are* mutable state.

## 6. Stale receipts after switching engagement

**Symptom:** the dashboard's validation receipts (DML, challenger, gates…)
describe the *previous* client after `input_data/` and the settings changed.

**Why:** receipts are read from artifacts on disk, and some artifacts live in
the persistent `output/DISCOUNT_PLAN/` working folder rather than a
timestamped run. This was a real bug for DML: a top-level copy of
`dml_results.json` "proved able to go stale across engagements and show a
previous client's verdict" (comment in `ui/app.py::_dml`) — the fix reads
the **current run's** `plan/dml_results.json`. The remaining
`DISCOUNT_PLAN/` artifacts (agreement, sensitivity, challenger report,
defense hold) are only refreshed by rerunning their producers.

**Fix:** after any engagement switch, **rerun the full monthly chain**
(Run Center "monthly_all": pipeline → … → outlier_audit, 14 steps). Every
receipt is rewritten from the new data; nothing merges. Archive the old
tracker state *before* the switch — the checklist is
[34 §New client](34-onboarding.md).

## 7. Backtest reports FAIL (not scoreable) — expected under 12 weeks

**Symptom:** step 10 prints
`[backtest] FAIL: no scoreable folds — not enough data for a rolling backtest.`
and the report is titled **"Rolling Backtest — FAIL (not scoreable yet)"**.

**Why:** `scripts/validation/backtest_rolling.py` skips any fold with fewer
than `MIN_TRAIN_WEEKS = 12` training weeks; the current Epigamia feed holds
10. With no scoreable fold, the script deliberately writes a FAIL report
instead of silence — an honest receipt is the product here.

**Fix:** none, and do not fake one. This is expected until the feed reaches
12+ weekly points; the backtest becomes scoreable on its own as weeks accrue.
Deliver with the FAIL receipt visible (the dashboard shows it), and never
hand-edit the verdict. If the backtest runs but the champion loses to a naive
benchmark, that is a *different*, genuinely bad result — see the report's
pooled-wMAPE table.

---

## Escalation heuristics

- **A crash with a clear message** is the system working (fail-loud policy):
  fix the named input, don't wrap it in try/except.
- **A wrong number with no crash** is the emergency. Check, in order: is the
  environment the pinned one (§3)? are the receipts from the current run
  (§6)? did a settings override silently *not* apply (blank value = default,
  §1)?
- After any fix: `pytest tests/ -m "not slow"`, then rerun from the earliest
  affected step.
