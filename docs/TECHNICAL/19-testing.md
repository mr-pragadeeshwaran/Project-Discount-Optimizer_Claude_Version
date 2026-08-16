# 19 — Testing

How the test suite is organized, what it actually covers, and — just as important —
what it deliberately does not cover yet.

Related: [20 — Reliability](20-reliability.md) (runtime guards that compensate for the
untested surface), [21 — Observability](21-observability.md) (how failures are seen when
they happen anyway).

## Running the suite

```
pytest tests/ -m "not slow"     # default: 67 tests, a few seconds
pytest tests/                   # adds 3 slow tests that train models (~seconds each)
```

Configuration is `pytest.ini` at the repo root: `testpaths = tests`, `addopts = -q`, and a
single custom marker `slow` ("tests that train models"). `tests/conftest.py` does exactly
one thing — inserts the repo root into `sys.path` so `import v4_config` and friends work
under pytest without installing the project as a package.

There is no CI. Tests run manually on the single dev/deploy machine (this is a
local-only product — see [20 — Reliability](20-reliability.md) for the deployment model).
There is no coverage measurement.

## Test map

The suite is small and opinionated: every file pins a **failure mode that was actually
observed or is onboarding-critical**, using tiny synthetic DataFrames — no fixtures from
real client data.

### `tests/test_settings.py` — settings round-trips (28 tests)

Targets `settings_loader.py`. Every script does `import v4_config as cfg`, so a settings
file that parses wrong is a whole-system defect. Coverage:

- Value plumbing: integer knobs override defaults, blank cells keep defaults, Excel's
  `240.0` becomes `int 240`, thousands separators (`"1,200"`) parse.
- Fail-loud on typos: an unknown key raises `SettingsError` *and suggests the real key*;
  all problems in a file are reported at once; a partially-bad file applies **nothing**
  (no half-applied config).
- The percent-vs-fraction footgun: `DEFAULT_BUDGET_PCT_CAP,12` (meaning 12%) is rejected
  with a hint to write `0.12` — silently accepting it would make cuts never fire.
- Lists: `STRATEGIC_SKUS` survives Excel float ids (`532393.0` → `"532393"`), `none`
  means empty, brand patterns keep embedded commas.
- Calendars: a `festivals.csv` replaces the in-code calendar; bad date formats and
  backwards platform-event windows fail loud.
- Template round-trip: the generated `settings.xlsx` template, fed back through the
  loader, must reproduce the live config for every key in `settings_loader.REGISTRY` —
  proving what we hand a client is what we accept back.
- Upload flow: `validate_bytes` rejects bad files without touching disk;
  `install_bytes` writes only valid files, always to the fixed path, and removes the
  stale sibling so there is one source of truth.

### `tests/test_brand_filter.py` — brand filter guards (7 tests)

Targets `stage1_ingestion/ingest.py::filter_own_brand`, the onboarding-critical gate that
selects the client's rows out of an all-brand export:

- Zero matches fail loud and list the brands actually present (a typo'd `BRAND_NAME`
  must never silently model an empty panel).
- Word-boundary matching: pattern `sun` matches brand `Sun` but not the glued
  competitors `Sunfeast`/`Sundrop`.
- Strict mode (`STRICT_OWN_BRAND_MATCH`): a generic-word pattern that matches two
  genuinely different brands raises; non-strict warns and proceeds.
- A competitor sharing only a generic descriptor token (`Organic India` vs pattern
  `24 mantra organic`) is not flagged; the same brand spelled two ways is not an
  over-match.

### `tests/test_category_brand.py` — category derivation (12 tests)

Targets `_auto_category` / `_detect_category` / `resolve_own_brand_patterns` in
`stage1_ingestion/ingest.py`:

- Title → category derivation strips brand and size (`"24 Mantra Organic Jaggery Powder
  500G"` → `"Jaggery Powder"`), works for unknown brands with no hardcoded keywords.
- Pack variants pool: 500g and 1kg of the same product land in the same category.
- Concatenated/hyphenated brand spellings (`24Mantra`, `24-Mantra`) still strip;
  accented Latin folds; non-Latin scripts are kept rather than collapsing to `Other`.
- Keyword mode overrides auto; `CATEGORY_EXTRA_STOPWORDS` merges variants; a snapshot
  test pins the live grouping for the real product line to catch heuristic drift.

### `tests/test_validate.py` — the fail-loud input gate (9 tests)

Targets `stage1_ingestion/validate.py`: missing required columns raise with the column
named; empty panels and single-cell panels raise; out-of-range discounts and negative
units are soft warnings, not errors. The named data-quality checks are exercised with
synthetic plants: an unexplained demand spike is flagged while a deep-promo spike is
excused; price-above-MRP, price/discount disagreement and sales-at-zero-availability are
flagged; SKU identity churn (a product vanishing, another appearing) is caught; all
checks degrade quietly when optional columns are absent.

### `tests/test_hero_shield.py` — hero-SKU protection (6 tests)

Targets `scripts/tracker/weekly_tracker.py`. `STRATEGIC_SKUS` is the "never auto-cut"
list, and the two sides of the match do not share a dtype (plan ids parse as int64,
settings ids arrive as strings) — a raw `isin()` protects nothing, silently. Tests pin
the normalized match (`_pid_key`) across int/float/string/whitespace shapes, and pin
that a broken settings file **raises** rather than falling back to "no heroes".

### `tests/test_leakage.py` — leakage decomposition (4 tests)

Targets `stage8_output/leakage.py::decompose_leakage` with constructed panels:
pull-forward detected in the interior (not the clipped corner) on a designed promo;
chronic deep discounters classified `always_promo`; flat cells classified
`no_promo`/`no_variation`; cannibalization scoped to same-category-same-city siblings.

### `tests/test_recovery.py` — elasticity recovery (1 fast + 3 slow)

Targets `scripts/diagnostics/recovery_test.py`: the model must recover a planted
elasticity from a synthetic panel and beat the biased naive fit. One 1-seed smoke test
runs by default; the `@pytest.mark.slow` variants run 3 seeds × 2 true elasticities and
assert the naive estimator is biased in the expected direction.

## Honest gaps

The suite covers the *ingestion boundary, configuration boundary, and a few
numerically-treacherous kernels*. It does **not** cover:

- **The analysis chain.** `scripts/analysis/discount_plan.py`, `dml_estimate.py`,
  `validate_plan.py`, `challenger.py` have no unit tests. Their check is runtime: the
  C1–C5/C7/C8 acceptance gates themselves (see [20 — Reliability](20-reliability.md)).
- **The pipeline stages as a whole.** `pipeline.py` orchestration and stages 2–8 are
  untested end-to-end; only individual helpers (validation, leakage, category logic,
  model recovery) are pinned.
- **The tracker loop.** Apart from the hero shield, `weekly_tracker.py`, `actuals.py`,
  `workbook.py` have no pytest coverage. Partial compensation:
  `scripts/tracker/killswitch.py` carries an executable smoke suite in its `__main__`
  block (empty history, revert/confound/recover archetypes, drift block, freeze expiry,
  acted-only judging), and `scripts/tracker/verify_loop.py` is a self-test step wired
  into the dashboard ("LOOP CLOSED: YES").
- **Reports and UI.** `scripts/reports/*`, `dashboard/`, and `ui/app.py` are untested;
  workbook builders are verified by eye on the delivered files.
- **Pricing/promo/validation scripts.** `scripts/pricing/*`, `scripts/promo/*`,
  `scripts/validation/*` rely on their own printed receipts rather than tests.

The design stance: where a wrong number would be *silent*, there is either a test or a
fail-loud runtime guard; where a wrong number would be *visible on a receipt a human
reads weekly*, the receipt is the check. The receipts are described in
[21 — Observability](21-observability.md).
