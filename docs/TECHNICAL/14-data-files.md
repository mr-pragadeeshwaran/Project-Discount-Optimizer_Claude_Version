# 14 — The Data Layer (files, not a database)

*Audience: engineers. Verified against the repo on 2026-08-16
(live run `output/runs/20260810_143823`, Epigamia on Blinkit).*

This project has **no database**. There is no schema migration, no ORM, no
connection string anywhere in the codebase. The equivalent is a file-based
data layer with strict conventions: platform CSV/XLSX exports in, immutable
timestamped run folders out, one tracked "working state" folder for the weekly
loop, and a spreadsheet as the configuration registry. Everything the
dashboard shows ([13 — the HTTP API](13-api.md)) is read live from these files.

The layers, in data-flow order:

```
input_data/                 platform exports (gitignored, proprietary)
config/settings.xlsx        the engagement's settings registry (tracked)
data/master/sku_costs.csv   optional per-SKU costs (absent → defaults)
        │  pipeline.py (stages 1–8)
        ▼
output/runs/<stamp>/        immutable per-run artifacts (gitignored)
        │  analysis chain (champion → DML → gates → … → tracker)
        ▼
output/DISCOUNT_PLAN/       the live plan + weekly-loop state (tracked)
output/STATIQ_STAGE_REPORT_vN.xlsx   versioned deliverables (gitignored)
```

## 1. Input layer: `input_data/`

Stage 1 (`stage1_ingestion/ingest.py`, `ingest_all_sales`) globs
`input_data/*.csv` and `*.xlsx`, skipping lock files (`~` prefix) and the
SKU-master metadata file (basenames containing `my sku` / `sku list`). The
live files are monthly Blinkit "RCA" exports, e.g.
`Epigamia_blinkit-rca-download_July_2026.csv`.

### The RCA export format and `RCA_RENAME`

CSVs arrive with the platform's human-readable headers. `RCA_RENAME` (top of
`stage1_ingestion/ingest.py`) maps them to the canonical raw names that
`v4_config.COL` defines; unlisted columns pass through unchanged, so the older
`.xlsx` format (already in canonical names) loads with no rename.

| RCA export column | canonical raw column | `cfg.COL` key |
|---|---|---|
| `Product ID` | `PRODUCT_ID` | `product_id` |
| `Platform` | `GC_PLATFORM` | `platform` |
| `Date` | `DATE` | `date` |
| `Product Title` | `TITLE` | `title` |
| `City` | `GC_CITY` | `city` |
| `Brand` | `BRAND` | `brand` |
| `Grammage` | `GRAMMAGE` (already canonical) | `grammage` |
| `Offtake (MRP)` | `OFFTAKE_MRP` | `offtake_mrp` |
| `Offtake (Qty)` | `OFFTAKE_QTY` | `offtake_qty` |
| `Selling Price` | `PRICE` | `price` |
| `MRP` | `MRP` (already canonical) | `mrp` |
| `Wt. OSA %` | `WT_AVAILABILITY_PCT` | `availability` |
| `Wt. Discount %` | `WT_DISCOUNT_PCT` | `discount_pct` |
| `Est. Category Share` | `MONTHLY_CAT_SHARE_MRP` | `cat_share` |
| `Overall SOV` | `MONTHLY_OVERALL_SOV` | `overall_sov` |
| `Organic SOV` | `MONTHLY_ORGANIC_SOV` | `organic_sov` |
| `Ad SOV` | `MONTHLY_AD_SOV` | `ad_sov` |
| `Wt. PPU` | `WT_AVG_PPU_X100` | `wt_avg_ppu` |
| `Category` | kept as-is (`Category`) | — (see category modes) |

Ingestion is memory-conscious (the dev machine has ~1 GB free RAM): CSVs are
read in 200k-row chunks, renamed, filtered to own-brand rows, and trimmed to
recognised columns per chunk (`_read_source_own`) before concatenation.

### Fail-loud validation (`stage1_ingestion/validate.py`)

- `validate_columns` — **hard fail** if any of `HARD_REQUIRED` is missing
  (mapped via `cfg.COL`): `product_id, city, date, offtake_qty, mrp,
  discount_pct, title`. `SOFT_OPTIONAL` columns (`grammage, availability,
  ad_sov, competitor_price, price, offtake_mrp, brand`) are defaulted with a
  printed note when absent (RCA has no competitor price — RPI defaults to 1).
- `validate_quality` — hard fail on zero rows, no parseable dates, or <2
  cells; warn-level checks for negatives, out-of-range discounts,
  unexplained spikes, price/discount inconsistency, and SKU-identity churn.

### Cell identity

A **cell** is `(PRODUCT_ID, GRAMMAGE, City)`; a row is a cell-day. Grammage is
normalised to a canonical string (`500`, `'500 g'`, `'500g'` → `500g`;
`1000` → `1kg`) *before* dedup so pack variants never merge. Dedup keeps the
last row per `(PRODUCT_ID, GRAMMAGE, GC_CITY, DATE)`. Downstream, `cell_id`
strings look like `540432_250ml_Chennai`. Categories come from the platform
`Category` column when `CATEGORY_MODE = "column"` (the live setting), else
auto-derived from titles or an explicit keyword map. Own-brand filtering
matches `BRAND_NAME` / `OWN_BRAND_PATTERNS` on word boundaries with loud
over-match and under-match guards.

## 2. Config layer: `config/settings.xlsx` and the REGISTRY

Every engagement-owned knob lives in a **file**, not in code.
`settings_loader.py` defines a `REGISTRY` of every settable key —
`(key, type, section, description)` — in four sections: *Business targets*,
*Brand identity*, *Cost structure*, *Model and guardrails*. Defaults stay in
`v4_config.py` (single source of truth); the loader applies file overrides
onto `v4_config`'s globals at import time, so all consumers keep reading
`cfg.WHATEVER` unchanged. `BRAND_NAME` and `PLATFORM_NAME` are settings —
never hardcoded.

Accepted files (either format; **xlsx wins** if both exist, with a warning):

- `config/settings.xlsx` — sheets `Settings` | `Festivals` | `Platform Events`
  (the live engagement uses this)
- `config/settings.csv` + `config/festivals.csv` + `config/platform_events.csv`

Rules enforced by the loader (all fail-loud, raising `SettingsError` on
`import v4_config`):

- Typed parsers per key: `fraction` rejects the 12-vs-0.12 percent mix-up with
  a "did you mean 0.12?" hint; `list_id` keeps SKU ids as strings (Excel turns
  `532393` into `532393.0`); errors are **collected** so one edit round fixes
  them all.
- Blank value = keep the code default; `none` / `[]` = explicitly empty list.
- An **unknown key is an error**, not a silent no-op (catches typos), with a
  nearest-key suggestion.
- A Festivals / Platform Events sheet with rows **replaces** the code calendar
  outright.
- Templates (`SETTINGS_TEMPLATE.*`, downloadable from the dashboard) are
  *generated from the REGISTRY*, so they can never drift from what the code
  supports; the reader scans for the header row, so human notes above it
  survive a round-trip.
- Uploads via `POST /api/settings/upload` are dry-run validated in a temp dir
  (`validate_bytes`) and only ever written to the fixed
  `config/settings.{csv,xlsx}` path (`install_bytes`), deleting the
  other-format file so one source of truth remains.

There is deliberately **no savings-target key** in the REGISTRY: the engine
reports confident amounts with spend-share context; sufficiency is a contract
question, not a setting. Cost knobs (`DEFAULT_COGS_PCT` etc.) exist for
internal guardrails only — no COGS/margin number reaches a user-facing surface.

`data/master/sku_costs.csv` is an optional per-SKU cost override; when absent
(the normal case) stage 6 uses the configured defaults.

## 3. Run folders: `output/runs/<YYYYMMDD_HHMMSS>/`

Each `pipeline.py` execution writes a fresh timestamped folder
(`v4_config.OUTPUT_DIR`); "latest run" everywhere means the lexicographic max
of `output/runs/2026*`. Runs are treated as immutable — the analysis chain
reads them, never edits them. Contents of the live run `20260810_143823`
(699 modeled cells, 91 products, 8 categories):

| File | What it is |
|---|---|
| `fact_table.csv` (~19 MB) | The cleaned cell-day panel — the modeling substrate and the `@latest_fact` the tracker scores against. |
| `features.csv` (~44 MB) | Engineered features per cell-day (stage 3). |
| `outliers_removed.csv` | Per-cell z-score outlier days excluded from training, kept for audit (`outlier_promo_audit` cross-checks them). |
| `elasticity_estimates.csv` | Per-category/cell elasticity fits (stage 4). |
| `recommendations.csv` | Per-cell optimal discount/price, estimated units/revenue, confidence tier + score — the dashboard's price board. |
| `waste.csv`, `reinvest.csv` | Stage-8 raw cut/reinvest candidates. |
| `per_cell_detail.json` | Full per-cell diagnostics. |
| `BRAND_DASHBOARD.html`, `WASTE_REINVEST_REPORT.{md,xlsx}` | Self-contained run report surfaces. |
| `plan/all_cells.csv` | The decision engine's verdict for every cell (buckets: `c_waste_cut` etc.), written by `scripts/analysis/discount_plan.py`. |
| `plan/cut_list.csv`, `plan/reinvest_list.csv` | The two act-now lists. |
| `plan/plan_summary.json` | Headline numbers incl. the MODEL v2.1 formula string, `achievable_savings_mo_allconf`, observed discount spend. |
| `plan/dml_results.json` | Double-ML confirmation per cut category — read from the **current run** by the dashboard (staleness was a real bug; see 13). |

Every generated table leads with `product_id` (and `cell_id` where cells are
the grain) so any row can be joined or looked up without guessing.

## 4. `output/DISCOUNT_PLAN/` — the live plan and weekly-loop state

Unlike `output/runs/`, this folder is **tracked in git** (it is the current
plan of record plus its receipts). Structure:

- **Top level** — plan narrative and state: `PLAN.md`, `CHALLENGER_REPORT.md`,
  `defense_hold.csv` (cells held out of the cut wave), `cut_list.csv`,
  `reinvest_list.csv`, `competitor_features.csv`, `MEASUREMENT_SPEC.md`,
  `DATA_GAPS.md`, `PARAMS_REVIEW.md` + `params_history.json` (governance
  snapshots of every decision knob).
- **Weekly loop state** — `WEEKLY_READOUT.md`, `WEEKLY_TRACKER.xlsx`,
  `execution_log_template.csv` (the KAM handoff:
  `week, cell_id, product_id, city, recommended_action, recommended_disc,
  applied`), `tracker_history.csv`, plus `baselines.json` and
  `execution_log.csv` when the loop is mid-cycle. These three state files are
  exactly what the dashboard's self-test reset deletes (`_reset_state` in
  `ui/app.py`).
- **Wave tests** — `wave1_issued.csv` (built by
  `scripts/reports/build_wave_kam_sheet.py`): the issued Mon 17 Aug wave,
  columns `issued, apply_week, type, wave, product_id, cell_id, city,
  from_disc, to_disc, units_wk_now, pred_units_wk, strike_units_wk` — the
  kill-switch strike threshold travels with the handoff.
- **`pricing/`** — the second engine's outputs: `elasticities.csv`,
  `pricing_reco.csv`, `agreement.csv` (the two-engine agreement the tracker
  requires), `gates.json`, `budget_allocation.csv`, `budget_glide*.csv`,
  `scenario_menu.csv`, `roi_ladder.csv`, cross-price artifacts, `priors.json`,
  and the `BUDGET_PLAN` / `BUDGET_GLIDE` / `SCENARIO_MENU` / `PRICING_PLAN`
  markdown reports. `pricing/history/<runstamp>/` snapshots each pricing run
  locally but is **gitignored** (local audit trail only).
- **`promo/`** — `PROMO_CALENDAR.md`, `promo_calendar.csv`,
  `promo_solver_report.csv` (the MILP's 12-week calendar).
- **`validation/`** — the receipts: `BACKTEST_REPORT.md` (+
  `backtest_folds.csv` once the feed is long enough to score),
  `ELASTICITY_GATES.md` + `elasticity_validation.json`,
  `SENSITIVITY_REPORT.md` + `sensitivity_cells.csv`, `OUTLIER_AUDIT.md` +
  `outlier_promo_audit.csv`.

## 5. Versioned deliverables

Delivered files are immutable history. `scripts/reports/build_stage_workbook.py`
(`_next_versioned_out`) never overwrites: each build writes
`output/STATIQ_STAGE_REPORT_v<N+1>.xlsx`, with the original unversioned file
counting as v1. The same rule applies to anything handed to the client — a
new build means a new `_vN`, never an edit in place.

## 6. Gitignore boundaries (`.gitignore`)

The commit boundary encodes the data policy:

- `input_data/` — **never committed** (proprietary platform exports).
- `/output/*` — ignored wholesale, with two carve-outs: `!/output/README.md`
  and `!/output/DISCOUNT_PLAN` + `!/output/DISCOUNT_PLAN/**` (the tracked plan
  of record). `output/runs/` therefore stays local, as do all generated
  deliverables (`STATIQ_STAGE_REPORT*`, learning docs, sales-deck assets).
- `/output/DISCOUNT_PLAN/pricing/history/` — re-ignored *inside* the tracked
  folder (run-stamped local snapshots).
- `data/`, `archive/`, `.venv/`, `.claude/`, `__pycache__/`,
  `experiment_results*.csv`, `scratch_*.log`, `ACTION_PLAN_all_products.*` —
  local-only.

Net effect: the repo carries **code + settings + the current plan and its
receipts**; raw data and regenerable bulk stay on the operator's machine,
which is also the product's privacy posture (local-only, no cloud).

Related reading: [13 — the HTTP API](13-api.md) (which endpoints read which
files), [docs/README.md](../README.md) (doc map),
[BUSINESS/04-business-architecture.md](../BUSINESS/04-business-architecture.md)
(the same layers in business language).
