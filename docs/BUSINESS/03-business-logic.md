# The Business Logic Catalog

*Every important rule the system enforces: what it means, why it matters,
where it lives. The first three columns are for you; the last is for
engineers.*

## The decision rules

| Business Rule | What It Means | Why It Matters | Where Implemented |
|---|---|---|---|
| Isolate before judging | Discount's effect is measured with availability, ads, competition and season held constant | Stops discounts taking credit for what stock or ads did | `scripts/analysis/discount_plan.py` (champion model) |
| The pay-line | Each cell has a response level where one point of discount exactly pays for itself | Below it, discounting is mathematically a donation | `discount_plan.py` (`be_beta` vs `marg_beta`) |
| Reliability, not point estimates | A cut needs the whole confidence interval below the pay-line, not just the average | Protects volume from acting on noise | `discount_plan.py` (CI gating, `reliably_waste`) |
| Bucket before action | Every cell gets one verdict: cut / fix-stock / competitive-hold / test / monitor | A below-pay-line cell with stock problems needs stock fixed, not price cut | `discount_plan.py` (bucket assignment) |
| Independent confirmation | A second causal method (Double ML) must agree the waste is real | One method can fool itself; two independent ones rarely fool identically | `scripts/analysis/dml_estimate.py` |
| Eight validation gates | Fit, controls present, money reconciles, out-of-sample accuracy, DML confirmation, more | The plan ships with receipts, not vibes | `scripts/analysis/validate_plan.py` |
| Two-engine agreement | A cut executes only if the independent pricing engine also wants it | Two witnesses who never talked | `pricing/agreement.csv` → `weekly_tracker.apply_agreement` |
| The proven floor | Never set a discount below the level the cell has actually traded at | No experiments in unknown price territory | tracker + all report builders (`historical_floor`) |
| The glide | Max 3 points of discount change per cell per week | Customers and platforms punish price lurches | `v4_config.TARGET_TIMELINE_WEEKS` / `MIN_DISCOUNT_CHANGE_PPT` |
| Budget cap | Weekly discount spend capped at 12% of gross (configurable) | Reinvestment can never blow the trade budget | `DEFAULT_BUDGET_PCT_CAP` → tracker guardrail |
| Hero shield | Listed flagship SKUs are never auto-cut | Strategy outranks statistics where you say so | `STRATEGIC_SKUS` → tracker |
| Kill-switch | Actual volume missing prediction by >5% twice → automatic revert | Bounded downside on every action; no meetings needed | `weekly_tracker.py` scoring |
| Defense hold (credible only) | Cells the challenger flags as competitive defense are held — but only when that challenger model is itself credible | A broken model's noise must not cancel the plan | `scripts/analysis/challenger.py` |
| Elastic-enough to reinvest | Deeper discount is considered only where sensitivity clearly exceeds the break-even threshold | A price cut below that mathematically cannot pay | `INELASTIC_ELASTICITY_THRESHOLD`, `REINVEST_MIN_ELASTICITY` |
| The engine reports, never grades | No savings target exists in the software; amounts come with context (share of spend), never verdicts | Any operator-chosen bar proved to be noise or self-confirmation | removed by design (see git history) |
| Observable numbers only | No COGS/margin assumptions in anything a brand sees | Brands won't share costs; invented costs invite one unanswerable question | report builders (revenue-space ROI) |
| Versioned deliverables | A file sent to anyone is never overwritten; each build gets the next version number | What a client holds must never silently change | `scripts/reports/*` (`_next_versioned_out`) |
| Fail loud | Bad settings or missing columns stop the run with a named reason before anything computes | A crash is cheaper than a wrong number reaching prices | `settings_loader.py`, `stage1_ingestion/validate.py` |

## The central decision, as a tree

```text
For each product-city cell:
Is availability healthy (≥75%)?
  NO → bucket: FIX STOCK FIRST (price says nothing useful yet)
  YES ↓
Is competitive pressure the likely explanation?
  YES → bucket: COMPETITIVE HOLD (watch, don't cut)
  NO ↓
Is the isolated response RELIABLY below the pay-line
(whole confidence interval on the wrong side)?
  YES → Does the independent engine agree? Does Double ML confirm?
        YES → bucket: CUT (glide toward the proven floor)
        NO  → held — a receipt shows exactly which check dissented
  NO ↓
Is it reliably ABOVE the pay-line?
  YES → PROTECT (and consider reinvest if clearly elastic + headroom)
  NO → TEST or MONITOR (the honest "not enough evidence" — with its
       unlock condition and, if testable, its wave assignment)
```

## The weekly execution decision

```text
Cell is in the cut bucket
↓ Both engines agree?          NO → hold, noted
↓ Defense-held?                YES → hold, noted
↓ Hero SKU?                    YES → hold, noted
↓ Within budget cap?           NO → trimmed to fit
↓ Move ≤ glide limit?          clipped to 3 points
↓ Above the proven floor?      never below
→ Row appears on the Monday sheet with its prediction and strike level
```
