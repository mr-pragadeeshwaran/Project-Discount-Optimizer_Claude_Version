# 21 — Observability

There is no metrics stack, no log aggregator, no tracing, no alerting. This is a
local-only system operated by a human on a weekly cadence, and its observability model
is built around that fact: **every run leaves file artifacts, and the dashboard renders
those artifacts as receipts a human reads before acting**. If you are looking for the
classic three pillars, the honest mapping is: logs → stdout plus an in-memory UI ring
buffer, metrics → receipt files regenerated per run, alerting → a person reading the
weekly readout.

Related: [20 — Reliability](20-reliability.md) (the guards that produce these
signals), [19 — Testing](19-testing.md) (what is checked before runtime at all).

## 1. Run logs

- Every stage of `pipeline.py` and every script in the analysis chain prints a
  narrated, stage-by-stage log to stdout — including the reliability ladder's
  decisions (e.g. `stage4_model/elasticity.py` prints when a category switches to the
  within-FE transform, when a fit is rejected as degenerate, and the per-category
  priors used for shrinkage). The console transcript *is* the run log.
- When steps run through the dashboard, `ui/app.py`'s job runner streams each
  subprocess's stdout/stderr into an in-memory ring buffer
  (`deque(maxlen=6000)` in the `Job` class) and serves it live to the browser with
  progress and per-step OK/FAILED lines.
- **Logs are not persisted.** The UI buffer dies with the server process, and console
  output dies with the terminal. The durable record of a run is not its log but its
  artifacts (next section). This is a known gap, accepted because every number a log
  would justify is recomputed and re-receipted on the next run.

## 2. Run-folder artifacts as ground truth

Each pipeline run writes `output/runs/<timestamp>/` (latest:
`output/runs/20260810_143823/`, 699 modeled cells across 8 categories) containing the
full evidence chain: `fact_table.csv`, `features.csv`, `elasticity_estimates.csv`,
`recommendations.csv`, `outliers_removed.csv`, `per_cell_detail.json`,
`BRAND_DASHBOARD.html`, the waste/reinvest reports and the `plan/` folder
(`all_cells.csv`, `plan_summary.json`, `dml_results.json`). Any headline number can be
traced back to the row-level file that produced it, per run, forever — run folders are
never overwritten ([20 — Reliability §4](20-reliability.md)).

## 3. Dashboard receipts — the health surface

`ui/app.py::api_status` assembles the system's health view, rendered by
`ui/index.html` as pass/fail chips. Each receipt is recomputed from artifacts on every
request — there is no cached health state to go stale:

| Receipt | Source | Current state (2026-08-10 run) |
|---|---|---|
| Double ML | `<run>/plan/dml_results.json` (current run, never a top-level copy) | cut categories confirmed reliably-waste |
| Elasticity gates | `output/DISCOUNT_PLAN/validation/elasticity_validation.json` | 3/3 stages PASS |
| Sensitivity | `output/DISCOUNT_PLAN/validation/sensitivity_cells.csv` | 0 fragile cut cells (200-draw shake) |
| Competitor challenger | `output/DISCOUNT_PLAN/CHALLENGER_REPORT.md` | champion stands |
| Defense hold | `output/DISCOUNT_PLAN/defense_hold.csv` | cells held out of the cut wave |
| Backtest | `validation/backtest_folds.csv` / `BACKTEST_REPORT.md` | honest FAIL — needs 12 training weeks, feed has 10 |
| Confident savings | `<run>/plan/plan_summary.json` | amount + spend-share, never graded against a target |

Two deliberate honesty details: the backtest chip quotes the report's own headline so
"FAIL (not scoreable yet)" reads differently from "lost to the naive benchmark", and
the savings chip is informational — the engine reports the amount with spend-share
context and explicitly notes "sufficiency is a contract question".

The status payload also surfaces the operating context: latest run name, config knobs
in force (brand, budget cap, hero SKUs, lookback), input-file inventory with sizes and
dates, two-engine agreement counts (`pricing/agreement.csv`), and per-category savings.

## 4. Tracker scorecard — is the model actually right?

`scripts/tracker/scorecard.py` grades past predictions against actuals, week over
week, with honesty rules baked in: no look-ahead (only realized weeks are scored),
direction hit-rate, delta R², units MAPE, revenue bias in rupees, and cumulative
**realized** savings (sum of actual deltas — the number that hit the P&L, not the
predicted one). Acceptance-rate reporting distinguishes "execution log not returned"
(`None`) from "recommendations rejected" (0%) — not-confirmed is never counted as
refused. Results land in `output/DISCOUNT_PLAN/WEEKLY_TRACKER.xlsx` and the
plain-English `WEEKLY_READOUT.md`, which also carries the kill-switch alerts
(reverts, frozen cells, confounded weeks, portfolio-drift block) as its warning
section — the closest thing the system has to alerting.

## 5. Outlier audit trail

Data the model *refused to learn from* is as observable as data it used:

- Stage 2 (`stage2_preparation/prepare.py`) writes every removed spike to
  `<run>/outliers_removed.csv` with cell, date, z-score, direction and reason, and
  demotes those rows from training rather than deleting them.
- `scripts/validation/outlier_promo_audit.py` then cross-checks the removed days
  against documented explanations (stockout, deep promo, festival, platform event) and
  writes `output/DISCOUNT_PLAN/validation/outlier_promo_audit.csv` +
  `OUTLIER_AUDIT.md`. A high explained share is the receipt that the z-filter removes
  event distortion, not demand signal. It is advisory by design — it never alters the
  frozen training data.

## 6. Parameter drift

`scripts/tracker/params_review.py` snapshots every decision knob into
`output/DISCOUNT_PLAN/params_history.json` and renders `PARAMS_REVIEW.md` showing
drift since the last sign-off — configuration changes are observable events, not
silent state.

## Honest gaps

- **No metrics, no alerting, no pager.** Nothing pushes a notification when a receipt
  flips to FAIL; the process is human-in-the-loop, and the loop cadence is weekly. A
  regression between weekly reviews is invisible until someone looks.
- **Logs are ephemeral** (in-memory ring buffer / console only). Post-mortems
  reconstruct from artifacts, not logs.
- **No uptime monitoring** — irrelevant in the classic sense, since the dashboard is
  launched on demand (`launch_ui.bat`, bound to `127.0.0.1:8765`) and nothing runs
  unattended.
- **The health surface assumes the human reads it.** The mitigations are structural:
  receipts are recomputed from current-run artifacts on every view (no stale state to
  mislead), FAIL states are written explicitly rather than omitted, and the
  kill-switch acts mechanically even if nobody reads the readout that week
  ([20 — Reliability §6](20-reliability.md)).
