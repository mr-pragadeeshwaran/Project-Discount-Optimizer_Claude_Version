# 30 — Code Organization

**Audience:** engineers making changes to this repo.
**Scope:** what lives where, the naming rules the codebase actually follows, and where a
new piece of code should go. The overall shape of the system is in
[`../TECHNICAL/10-system-architecture.md`](../TECHNICAL/10-system-architecture.md);
known problems are catalogued honestly in
[`31-technical-debt.md`](31-technical-debt.md); the reasoning behind the structural
choices is in [`35-architecture-decisions.md`](35-architecture-decisions.md).

Everything runs from the repo root (`D:\1. PROJECT\Stat IQ Lab`). All commands assume
that working directory; scripts locate the root themselves via
`os.path.abspath(os.path.join(HERE, "..", ".."))` so they also work when invoked by
absolute path.

## Directory map

| Path | Purpose |
|---|---|
| `pipeline.py` | Master orchestrator for the 8-stage foundation build. Runs `stage1..stage8`, writes a timestamped run folder under `output/runs/`. |
| `v4_config.py` | Code-side defaults for every knob (costs, caps, hero SKUs, competitor brands). The name is legacy; it is *the* config module. Values are overridden by `config/settings.xlsx`. |
| `settings_loader.py` | Loads and validates `config/settings.xlsx` against a typed registry; raises `SettingsError` on any bad value (fail-loud — a broken settings file must never silently fall back). |
| `stage1_ingestion/` … `stage8_output/` | The 8 pipeline stages, one package each: `ingest.py`/`validate.py`, `prepare.py`, `features.py`, `elasticity.py`, `curves.py`, `economics.py`, `guardrails.py`, and `stage8_output/` (`excel_report.py`, `leakage.py`, `track_record.py`, `waste_reinvest.py`). Note: `stage8_monitoring/` also exists but contains only an empty `__init__.py` — vestigial; `pipeline.py` imports from `stage8_output`. |
| `scripts/analysis/` | The champion analysis chain: `discount_plan.py` (champion waste model), `dml_estimate.py` (Double ML confirmation), `validate_plan.py` (gates C1–C5, C7, C8), `challenger.py` (competitor-controls challenger + defense holds), `competitor_features.py`, `optimize_plan.py`, `unlock_estimate.py`, `build_report.py`. |
| `scripts/pricing/` | Engine B: `pricing_engine.py` (also *produces* the two-engine `agreement.csv`), `budget_allocator.py`, `scenario_menu.py`, `budget_glide.py`, plus the supporting stack (`pricing_panel.py`, `elasticity_bayes.py`, `elasticity_hier.py`, `de_optimizer.py`, `constraints_lib.py`, `cross_price_v2.py`, `whatif.py`, `prior_store.py`). |
| `scripts/promo/` | `promo_calendar_milp.py` + `promo_constraints.json`. |
| `scripts/validation/` | Out-of-band honesty checks: `backtest_rolling.py`, `elasticity_gates.py`, `sensitivity.py`, `outlier_promo_audit.py`. |
| `scripts/tracker/` | The weekly loop: `weekly_tracker.py` (orchestrates, *consumes* `agreement.csv` and `defense_hold.csv`), `killswitch.py`, `guardrail.py`, `actuals.py`, `scorecard.py`, `seasonality.py`, `workbook.py`, `params_review.py`, `verify_loop.py` (end-to-end loop simulation). |
| `scripts/reports/` | Deliverable builders: `build_stage_workbook.py` (versioned `STATIQ_STAGE_REPORT_v<N>.xlsx`), `build_wave_kam_sheet.py` (Monday KAM handoff sheet). |
| `scripts/diagnostics/` | Throwaway data-quality probes. Explicitly disposable per `scripts/README.md`. **Frozen with 24 Mantra-era constants** — see [debt item 7](31-technical-debt.md). |
| `scripts/experiments/` | Model-comparison harnesses from the May 2026 Stage-4 rewrite. Re-run only when considering a structural model change. |
| `ui/` | The dashboard: `app.py` (stdlib HTTP server, `127.0.0.1:8765`, fixed step allowlist), `index.html` (single page), `action_plan.py`. Started by `launch_ui.bat` or `.claude/launch.json`. |
| `tests/` | Pytest suite (`test_*.py` + `conftest.py`). `pytest tests/ -m "not slow"` is the fast gate (67 pass); `slow` marks tests that train models (`pytest.ini`). |
| `config/` | `settings.xlsx` (the live engagement's knobs — brand, platform, competitors, caps, festival dates) plus the blank templates (`SETTINGS_TEMPLATE.*`, `FESTIVALS_TEMPLATE.csv`, `PLATFORM_EVENTS_TEMPLATE.csv`). |
| `input_data/` | Raw platform CSV exports (currently three Epigamia/Blinkit monthly files). Git-ignored — proprietary, never committed. |
| `output/` | All generated artifacts. Git-ignored **except** `output/README.md` and `output/DISCOUNT_PLAN/` (tracker state, blessed plan, issued waves). `output/runs/<YYYYMMDD_HHMMSS>/` holds one immutable folder per pipeline run. |
| `data/` | `master/` and `processed/` — currently empty placeholders, git-ignored. |
| `dashboard/` | `dashboard_generator.py` — the per-run `BRAND_DASHBOARD.html` writer invoked by the pipeline (distinct from `ui/`, which is the live server). |
| `docs/` | The current documentation home: `BUSINESS/`, `TECHNICAL/`, `ENGINEERING/` (this folder). |
| `doc/` | The **older** doc tree (`legacy/`, `reference/`, `pdf/`, `assets/`). Valuable for mechanism; parts are pinned to the previous 24 Mantra engagement — see [31-technical-debt.md](31-technical-debt.md). |
| `archive/` | Git-ignored local junk drawer (old tracker state, marketing files, superseded reports). Safe to delete; nothing in code references it. |
| `SALES_KIT/` | Sales/outreach materials (tracked). Not code. |
| `run.bat`, `launch_ui.bat` | One-click entry points: full pipeline + open the weekly report; start the dashboard. Both prefer `.venv\Scripts\python.exe` and fall back to `python` on PATH. |

## Naming conventions (as practiced)

- **Stage packages:** `stage<N>_<purpose>/` containing one main module named for the job
  (`elasticity.py`, `guardrails.py`), plus `__init__.py`.
- **Modules and functions:** `snake_case` throughout. Private helpers are
  `_underscore_prefixed` (`_fit_category_within`, `_next_versioned_out`,
  `_competitor_weekly`).
- **Script names say what they produce or check:** `build_*` for deliverable builders,
  `*_gates`/`validate_*` for pass-fail checks, `verify_*` for end-to-end proofs, `diag*`
  for throwaway probes.
- **Module-level tunables:** `SCREAMING_SNAKE` constants near the top with an inline
  comment per knob (see the tunables block in `scripts/analysis/discount_plan.py`).
- **Deliverables:** `SCREAMING_SNAKE.xlsx/.md` (`STATIQ_STAGE_REPORT_v3.xlsx`,
  `WEEKLY_TRACKER.xlsx`, `CHALLENGER_REPORT.md`). Delivered files are versioned `_v<N>`,
  never overwritten (see
  [ADR-6](35-architecture-decisions.md#adr-6--versioned-immutable-deliverables)).
- **Run folders:** `output/runs/<YYYYMMDD_HHMMSS>/` — sortable, immutable.
- **Every generated table leads with `product_id` (and `cell_id`)** so any row is
  joinable back to the catalog (commit `c4eeed6`).
- **Brand/platform are settings, never literals.** `BRAND_NAME` / `PLATFORM_NAME` come
  from `config/settings.xlsx` via `settings_loader.py`. Grep-check before committing: a
  hardcoded "Epigamia" or "Blinkit" outside config/tests is a bug.
- **Docstrings carry the design rationale.** The header docstring of each analysis
  script states what it does, *why* it does it that way, and its exact inputs/outputs
  (see `challenger.py`, `backtest_rolling.py`, `killswitch.py`). This is the house style
  — the docs point to these docstrings rather than duplicating them.
- **Tests:** `tests/test_<area>.py`; anything that trains a model gets
  `@pytest.mark.slow`.

## Where new code goes

- **A change to how the foundation data is built or modeled** → the relevant
  `stage<N>_*` package. Stage 4 model changes should first run against
  `scripts/experiments/` harnesses.
- **A new analysis on top of a run** (reads `output/runs/<ts>/fact_table.csv`, writes to
  the run's `plan/` or `output/DISCOUNT_PLAN/`) → `scripts/analysis/`. Follow the
  resident pattern: locate the newest run yourself, import the champion read-only via
  `importlib` if you need its panel/models (as `challenger.py` and `backtest_rolling.py`
  do), never edit the champion in place.
- **Pricing/optimizer work** → `scripts/pricing/`. If it changes what the tracker may
  execute, it must speak through `DISCOUNT_PLAN/pricing/agreement.csv`, not around it.
- **A new honesty check** → `scripts/validation/`; a new weekly-loop behavior →
  `scripts/tracker/`.
- **A new client-facing workbook or sheet** → `scripts/reports/`, using
  `_next_versioned_out`-style versioning from day one.
- **One-off investigation** → `scripts/diagnostics/` (disposable) or the session
  scratchpad — never the repo root.
- **If a script belongs in the operator's flow**, register it in the `STEPS` allowlist
  in `ui/app.py` and slot it into `MONTHLY_ORDER` (or the weekly group). The Run Center
  only executes allowlisted steps.
- **Generated files** always land in `output/` (git-ignored by default; only
  `DISCOUNT_PLAN/` is tracked). Never write deliverables to the repo root.
- **Every new setting** gets three homes: a default in `v4_config.py`, a typed row in
  the registry in `settings_loader.py`, and a line in `config/SETTINGS_TEMPLATE.xlsx`.
  Validation must fail loud.
- **Docs:** engineer-facing docs go here (`docs/ENGINEERING/`); do not extend
  `docs/legacy` or `docs/reference` — they are frozen history.

## What deliberately does not exist

There is no `src/` layout, no packaging (`pyproject.toml`), no CI pipeline, and no
deployment target: the product *is* this working directory on one machine, run via
`run.bat`/`launch_ui.bat` inside the pinned `.venv` (`requirements.txt` — numpy is
pinned at 1.26.4 with a comment explaining the breakage history). The trade-offs of that
choice are recorded in
[ADR-1](35-architecture-decisions.md#adr-1--file-based-no-database-design) and
[ADR-9](35-architecture-decisions.md#adr-9--local-only-no-auth-dashboard), and its costs
are tracked honestly in [31-technical-debt.md](31-technical-debt.md).

