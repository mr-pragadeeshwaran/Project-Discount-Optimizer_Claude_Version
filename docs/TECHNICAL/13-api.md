# 13 — The HTTP API (`ui/app.py`)

*Audience: engineers. Verified against `ui/app.py` on 2026-08-16.*

There is no web framework, no auth layer, and no cloud deployment here — by
design. The "API" is a single-file, zero-dependency dashboard backend built on
Python's stdlib `http.server` (`ThreadingHTTPServer` + `BaseHTTPRequestHandler`),
plus pandas for reading artifacts. It exists so the operator can *see and run*
the system from a browser instead of a terminal.

- **Bind address:** `127.0.0.1` only — never `0.0.0.0`. The dashboard is
  unreachable from other machines, which is the whole authentication story.
- **Port:** env `UI_PORT`, default `8765`.
- **Start:** `python -X utf8 ui/app.py`, `launch_ui.bat`, or the
  `.claude/launch.json` entry. `GET /` serves `ui/index.html` (a single static
  file; all rendering is client-side against the JSON endpoints below).
- **Responses:** JSON (`application/json; charset=utf-8`) with an explicit
  `Content-Length`, except `/` (HTML) and the template downloads
  (`Content-Disposition: attachment`).

## Security model: the STEPS allowlist

The one dangerous capability — "run something" — is constrained three ways
(see the module docstring and `STEPS` / `start_job`):

1. **Allowlist, not commands.** `POST /api/run/<step_id>` accepts only ids that
   are keys of the fixed `STEPS` dict (plus the pseudo-id `monthly_all`).
   The request body is ignored; nothing from the client ever reaches a shell.
   Each step carries its exact command in **list form**
   (e.g. `["scripts/analysis/discount_plan.py"]`), executed as
   `subprocess.Popen([sys.executable, "-X", "utf8", *cmd], cwd=ROOT, shell
   never used)`.
2. **One job at a time.** A module-level `Job` (guarded by `JOB.lock`) refuses
   a second start while `status == "running"` — the endpoint answers `409`.
3. **Two resolved tokens only.** `@latest_fact` is replaced at run time with
   `<latest run>/fact_table.csv` (`_resolve`); `#reset_state` is an internal
   action (`_reset_state` deletes the three tracker state files under
   `output/DISCOUNT_PLAN/`), never a shell command.

The settings upload has the same shape of defense: the uploaded *filename* is
only used to pick csv-vs-xlsx; the write destination is always the fixed
`config/settings.{csv,xlsx}` path, and the payload is validated by
`settings_loader.validate_bytes` **before** anything is written
(see [14 — the data layer](14-data-files.md)).

### The step catalog

`STEPS` groups every runnable step by cadence. `GET /api/steps` returns this
verbatim plus `MONTHLY_ORDER` (the 14-step rebuild sequence used by
`monthly_all`).

| id | group | runs |
|---|---|---|
| `pipeline` | monthly | `pipeline.py` |
| `champion` | monthly | `scripts/analysis/discount_plan.py` |
| `dml` | monthly | `scripts/analysis/dml_estimate.py` |
| `gates` | monthly | `scripts/analysis/validate_plan.py` |
| `challenger` | monthly | `scripts/analysis/challenger.py` |
| `pricing` | monthly | `scripts/pricing/pricing_engine.py` |
| `budget` | monthly | `scripts/pricing/budget_allocator.py --budget_pct 0.12` |
| `promo` | monthly | `scripts/promo/promo_calendar_milp.py` |
| `scenarios` | monthly | `scripts/pricing/scenario_menu.py` |
| `glide` | monthly | `scripts/pricing/budget_glide.py` |
| `backtest` | monthly | `scripts/validation/backtest_rolling.py` |
| `elast_gates` | monthly | `scripts/validation/elasticity_gates.py --report-only` |
| `sensitivity` | monthly | `scripts/validation/sensitivity.py` |
| `outlier_audit` | monthly | `scripts/validation/outlier_promo_audit.py` |
| `recommend` | weekly | `scripts/tracker/weekly_tracker.py` |
| `score` | weekly | `scripts/tracker/weekly_tracker.py --actuals @latest_fact` |
| `selftest` | weekly | `scripts/tracker/verify_loop.py`, then `#reset_state`, then `weekly_tracker.py` |
| `params` | governance | `scripts/tracker/params_review.py` |

## GET endpoints

| Path | Purpose |
|---|---|
| `/`, `/index.html` | The single-page dashboard (`ui/index.html`). |
| `/api/steps` | `{steps: STEPS, monthly_order: [...]}` — drives the Run Center buttons. |
| `/api/status` | The headline payload: latest run, config snapshot, input files, tracker summary, plan summary, category savings, two-engine agreement, sensitivity summary, and the **receipts** array (see below). |
| `/api/job` | Live job snapshot: `{step, status: idle\|running\|done\|failed, rc, elapsed, log, done_steps, total_steps, current}`. The log is an in-memory `deque(maxlen=6000)` of streamed subprocess lines; the UI polls this. |
| `/api/settings` | Effective settings with provenance (`settings_loader.describe()`): every REGISTRY key, its live value, and whether it came from `file` or `default`. Reloads `v4_config` so an uploaded file shows up without a restart. A broken settings file returns `{ok: false, error}` instead of a blank page. |
| `/api/settings/template` | Settings template download. Suffix routing: `...template.xlsx` → generated workbook, `...template/festivals.csv`, `...template/platform_events.csv`, anything else → `settings.csv`. All generated live from `settings_loader.REGISTRY`, so templates cannot drift from code. |
| `/api/table/<name>` | Tabular JSON `{columns, rows}` read from real artifacts. Valid names: `cuts`, `reinvest`, `buckets`, `handoff`, `scenarios`, `sensitivity`, `history`, `plan_all`, `elasticity`, `prices`. Column sets are pinned by `TABLE_COLS_*`; every table leads with `product_id` / `cell_id` for lookup. |
| `/api/report/<key>` | Raw markdown text of a report file. Valid keys (the `REPORTS` map): `readout`, `budget`, `glide`, `backtest`, `sens`, `promo`, `chal`, `params`, `egates` — all resolved to files under `output/DISCOUNT_PLAN/`. |

### `/api/status` receipts — the anti-staleness rule

`api_status()` builds a `receipts` list of pass/fail chips (Double ML,
elasticity gates, sensitivity, challenger, defense hold, backtest, confident
savings). Two deliberate behaviors are worth knowing:

- **Receipts read CURRENT-run artifacts.** The DML chip reads
  `<latest run>/plan/dml_results.json`, *not* a top-level copy — a top-level
  copy once went stale across engagements and showed a previous client's
  verdict (the comment in `_dml` records this). Stale receipts are treated as
  bugs, not cosmetics.
- **Backtest verdict is computed, with an honest fallback.** If
  `output/DISCOUNT_PLAN/validation/backtest_folds.csv` exists, the chip pools
  wMAPE by model (weighted by `n_cellweeks`) and requires the champion to beat
  *both* naive benchmarks. Otherwise it falls back to the verdict line of
  `BACKTEST_REPORT.md` and **quotes the report's own headline**, so a
  "not scoreable yet" FAIL (feed too short) reads differently from a
  "lost to the naive" FAIL. There is no path that fabricates a PASS.
- **Confident savings is informational.** The chip reports the amount and its
  share of observed discount spend — there is deliberately no savings target
  to grade against (sufficiency is a contract question, not a setting).

Every panel value is wrapped in `_safe(fn, fallback)`: a missing or malformed
artifact degrades that one card to its fallback instead of failing the whole
status call.

## POST endpoints

### `POST /api/run/<step_id>`

Starts a job. No body. Responses:

- `200 {"ok": true, "message": "started"}` — a worker thread now runs the
  step's command(s) sequentially, streaming merged stdout/stderr into the job
  log with a `── <label>` header and a closing `OK <label> (<secs>s)` or
  `FAILED <label> (exit <rc>)` per command. Commands run with
  `cwd=ROOT`, `python -X utf8`, `PYTHONIOENCODING=utf-8`.
- `409 {"ok": false, "message": "A job is already running — …"}` — one at a time.
- `409 {"ok": false, "message": "Unknown step: <id>"}` — not on the allowlist.

`monthly_all` expands to all of `MONTHLY_ORDER` in order and stops at the
first non-zero exit (`status: "failed"`, `rc` = that exit code). A step's
optional `then` list (only `selftest` uses it) appends follow-up actions.

### `POST /api/settings/upload`

Body: `{"filename": "...", "content_b64": "..."}`. Flow (`_settings_upload`):

- `400` — missing/oversized body (hard 5 MB cap), undecodable JSON/base64,
  or the file fails `settings_loader` validation (the message names every bad
  cell; nothing is written).
- `409` — a job is running; settings may not change mid-run.
- `200 {"ok": true, "message": "Saved to config/… They take effect on the next run."}`
  — validated and installed to the fixed path; the other-format file is
  removed so exactly one source of truth remains.

## Error semantics (shared by all GET routes)

`do_GET` maps exceptions to statuses uniformly:

| Exception | Status | Body |
|---|---|---|
| `KeyError` (unknown table name) | 404 | `{"error": "unknown table '<name>'"}` |
| `FileNotFoundError` | 404 | `{"error": "not generated yet: <plain-English what>"}` |
| anything else | 500 | `{"error": "<str(e)>"}` |

The `FileNotFoundError` convention is load-bearing: readers call
`_need(path, what)` where `what` is a human sentence including the fix
(e.g. `"the cut list (run the monthly rebuild)"`), so a 404 tells the operator
*which button to press*, not which path was missing. Unknown report keys
return 404 with `{"error": "unknown report '<key>'"}` before touching disk.
Per-request console logging is silenced (`log_message` is a no-op).

## What does not exist (on purpose)

- **No authentication / sessions / CSRF** — loopback bind is the boundary;
  nothing here is exposed beyond the operator's own machine.
- **No database** — every endpoint reads plain files produced by the engine;
  see [14 — the data layer](14-data-files.md) for exactly which ones.
- **No arbitrary execution** — the allowlist above is the complete runnable
  surface.
- **No API versioning** — the only client is `ui/index.html`, shipped in the
  same directory and served by the same process.

Related reading: [docs/README.md](../README.md) (doc map),
[BUSINESS/02-user-journeys.md](../BUSINESS/02-user-journeys.md) (what each
dashboard button means to the operator).
