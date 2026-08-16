# 20 — Reliability

There is no cluster, no failover, no database, no retry queue. The system is plain
Python files on one small Windows machine (5.9GB RAM, ~1GB free), writing plain files.
"Reliability" here does not mean uptime — it means **a wrong number must never leave the
system silently**. Every mechanism below serves that one goal, in one of three ways:
stop loudly, degrade honestly, or make the blast radius of a mistake small.

Related: [19 — Testing](19-testing.md) (which of these guards are pinned by tests),
[21 — Observability](21-observability.md) (how a human sees the guards fire).

## 1. Fail-loud configuration (`settings_loader.py`)

Every script imports `v4_config`, which applies overrides from `config/settings.xlsx`
(or `.csv`). The loader's contract:

- An unknown key raises `SettingsError` and suggests the nearest real key.
- All problems in a file are reported in one error ("2 problem(s)"), not one at a time.
- **A file with any error applies nothing** — no half-applied configuration.
- Type coercion handles Excel realities (`240.0` → `int`, `"1,200"` → 1200, float SKU
  ids stripped of `.0`).
- The percent-vs-fraction footgun is a hard error: `DEFAULT_BUDGET_PCT_CAP,12` is
  rejected with the message to write `0.12`, because accepting "12" as 1200% would make
  budget caps never bind.
- Uploads through the dashboard are validated as bytes before anything touches disk
  (`validate_bytes` / `install_bytes`), and installing one format removes the stale
  sibling so there is exactly one source of truth.

The consequence that matters most: a broken settings file **stops the run** rather than
silently dropping `STRATEGIC_SKUS` hero protection (pinned by
`tests/test_hero_shield.py::test_broken_settings_file_raises_rather_than_unprotecting`).

## 2. Fail-loud input validation (`stage1_ingestion/validate.py`)

- `validate_columns` raises with the missing column names and the columns actually
  found, so a misaligned client export dies at the door with an actionable message.
- `validate_quality` hard-fails on fatal states (zero rows after the brand filter, no
  parseable dates, fewer than 2 SKU×city cells) and returns *soft* warnings for
  survivable ones (out-of-range discounts, negative units).
- Named data-quality checks (unexplained demand spikes vs promo-excused ones,
  price-above-MRP, price/discount-field disagreement, sales at zero availability, SKU
  identity churn) warn rather than fail, and degrade quietly when optional columns are
  absent.
- `filter_own_brand` (`stage1_ingestion/ingest.py`) fails loud on zero matches and, in
  strict mode, on a pattern that over-matches two genuinely different brands — the two
  ways a wrong `BRAND_NAME` could silently produce a wrong model.

## 3. Fit-sanity ladders with prior fallbacks (`stage4_model/elasticity.py`)

The per-category fixed-effects regression can fail in ways that look like success:
RLM's IRLS can diverge, and rank-deficient fits keep finite in-sample predictions while
exploding out-of-sample. The defense is a ladder, each rung checked by `_fit_is_sane`:

1. **RLM (Huber)** on the dummy-FE formula.
2. **OLS** on the same formula if RLM diverges or errors.
3. **Within-FE (FWL) transform** (`_fit_category_within`) — the same fixed-effects
   model with cell effects absorbed by demeaning — if the dummy matrix would exceed
   the `_FE_DUMMY_BUDGET_MB = 32.0` estimate or either fit hits `MemoryError`. This is
   not an approximation: FWL yields identical OLS coefficients with a cells-free design
   matrix, and it exists because the real machine threw `MemoryError: Unable to
   allocate 86.2 MiB` on the dominant category, which silently pushed all its cells
   onto the generic default.
4. **Category prior**: if every fit is degenerate the category is skipped and its cells
   fall to the robust per-cell-median prior (`_category_robust_priors`).
5. **Global default** `-1.5` (`_global_default_elasticity`) as the last resort.

`_fit_is_sane` rejects: non-finite params, in-sample `|log-prediction| > 15`, and a
`log_price` standard error above 10 (an elasticity bounded in [-4, -0.3] with se≈9e4
carries no information). Individually-estimated cells are additionally shrunk toward
their category prior with effective prior weight `N_PRIOR = 60` observations, so thin
cells cannot carry wild slopes into recommendations.

## 4. Run-folder isolation (`pipeline.py`)

Every pipeline run writes to its own timestamped folder,
`output/runs/<YYYYMMDD_HHMMSS>/` (e.g. `output/runs/20260810_143823/`), containing
`fact_table.csv`, `features.csv`, `elasticity_estimates.csv`, `recommendations.csv`,
`outliers_removed.csv`, the dashboard HTML and the `plan/` folder. Consequences:

- A crashed or interrupted run can never corrupt a previous run; recovery is "run it
  again". There are no partial-write hazards across runs and no transactional storage
  to get wrong.
- Consumers (`ui/app.py::_latest_run`, the analysis chain, report builders) resolve the
  newest run folder at read time, so everything downstream reads one coherent snapshot.
- Memory discipline lives here too: `pipeline.py` drops the raw all-brand frame from
  the context after Stage 2 (`context.pop("raw_df")`) so Stage 4's fits get the RAM.

## 5. Acceptance gates as runtime checks (`scripts/analysis/validate_plan.py`)

The analysis chain has no unit tests ([19 — Testing](19-testing.md)); its check is the
gate script that must end **ALL PASS** before a plan is acted on: C1 (discount effect
isolated from OSA/SOV/competition), C2 (bucketing before action), C3 (every cut has
isolated marginal ROAS < 1), C4 (category fit floor), C5 (money reconciles line-by-line
to the reported total), C7 (out-of-sample R² ≥ 0.75), C8 (every banked cut category
confirmed by Double ML). It exits 1 on any failure. C6 — a business-ambition gate
against a savings target — was deliberately retired: the engine reports amounts,
never grades sufficiency.

## 6. Kill-switch (`scripts/tracker/killswitch.py`)

The weekly loop's automatic brake, enforcing "two weekly misses beyond tolerance →
revert the cell":

- A **strike** requires both a >5% volume miss vs prediction (`vol_tol_pct = 0.05`)
  and negative actual net revenue; a clean week resets the count; 2 strikes revert the
  cell and freeze it for 4 weeks (a real expiring window, not a latch).
- **Confounders are checked first**: if OSA or SOV collapsed >10% vs baseline that
  week, the week is excused entirely — blaming a cut for a stockout would revert good
  cells and destroy trust.
- **Only acted cells are judged** (`applied == True` and `week_action` in
  cut/reinvest): unacted holds carry no prediction we bet on, and judging them would
  fabricate phantom reverts and poison the drift denominator.
- **Portfolio drift brake**: with ≥30 scored cells and a latest-week direction
  hit-rate below 0.60, `block_new_cuts` goes up — existing reverts still fire, but no
  new cuts roll out until accuracy recovers.

Its `__main__` block is an executable smoke suite covering every branch.

## 7. Versioned deliverables (`scripts/reports/build_stage_workbook.py`)

Delivered files are immutable history. `_next_versioned_out()` scans
`output/STATIQ_STAGE_REPORT*.xlsx` and writes `_v<N+1>` — a rebuild can never
overwrite the workbook a client already has. The same policy applies to all delivered
artifacts (repo-wide convention; the wave KAM sheets in `output/DISCOUNT_PLAN/` follow
the `waveN_issued.csv` naming for the same reason).

## 8. Stale-receipt prevention

A receipt showing a previous run's verdict for this run's data is worse than no
receipt. Two concrete fixes encode the rule:

- `scripts/validation/backtest_rolling.py`: when no fold is scoreable, it **deletes**
  the old `backtest_folds.csv` and writes `BACKTEST_REPORT.md` with an explicit
  `FAIL (not scoreable yet)` headline, instead of leaving the previous verdict in
  place. (The current honest state: FAIL — each fold needs 12 training weeks, the feed
  has 10.)
- `ui/app.py`: the Double ML receipt reads `dml_results.json` from the **current
  run's** `plan/` folder, because a top-level copy once went stale across engagements
  and showed a previous client's verdict.

## 9. Dashboard containment (`ui/app.py`)

The stdlib HTTP dashboard binds to `127.0.0.1:8765` only; the run endpoint accepts
only step ids from the fixed `STEPS` allowlist (never arbitrary commands); one job runs
at a time. A failed step reports its exit code and stops the sequence.

## What deliberately does not exist

No retries (a failed step is investigated, not retried), no backups beyond git for
code (input and output data live outside version control by design), no
high-availability anything. The recovery story for every failure class is the same:
the run folder from the last good run is intact, the guards above make the failure
loud, and the human reruns after fixing the cause.
