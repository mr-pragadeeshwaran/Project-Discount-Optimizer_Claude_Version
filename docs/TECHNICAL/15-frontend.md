# 15 — The Frontend (`ui/index.html`)

*Audience: engineers. Verified against `ui/index.html` (~2,300 lines) and `ui/app.py` on 2026-08-16.*

The entire dashboard is **one static HTML file** served by the stdlib backend
(`GET /` in `ui/app.py` reads `ui/index.html` from disk — see
[13-api.md](13-api.md)). There is no framework, no build step, no `node_modules`,
no bundler, and no client-side dependency: styling is hand-written CSS custom
properties, logic is one `<script>` block of vanilla ES5-ish JavaScript, and the
charts are inline SVG strings. The only external reference is a Google Fonts
stylesheet loaded with the non-blocking `media="print" onload` swap — offline,
the UI falls back to Segoe UI / system fonts and everything still works.

## Why no framework

- **It matches the backend's zero-dependency policy.** The server is stdlib
  `http.server` + pandas; a React/Vite toolchain would be the largest dependency
  in the repo, on a deployment machine with 5.9 GB RAM (~1 GB free) where even
  the *model fit* had to be reworked to stay under a 32 MB matrix budget
  (see [16-engine.md](16-engine.md)).
- **State is tiny.** One global object `S` (status payload, step list, current
  job, route, settings) plus three small caches (`CUT`, `WK`, `REP`). Every page
  re-renders by writing an HTML string into its section — with tables of a few
  hundred rows this is instant, and there is nothing a virtual DOM would save.
- **One file is the deployment unit.** Editing the UI is: edit `index.html`,
  refresh the browser. No compile, no source maps, no version skew between
  built assets and server.

XSS discipline replaces a template engine: every interpolated value goes through
`esc()` (HTML-entity escaping), and the markdown renderer escapes *first*, then
transforms (`mdRender`). The server only ever feeds the page artifacts from the
local repo, but the rule is applied unconditionally.

## Pages and routing

A hash router (`route()`, wired to `window.hashchange`) switches six pages whose
`<section class="page">` skeletons are all present in the static HTML:

| Hash | Page | Renders from |
|---|---|---|
| `#overview` | Overview — hero number, KPIs, charts, proof receipts | `/api/status` |
| `#run` | Run Center — every playbook step as a button + live log console | `/api/steps`, `/api/job` |
| `#cuts` | Cut Plan — 8 tabbed tables (action plan, price board, elasticity, …) | `/api/table/<name>` |
| `#weekly` | Weekly Loop — loop status, KAM handoff sheet, scorecard history | `/api/table/handoff`, `/api/table/history` |
| `#reports` | Reports — 9 markdown reports rendered in a reading pane | `/api/report/<key>` |
| `#inputs` | Inputs & Settings — config cards, settings spreadsheet, data files | `/api/status`, `/api/settings` |

`PAGE_META` holds each route's title/subtitle for the topbar; `PAGE_LOADERS`
maps route → render function. Unknown hashes fall back to `overview`. There is
no history state beyond the hash, and no server-side routing at all.

## Data flow: polling, caching, invalidation

- `api(url, opt)` is the single fetch wrapper — parses JSON, converts non-2xx
  into an `Error` carrying the server's `error` message and status code.
- `boot()` loads `/api/steps` once, then `refreshStatus()` (`/api/status`) and
  `pollJob()` (`/api/job`). Status refreshes every **30 s** while idle; while a
  job runs, `pollJob` polls every **1 s** and streams the log into the console
  (`#log`), auto-pinned to the bottom unless the user scrolls up (`S.logPinned`).
- When a job transitions running → done/failed, `invalidateData()` clears every
  table/report/settings cache and the current page re-renders — this is the
  client half of the "stale receipts are bugs" policy (the server half is in
  [13-api.md](13-api.md): receipts read the *current* run's artifacts).
- Every artifact-backed panel has an explicit **empty state**: a 404
  (`not generated yet: …`) renders `emptyState()`, which names the missing
  artifact *and the Run Center step that creates it* (`TABLE_EMPTY`,
  `REPORT_EMPTY`), with a button to `#run`. A broken settings file renders the
  loader's error verbatim — deliberately loud, since it will also fail the next run.

## Tables: one generic renderer, declarative formatting

Every table endpoint returns `{columns, rows}`; `rowsToObjects()` zips them and
`tableHTML()` renders. Formatting is registry-driven, not per-table code:

- `COL_LABEL` — column key → human header ("net_gain_mo" → "Gain / month").
- `RUP_COLS` / `PCT_COLS` / `FRAC_COLS` / `ID_COLS` — rupee (Indian digit
  grouping, `₹`/compact `k/L/Cr`), percent (already 0–100), fraction (0–1 → %),
  and identifier columns (never comma-grouped).
- `fmtCell()` adds per-column widgets: confidence chips, the Action/Verdict
  colored chips, the signed `gap` coloring, Y/N booleans, and the synthetic
  `move` column (`cur_disc → tgt_disc` merged into one cell).

The Cut Plan page (`renderCutPlan`) layers on top: `CUT_TABS` defines the eight
tabs (`plan_all`, `prices`, `elasticity`, `cuts`, `reinvest`, `buckets`,
`scenarios`, `sensitivity`); filterable tabs get client-side search
(SKU/title/city), a category select built from the data, and a high-confidence
filter; clicking a `<th>` sorts (numeric-aware, direction toggling); a summary
strip computes per-tab "so what" stats (median elasticity, cells to cut,
₹/month in view, …). **Export CSV** serializes exactly the on-screen view
(`CUT.view` — post-filter, post-sort) through a `Blob` download; `move` is
re-expanded into `cur_disc,tgt_disc`. All of this happens client-side; the
server never re-queries.

## The `REPORT_DEFS` registry

The Reports page is driven by one array:

```js
const REPORT_DEFS = [
  ['readout',  'Weekly readout',      'What changed this week, …'],
  ['backtest', 'Rolling backtest',    'Would the model have made money …'],
  // … sens, promo, chal, budget, glide, params, egates
];
```

Each entry is `[key, title, question-the-report-answers]`. The key must match
the server-side `REPORTS` dict in `ui/app.py`, which maps it to a markdown file
under `output/DISCOUNT_PLAN/`. `openReport(key)` fetches `/api/report/<key>`
and renders it with `mdRender` — a ~50-line escape-first markdown subset
(headings, lists, pipe tables, `**bold**`, `` `code` ``). Cards also carry an
icon (`REPORT_ICON`), a hue (`REPORT_HUE`), and an empty-state step
(`REPORT_EMPTY`). **Adding a report is two lines**: one entry in `REPORT_DEFS`
here, one path in `REPORTS` in `ui/app.py`.

## Run Center rendering

`/api/steps` returns the server's `STEPS` allowlist plus `monthly_order` (14
step ids). The client groups them into three phases via `RUN_PHASES` (Build &
model / Pricing & promo engines / Validation & proof) — any allowlisted step
the grouping doesn't know lands in a "More steps" bucket, so a new server-side
step appears without a client change. `renderJob()` drives: the topbar status
pill, the console header/elapsed/log, a progress bar for `monthly_all`
(`done_steps / total_steps` from the job snapshot), and per-step badges
(number → spinner → check/cross) in `S.stepState`. While a job runs,
`body.job-running` CSS disables every `[data-run]` button — mirroring the
server's one-job-at-a-time lock rather than merely trusting it.

## Charts

Pure SVG string builders, no library: `donutChart()` (cells by bucket, with a
full-ring track, per-arc tooltips via the shared `data-tip` tooltip layer, and
a center count-up) and `hbarChart()` (waste by category, rounded bars with
staggered entrance). Bucket names/colors live in `BUCKETS` and map 1:1 to the
champion model's bucket codes (`a_stock`, `b_competitive`, `f_monitor`,
`c_waste_cut` — see [16-engine.md](16-engine.md)). Number count-ups are
`requestAnimationFrame`-driven with a settle-guard timeout and are skipped
entirely under `prefers-reduced-motion`.

## Theme system

A tiny inline script in `<head>` runs **before first paint**: it reads
`localStorage['opf-theme']`, falls back to `prefers-color-scheme`, and stamps
`data-theme="light|dark"` on `<html>` — so there is never a theme flash.
Everything else is CSS custom properties:

- `:root` defines the token vocabulary (surfaces, ink levels, accent, good/warn/
  bad, chart colors `--c1..--c6`, spacing/radius/elevation/motion/z-index/type
  scales) with a light default, plus a `prefers-color-scheme: dark` block.
- `:root[data-theme="light"]` and `:root[data-theme="dark"]` then override with
  the tuned palettes (cool light canvas, warm near-black dark), so the explicit
  toggle always beats the OS preference.
- The Day/Night segmented control calls `setTheme()` (attribute + localStorage);
  the command palette exposes the same actions.
- Accessibility variants are token overrides too: `prefers-contrast: more` and a
  user-forced `.hc` class sharpen ink/border/ring tokens;
  `prefers-reduced-motion` collapses all animation/transition durations.

Because every component only ever references tokens, no component has
theme-specific rules.

## Interaction chrome

- **Command palette** (`⌘K` / `Ctrl-K`, or `/`): fuzzy-scored jump-to-page,
  run-any-step (navigates to `#run`, then calls `runStep`), and theme/contrast
  toggles. Built from `PAGE_META` + the live step list, so it stays in sync.
- **Event delegation:** one document-level click handler routes `[data-run]`,
  `[data-cuttab]`, `[data-report]` and sortable `<th>` clicks — re-rendered HTML
  never needs listeners re-attached.
- **Toasts + tooltip:** a `role="status"` toast stack for job finish/fail and
  export/copy feedback; one fixed tooltip element driven by `data-tip`
  attributes (used by charts and receipts).
- **Responsive shell:** sidebar collapses to an icon rail below 1100 px and to a
  hamburger-plus-scrim drawer below 760 px; KPI grid steps 4→2→1 columns. A
  skip-link, `aria-current` on nav, `aria-live` on the job pill, and
  `:focus-visible` rings cover keyboard/screen-reader use.

## Anti-stale honesty in the UI itself

The Overview page never grades sufficiency and never shows a savings target
(policy — see `docs/BUSINESS/03-business-logic.md`). The hero states whether
the number is *model-estimated* or *register-proven* (any scored tracker cells
flip the badge), the receipts row renders the server's pass/fail chips verbatim
(including the honestly-FAIL backtest), and the "How to read the number" card
spells out that model-proven ≠ register-proven. When adding UI, keep that
contract: render what the artifacts say, including failures.
