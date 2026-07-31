# output/ — generated deliverables

Everything Claude generates for you (files to open, share, or hand off) lands here —
not in the repo root and not in a temp folder. These are **regenerated from the latest
`v4_outputs/` run**, so they are outputs, not source; this folder is git-ignored.

**Subfolders (moved here so the whole project has one output root):**
- `runs/` — the engine's run store; every monthly rebuild writes a timestamped folder
  (`runs/<YYYYMMDD_HHMMSS>/` with fact_table, recommendations, plan/, …). Scripts and the
  dashboard read the newest automatically. *(Was `v4_outputs/` at the repo root; git-ignored.)*
- `DISCOUNT_PLAN/` — the weekly-tracker + pricing + promo + validation artifacts
  (WEEKLY_TRACKER.xlsx, execution_log_template.csv, tracker_history.csv, pricing/, validation/, …).
  *(Was `DISCOUNT_PLAN/` at the repo root; stays git-tracked, except `pricing/history/`.)*

| File | What it is |
|------|------------|
| `ACTION_PLAN_all_products.csv` | The single master sheet — one row per product × city with the action (Cut / Reinvest / Hold / Monitor), the discount to set, and why. Open in Excel/Sheets. |
| `ACTION_PLAN_all_products.xlsx` | Same, as an Excel workbook for sharing. |
| `DECISION_LOGIC_explainer.html` | The stakeholder one-pager explaining how each product gets its verdict (plain + technical). Open in any browser. |
| `EXECUTIVE_BRIEF.md` | **For leadership.** What the engine is, how it works in plain terms, what it found, why it can be trusted, and what it does *not* claim. Start here for any non-technical audience. |
| `HOW_THE_MODEL_ISOLATES_PRICE.md` | Deep reference: every control the model uses to isolate price's true effect (pre-filters, in-model controls, measurement discipline), what lie each one deletes, and all threshold values. |
| `ENGINE_FLOWCHART.md` | Granular flowcharts of the whole engine — ingest → clean → panel → fit → diagnose → gate → confirm → validate → execute, with every threshold and branch drawn. |
| `ANALYST_DEEP_DIVE_01_TUR_DAL_32385_BANGALORE.md` | **For learning.** One product's complete decision taught mentor-style: every metric from first principles, the expert's scan order, every rule, the strongest counter-argument, and exact numeric flip conditions. |
| `FROM_ZERO_THE_COMPLETE_WORKING.md` | **For learning, deeper.** The full math from absolute zero — logs, regression, "holding constant", the attribution arithmetic, the break-even test and the money — walked on four real products, one per decision type. |
| `WORKING_<cell_id>.md` (×4) | **Machine-generated audit trails** — every weekly row, coefficient and arithmetic step for one cell, from raw data to bucket. Regenerate for ANY cell: `python -X utf8 scripts/explain_cell.py <cell_id>`. |
| `OPTIMIZATION_REPORT.xlsx` | Decision-ready discount-spend optimization workbook: Executive Summary + every SKU's action / recommended spend / confidence + a full per-row confidence explanation + a Confidence Method sheet. Regenerate with `scripts/build_optimization_report.py`. |

To refresh these after a new monthly rebuild, ask Claude to "regenerate the action plan and explainer into output/".
