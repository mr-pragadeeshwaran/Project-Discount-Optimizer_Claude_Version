# 32 — Change Guide: how to make common changes safely

*Audience: engineers. Verified against the repo on 2026-08-16 (Epigamia on
Blinkit, run `output/runs/20260810_143823`). When something breaks while
following this guide, see [33 — Troubleshooting](33-troubleshooting.md);
if you are brand new, start with [34 — Onboarding](34-onboarding.md).*

## The one rule before anything else

```
pytest tests/ -m "not slow"
```

Run this **before every commit**. It is 67 fast tests (brand filtering,
settings parsing, hero shield, leakage, input validation — see `tests/`)
and it is the only automated gate this project has: **there is no CI/CD**.
The `slow` marker (defined in `pytest.ini`) covers tests that train models;
run the full `pytest tests/` when you touched `stage4_model/` or the pricing
scripts. A green fast suite is the merge bar; a red one means stop.

There is also no deployment pipeline: the repo *is* the deployment. "Shipping"
a change means committing it and rerunning the affected chain from the Run
Center. Delivered artifacts are never patched in place — see the versioning
policy below.

---

## 1. Add a settings knob (end-to-end)

Every knob an engagement owner may set lives in the `REGISTRY` list in
`settings_loader.py`. The design: `v4_config.py` holds the **default**,
`config/settings.xlsx` (or `.csv`) holds the **override**, and consumers only
ever read `cfg.KEY` via `import v4_config as cfg`.

1. **Default** — add `MY_KNOB = <default>` to `v4_config.py`. Defaults live
   *only* there (the registry deliberately carries no defaults, so there is
   exactly one source of truth).
2. **Registry** — add a `(key, type, section, description)` tuple to
   `REGISTRY` in `settings_loader.py`. `type` must be one of the `PARSERS`
   keys: `text`, `integer`, `number`, `fraction` (0–1, rejects the 12-vs-0.12
   percent mix-up), `percent` (0–100), `yes_no`, `list_text`, `list_id`
   (IDs kept as strings — Excel turns `532393` into `532393.0`).
   Write the description for the person editing the spreadsheet; it appears
   verbatim in the template.
3. **Template** — nothing to do. The downloadable template
   (`GET /api/settings/template` on the dashboard) is *generated from the
   REGISTRY* (`template_csv` / `template_xlsx_bytes`), so it cannot drift.
4. **Consumer** — read `cfg.MY_KNOB` wherever it is used. Never import
   `settings_loader` from engine code; overrides are applied once at
   `v4_config` import time (`apply_to`).
5. **Test** — add a parse/override case to `tests/test_settings.py`, then run
   the fast suite.

Two registry policies to respect: an **unknown key is an error**, not a silent
no-op (typos fail loud with a "did you mean" hint), and there is deliberately
**no savings-target key** — the engine reports achievable amounts, it never
grades sufficiency.

## 2. Add a Run Center step

The dashboard's execute page is driven entirely by the `STEPS` dict at the top
of `ui/app.py`. This dict is also the **security model**: `POST
/api/run/<step_id>` accepts only ids that are keys of `STEPS` (plus
`monthly_all`) — never arbitrary commands. Keep it that way.

1. Add an entry to `STEPS`:

   ```python
   "my_step": {"group": "monthly",            # or "weekly" / "governance"
               "label": "14. My new step",
               "desc": "One plain-English sentence for the button.",
               "cmd": ["scripts/foo/my_step.py", "--flag", "value"]},
   ```

   `cmd` is list-form argv, executed as `python -X utf8 <cmd>` from the repo
   root with stdout streamed into the live log. Two placeholders exist:
   `"@latest_fact"` resolves to the newest run's `fact_table.csv`, and
   `"#reset_state"` (only valid inside a `"then"` chain) deletes the tracker
   state files. A `"then"` key chains follow-up commands (see the `selftest`
   step for the pattern).
2. If the step belongs to the monthly rebuild, append its id to
   `MONTHLY_ORDER` **in dependency order** — `monthly_all` runs that list
   verbatim.
3. No frontend work: `GET /api/steps` returns `STEPS` + `MONTHLY_ORDER` and
   `ui/index.html` renders the buttons from it.
4. The step's script must exit non-zero on failure — the job runner marks the
   job `failed` on any non-zero return code, which is what the operator sees.

## 3. Add a report

Reports are standalone scripts under `scripts/reports/` that read finished
artifacts and write a deliverable to `output/`. Copy the pattern from
`scripts/reports/build_stage_workbook.py` or `build_wave_kam_sheet.py`:

- **Inputs**: the latest run folder (`output/runs/<ts>/`) and the working
  artifacts in `output/DISCOUNT_PLAN/`. Never recompute model results inside
  a report — reports render, engines compute.
- **Output location**: `output/` (git-ignored, except `output/DISCOUNT_PLAN/`).
  Never the repo root, never a temp dir.
- **Versioning — non-negotiable**: delivered files are immutable history.
  Reuse the `_next_versioned_out()` pattern (`build_stage_workbook.py`): each
  build writes `<NAME>_v<N+1>.xlsx`, scanning existing versions rather than
  overwriting. This also sidesteps Windows file locks — see
  [33 §5](33-troubleshooting.md#5-excel-file-locked--a-build-fails).
- **Columns**: every table starts with `product_id` (and `cell_id` where the
  grain is a cell), so rows are always look-up-able.
- Optionally wire the report in as a Run Center step (§2) so the operator can
  build it without a terminal.

## 4. Change a threshold

First question: **who owns the number?**

- **Engagement-owned** (budget cap, kill-switch tolerance, lookback window,
  ROI elbow, …): it is already in the `REGISTRY` — change it in
  `config/settings.xlsx`, Settings sheet, via the dashboard's upload flow
  (dry-run validated before install). Do **not** edit `v4_config.py` for a
  client-specific value.
- **Code default** (a new engagement should inherit the new value): edit the
  default in `v4_config.py`, keep the registry entry's description honest,
  and rerun the affected chain.

Either way, run the **Parameter review** governance step
(`scripts/tracker/params_review.py`, the `params` button): it snapshots every
decision knob into `output/DISCOUNT_PLAN/params_history.json` and renders the
drift since last sign-off in `PARAMS_REVIEW.md`, so a threshold change is a
recorded event, not a silent diff. Then rerun from the earliest affected step
(usually `champion` onward; a lookback change means the full `pipeline`) and
confirm the acceptance gates (`scripts/analysis/validate_plan.py`, C1–C5, C7,
C8 — C6 was deliberately retired) still pass.

## 5. Onboard a new platform export format

Stage 1 normalises platform exports through **one rename map**:
`RCA_RENAME` in `stage1_ingestion/ingest.py`, which maps the platform's
column headers (e.g. `"Offtake (Qty)"`, `"Wt. Discount %"`) to the canonical
names in `cfg.COL`. Unlisted columns pass through unchanged, which is why the
older `.xlsx` format still loads with no entries at all.

1. Add the new platform's header spellings to `RCA_RENAME`.
2. Drop a sample file in `input_data/` and run the pipeline. Two guardrails
   tell you what is missing, loudly:
   - `stage1_ingestion/validate.py::validate_columns` fails with a clear
     message if a **required** column never appeared;
   - optional columns the export lacks (e.g. competitor price) are created as
     `NaN` and features degrade gracefully (RPI defaults to 1).
3. Large all-brand CSVs are read in 200k-row chunks and brand-filtered per
   chunk — keep that path intact; it is what makes multi-GB exports fit in
   this machine's RAM.
4. Add a fixture-driven case to `tests/test_brand_filter.py` /
   `tests/test_validate.py` if the new format has quirks worth pinning.

Files whose names start with `~` (Office lock files) or contain
`my sku` / `sku list` are skipped by ingestion — don't fight that list,
extend it.

---

## Which doc to update, per change

Docs are part of the change, not an afterthought. The map:

| You changed… | Update |
|---|---|
| A settings knob (REGISTRY) | `docs/TECHNICAL/14-data-files.md` §2 (config layer); `docs/BUSINESS/03-business-logic.md` if it is a business rule |
| A Run Center step (`STEPS`) | `docs/TECHNICAL/13-api.md` (endpoints + allowlist); `docs/BUSINESS/02-user-journeys.md` (what the button does) |
| A report / output file | `docs/TECHNICAL/14-data-files.md` (output inventory); `output/README.md` |
| A threshold or gate | `docs/BUSINESS/03-business-logic.md`; note it in the next `PARAMS_REVIEW.md` sign-off |
| Ingestion / a new export format | `docs/TECHNICAL/14-data-files.md` (input layer) |
| Anything with a new term | `docs/BUSINESS/05-glossary.md` |
| Failure behaviour | [33 — Troubleshooting](33-troubleshooting.md) |
| Setup steps | [34 — Onboarding](34-onboarding.md) |

Then: `pytest tests/ -m "not slow"` — and only then commit.
