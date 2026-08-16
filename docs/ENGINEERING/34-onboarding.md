# 34 — Onboarding: a new machine, a new client

*Audience: engineers. Two distinct checklists: (a) getting the system running
on a **fresh machine**, and (b) pointing a running system at a **new client
engagement**. Verified against the repo on 2026-08-16 (current engagement:
Epigamia on Blinkit). When a step fails, the fix is almost certainly in
[33 — Troubleshooting](33-troubleshooting.md); how to change things once you
are running is [32 — Change Guide](32-change-guide.md).*

There is **no deployment** in the classic sense: no server to provision, no
cloud account, no CI. The machine you set up below *is* production — a
single Windows box running everything locally, with a stdlib dashboard bound
to `127.0.0.1:8765` (`docs/TECHNICAL/17-security.md` explains why that is
the entire auth story).

---

## (a) New machine

1. **Python 3.12.** Install it (python.org build is fine). The pinned stack
   is built against 3.12 — don't substitute another minor version.
2. **Clone the repo** and work from the repo root — every script resolves
   paths relative to it. Note the current root contains spaces
   (`D:\1. PROJECT\Stat IQ Lab`), so quote paths in shells.
3. **Create the venv** at `.venv` in the repo root:

   ```
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   The location matters: `launch_ui.bat` prefers `.venv\Scripts\python.exe`
   when it exists.
4. **Respect the pins.** `requirements.txt` is exact-pinned and its header is
   load-bearing: `numpy` **must stay 1.26.4**, and PyMC must never be
   installed (it force-upgrades numpy ≥ 2 and binary-breaks
   statsmodels/scikit-learn). A previously unpinned environment produced a
   diverged RLM fit (OOS R² = −9.99); this exact set reproduces healthy fits.
5. **Launch the dashboard**: double-click `launch_ui.bat` (opens
   http://localhost:8765 and starts `python -X utf8 ui\app.py`), or run that
   command yourself. Port clashes → [33 §4](33-troubleshooting.md).
   `.claude/launch.json` holds the same entry for agent-driven sessions.
6. **Prove the install**:

   ```
   pytest tests/ -m "not slow"
   ```

   Expected: **67 passed** (brand filter, category/brand, hero shield,
   leakage, recovery, settings, validate). Run the full `pytest tests/`
   once if you have a few spare minutes — the `slow` marker covers tests
   that train models.
7. **Know the machine constraint.** The reference machine has 5.9GB RAM with
   roughly 1GB free; this shaped real code (Stage 4's 32MB dummy-matrix
   budget and within-FWL fallback, chunked CSV ingestion). Close Excel and
   heavy browser sessions before a full pipeline run.

A fresh clone has no `output/runs/` — the dashboard will say so until the
first pipeline run. That is normal; runs are generated state, not repo
content (`output/` is git-ignored except `output/DISCOUNT_PLAN/`).

---

## (b) New client

The engine is engagement-agnostic by design: **brand and platform are
settings, never code** (`BRAND_NAME` / `PLATFORM_NAME` in the settings
registry). Switching clients is a data-and-settings operation plus one full
rebuild — no code changes.

### 1. Archive the previous engagement's tracker state

Do this **first**. The weekly loop keeps mutable state in
`output/DISCOUNT_PLAN/` — `tracker_history.csv`, `baselines.json`,
`execution_log.csv` (plus the delivered `WEEKLY_TRACKER.xlsx` and reports) —
and that history is client evidence, not scratch. Move it into `archive/`
under a dated folder; the precedent is
`archive/24mantra_tracker_state_2026-08-10/` from the 24 Mantra → Epigamia
switch. The Run Center's self-test step can *delete* this state
(`#reset_state` in `ui/app.py`), but archiving beats deleting: never destroy
a previous client's audit trail.

### 2. Drop the new exports into `input_data/`

Platform exports (`.csv` or `.xlsx`) go straight into `input_data/` — e.g.
the current files are `Epigamia_blinkit-rca-download_<Month>_2026.csv`.
Ingestion reads every `.csv`/`.xlsx` there, skipping `~`-prefixed lock files
and SKU-master files ("my sku"/"sku list" in the name). RCA-style CSV columns
are mapped by `RCA_RENAME` in `stage1_ingestion/ingest.py`; a genuinely new
platform format means extending that map first —
[32 §5](32-change-guide.md).

### 3. Set the engagement settings via the dashboard

On the dashboard's Inputs & Settings page: download the current template
(generated from the code's `REGISTRY`, so always in sync), edit the value
column, and upload. The upload is dry-run validated before it is installed
(`settings_loader.py::install_bytes`) — a bad file is rejected with named
errors and changes nothing. Minimum set for a new client:

| Key | What to put there |
|---|---|
| `BRAND_NAME` | The client's brand exactly as the platform spells it |
| `OWN_BRAND_PATTERNS` | *Every* spelling of the brand in the data, `|`-separated (blank = derive from `BRAND_NAME`) |
| `PLATFORM_NAME` | The quick-commerce platform, e.g. `Blinkit` |
| `COMPETITOR_BRANDS` | Up to 3 competitor names, spelled as in the export (feeds the relative-price index) |
| `STRATEGIC_SKUS` | Hero `PRODUCT_ID`s that must never be auto-cut (`none` for no protection) |

Review the rest of the Settings sheet too (budget cap, lookback, kill-switch
tolerance) — blank keeps the code default. If the client has a festival or
platform-event calendar, fill the `Festivals` / `Platform Events` sheets;
rows there **replace** the code calendar outright.

### 4. Run the monthly chain

Run Center → run all monthly (or step buttons 1–13 in order): `pipeline` →
`champion` → `dml` → `gates` → `challenger` → `pricing` → `budget` → `promo`
→ `scenarios` → `glide` → `backtest` → `elast_gates` → `sensitivity` →
`outlier_audit` (`MONTHLY_ORDER` in `ui/app.py`). The first minutes are the
sharp edge: Stage 1 fails loud if the brand patterns match no rows or
over-match a competitor — that means step 3's settings need fixing, see
[33 §2](33-troubleshooting.md).

### 5. Verify the receipts

On the dashboard's outputs page, check every validation chip against the
**new** run:

- **Double ML** — read from the current run's `plan/dml_results.json`
  (this is the receipt that once went stale across engagements; the reading
  is now current-run by design, but verify the note says "this run").
- **Acceptance gates** — must end ALL PASS (C1–C5, C7, C8; C6 retired).
- **Elasticity gates**, **Sensitivity** (0 fragile), **Competitor
  challenger** (champion stands or challenger adopted — either is a valid
  verdict, but read which), **Defense hold**.
- **Rolling backtest** — with a young feed this will honestly read
  **FAIL (not scoreable yet)**: each fold needs 12 training weeks. Expected;
  do not fake it — [33 §7](33-troubleshooting.md).

If anything still describes the previous client, an artifact is stale —
rerun the chain; never hand-edit a receipt ([33 §6](33-troubleshooting.md)).

### 6. Start the weekly loop

With receipts green: weekly steps A (recommend → `execution_log_template.csv`
KAM handoff), B (score last week vs actuals), C (self-test — must print
`LOOP CLOSED: YES`). From here the cadence is the weekly tracker under its
six controls plus the monthly rebuild when a new export lands.

---

*Doc map for what you just touched: setup facts → this doc; runtime behaviour
→ `docs/TECHNICAL/13-api.md` and `14-data-files.md`; anything you change from
here on → [32 — Change Guide](32-change-guide.md).*
