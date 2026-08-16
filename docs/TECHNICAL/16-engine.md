# 16 — The Computation Engine

*Audience: engineers. Verified against the code on 2026-08-16 (latest run
`output/runs/20260810_143823`, 699 cells, 8 categories).*

Two engines produce numbers here. **Engine A** is the foundation pipeline
(`pipeline.py`, stages 1–8) plus the **champion waste model**
(`scripts/analysis/discount_plan.py`). **Engine B** is the PricingAI-style
**pricing engine** (`scripts/pricing/`). They estimate elasticities
independently and must agree before a cut ships (`agreement.csv` — see
[10-system-architecture.md](10-system-architecture.md)). This doc covers the
stage modules, the champion model spec, and the pricing engine's shared demand
kernel. The dashboard that runs all of it is in [13-api.md](13-api.md) /
[15-frontend.md](15-frontend.md).

## The 8-stage pipeline (`pipeline.py`)

`run_pipeline()` threads a plain `context` dict through the stages and writes
everything into a timestamped `output/runs/<ts>/` directory. No DAG framework:
stages are imported lazily and can be run selectively
(`python pipeline.py --stages 1 2 3`). One memory-driven detail: after Stage 2
the raw all-brand frame is `context.pop("raw_df")`-ed — it is the largest object
in memory and Stage 4's fits need the RAM (the machine has ~1 GB free).

| Stage | Module | What it does |
|---|---|---|
| 1 | `stage1_ingestion/ingest.py` | Reads all platform exports from `input_data/`, maps the CSV "RCA" columns to canonical names (`RCA_RENAME`), normalizes grammage (`'500 g'`→`'500g'`) so a cell's identity is stable. `validate.py` fail-louds on missing columns / fatal quality problems and WARNs on hygiene issues (unexplained spikes, price-vs-discount disagreement, SKU-id churn). |
| 2 | `stage2_preparation/prepare.py` | One fact table at SKU × grammage × city × **day** grain. `stable_mrp` = 90th-pct MRP per SKU-grammage; `selling_price` = `stable_mrp × (1 − disc/100)`; flags event/festival/OOS days and marks `is_regular_day` training rows. |
| 3 | `stage3_features/features.py` | Dual-signal features: `log_price` (price-level effect) and `discount_pct` (badge/deal psychology), plus OSA rolling means, SOV, month/DOW dummies, lag and rolling-mean log-units — all per cell. |
| 4 | `stage4_model/elasticity.py` | Per-category elasticity model with cell fixed effects (below). |
| 5 | `stage5_curves/curves.py` | Sweeps selling price floor→MRP per cell through the log-log model, fits a smooth 4PL saturation curve, assigns curve confidence. |
| 6 | `stage6_economics/economics.py` | Contribution margin along each curve and the **elbow** where marginal ROI crosses the threshold. Cost knobs (COGS/commission/fulfillment defaults in `v4_config`) are **internal guardrail inputs only** — no COGS or margin number reaches a user-facing surface (policy). |
| 7 | `stage7_guardrails/guardrails.py` | Price floors, competitor ceiling, max change rate, tiering (Strong Cut / Trade-off / Hold / Increase / Do Not Act), phasing plan; writes `recommendations.csv` (price-first column order, `product_id` + `cell_id` leading). |
| 8 | `stage8_output/waste_reinvest.py` | Waste & Reinvestment report (markdown + Excel via `excel_report.py`), `waste.csv` / `reinvest.csv`, per-cell JSON. `leakage.py` / `track_record.py` support it. `stage8_monitoring/` is an empty placeholder — live monitoring is the weekly tracker. |

### Stage 4 in detail — the elasticity model

One **Huber-robust RLM per category** with cell fixed effects (a May-2026
redesign; the earlier global MixedLM produced elasticity −5.9 and negative test
R², documented in the module docstring):

```
log_units ~ C(sku_city) + log_price + badge_resid
          + osa_rolling_7d + log_ad_sov + rpi + is_weekend
          + month_* + dow_* + lag/rolling log-units terms
```

- `badge_resid` is `discount_pct` residualized on `log_price` *per cell* — it
  isolates deal-badge psychology from the price level.
- Training is restricted to `TRAIN_LOOKBACK_DAYS` of regular days (the single
  biggest accuracy lever), split by time (last 20 % of dates held out; test
  restricted to cells seen in training, since FE cannot predict unseen cells).
- Per-cell elasticities: raw per-cell OLS slopes on within-cell residuals are
  shrunk **James-Stein-style toward a robust category prior** (median of
  clipped raw slopes; prior strength `N_PRIOR_PRICE = 60`), then clipped to the
  plausible CPG band `[−4.0, −0.3]` (badge to `[−0.01, 0.20]`).

**The 32 MB budget and the within/FWL fallback** (`_fit_category` /
`_fit_category_within`): the formula path materializes `C(sku_city)` as dense
dummy columns — hundreds of cells × tens of thousands of rows needed ~100 MB
during IRLS, which this machine cannot allocate (observed `MemoryError`,
silently defaulting a whole category's cells). Above
`_FE_DUMMY_BUDGET_MB = 32.0` (estimated as `rows × (cells + regressors + 5) × 8`
bytes) the *same* fixed-effects model is fitted on the cell-demeaned system —
by Frisch–Waugh–Lovell the OLS coefficients are identical, and the Huber-
weighted variant is the standard robust FE estimator. SEs are scaled by a
degrees-of-freedom factor for the absorbed intercepts, and `_FEWithinModel`
re-exposes `.params/.bse/.predict()` so downstream code cannot tell which path
ran. Both paths run an RLM → OLS ladder with `_fit_is_sane` divergence checks.

## The champion waste model (`scripts/analysis/discount_plan.py`)

This is what the headline number comes from. It rebuilds its own **weekly**
product × city panel from the latest `fact_table.csv` (regular days only,
calendar-incomplete edge weeks dropped, volume-weighted price/discount) and
fits one confounder-controlled model per category — **MODEL v2.1**:

```
log1p(units) ~ C(cell_id) + disc + disc_sq
             + log_osa + log_adsov                      (our ops)
             + rpi_w + log_comp_osa + log_comp_adsov    (competitor: price index, availability, ads)
             + log_orgsov + lag1_lu + lag2_lu + C(month)
```

Fit with Huber RLM (OLS fallback), category R² floor `CAT_R2_FLOOR = 0.60`.
Design decisions worth knowing:

- **Own category share was removed** (v2): it is outcome-derived (this cell's
  units sit in its numerator) — a bad control that stole discount credit. Its
  replacement is the exogenous competitor relative price index `rpi_w`
  (own price ÷ competitor median price per category/grammage/city/week, built
  straight from the raw exports for `COMPETITOR_BRANDS`), plus the competitor's
  own OSA and ad SOV (v2.1) — their stockout moves our sales, never vice versa.
- **Calendar-aware lags:** `lag1_lu`/`lag2_lu` only count when the previous
  panel row is the actual previous calendar week — gappy (delisted/seasonal)
  cells otherwise feed a months-old week in as "last week".
- **CI gating, not point estimates.** At current discount `d`, the marginal
  effect is `marg_beta = beta + 2·beta2·d` and the pay-line is
  `be_beta = 1/(100 − d)`. A cell is `reliably_waste` only if
  `marg_beta + 1.96·se < be_beta` (even the optimistic CI edge doesn't pay) and
  `reliably_pays` only if `marg_beta − 1.96·se > be_beta`. Everything between
  is uncertain — monitored, never banked.
- **Buckets** (`_bucket`, attribution-first): `a_stock` (OSA < 75 % or a
  material negative OSA contribution — never cut a stock-gated cell),
  `b_competitive` (share loss > 15 % or competitor-price drag), `f_monitor`
  (visibility drag, or uncertain), `c_waste_cut` (reliably-waste + trim room +
  positive modeled net gain), `e_reinvest` (reliably-pays + headroom below the
  net-revenue-maximizing discount).
- **Targets never extrapolate:** the break-even discount is a grid search over
  the quadratic response `N(d) ∝ (1 − d/100)·exp(b1·d + b2·d²)`, floored at the
  category's observed 10th-percentile discount, and modeled units at target are
  clamped so a price cut can never *raise* units (kills reverse-causality
  phantom gains).
- **Confidence** is a data-sufficiency tier (High needs ≥ 8 weeks, ≥ 1.5 ppt
  within-cell discount variation, category fit OK); the headline
  "achievable savings" banks only High-confidence `c_waste_cut` cells. A
  temporal holdout (`holdout_r2`, sized to the last third of the panel) prints
  the out-of-sample R². There is deliberately **no savings-target bar**
  anywhere — the engine reports amounts with spend-share context.

Downstream of the champion sit `dml_estimate.py` (independent Double-ML
confirmation), `validate_plan.py` (gates C1–C5, C7, C8 — C6 was removed by
design), and `challenger.py` (competitor-confounding challenger; defense holds
only from a credible Model B). Their receipts surface in the dashboard.

## The pricing engine (`scripts/pricing/`) and its one demand kernel

`pricing_engine.py` chains four modules and writes to
`output/DISCOUNT_PLAN/pricing/`:

1. **`pricing_panel.py`** — weekly SKU × city panel from the fact table:
   `regular_price` (max weekly price in a ±8-week window), `is_promo`
   (> 5 % below regular), `pack_grams` parsing, `base_product` (title minus the
   pack token), recency (half-life ~8 weeks) and volume weights;
   `freeze_baselines()` yields one row per cell (`q0_units_wk`, `p0_price`,
   `mrp`, `disc0`) — the optimizer's starting state.
2. **Elasticities — Bayes first, hier fallback.** `pricing_engine` imports
   `elasticity_bayes.py` when available: closed-form conjugate Bayesian
   regression per category after FWL residualization of cell FE + controls,
   with an informative negative own-price prior (N(−1.0, 0.8²)) and
   empirical-Bayes shrinkage across categories — a sparse category gets pulled
   toward plausibility with an honestly *wide* posterior SD instead of being
   estimated wild then clipped. The fallback `elasticity_hier.py` approximates
   the same thing with penalized regression: a pooled per-category log-log FE
   model, then own-elasticity written as an additive decomposition
   `grand + category + size_tier + city` fitted by ridge (the L2 penalty *is*
   the shrinkage prior), bootstrap SD, hard clip band. Both return the same
   contract: `(elast_df, cross_df, baseline_df, gates)` with `own_elast`,
   `own_sd`, `promo_elast` per cell and sparse within-category cross pairs.
3. **`de_optimizer.py`** — the decide-the-discount engine (details below).
4. **`whatif.py`** — instant manual-edit simulation (no solver, by rule).

Then a **cannibalization check** on the champion's cut list (does a cut's
"held" volume leak to sibling SKUs?) and a DML-confirmed reinvest block.

### `de.build_problem` / `de.demand_model` — the shared kernel

`build_problem(elast_df, cross_df, baseline_df, config)` assembles one
index-aligned problem dict `P`: baselines (`q0/p0/mrp/disc0`), elasticities
(`own/own_sd/promo`), the `reliable_neg` mask
(`own + 1.64·own_sd < 0`), city-scoped cross pairs, Δln-price bounds derived
from the reachable discount range, pack-ladder pairs, cost vectors, and
optional declarative constraints compiled by `constraints_lib.py`.

`demand_model(disc_vec, P)` is the log-linear PricingAI response
(`V = q0·exp(own·Δln p + Σ cross·Δln p_sibling + Δln PPP)`) with three honesty
clamps: a price **cut earns volume only where `own_elast` is reliably
negative** (otherwise the cut's own-effect is zeroed — no manufactured demand);
Δln-price is clipped to the observed-discount range (no extrapolation); and
volume is capped by the pure power-law response times a bounded sibling
multiplier (`exp(clip(cross, ±0.5))`) so the exponential can never run away.

Every consumer builds `P` through `build_problem` and evaluates through
`demand_model` — **no module carries its own copy of the demand equation**:

- `de_optimizer.optimize()` — differential evolution over the discount vector
  (bounds 0–45 %, ≤ 3 ppt move per cell, revenue floor 98 %, psychological
  price points, ladder), constraints as penalties, a multi-config robustness
  ensemble with agreement-based early stop. `pricing_engine.optimize_decomposed`
  splits the 526-dim problem into independent (category, city) subproblems —
  exact, because cross-price links exist only within category + city.
- `whatif.simulate` — evaluates a manually edited discount vector through the
  same `P`; the readout is arithmetically identical to the optimizer's belief.
- `budget_allocator.py` — per-cell **ROI ladders** (2.5 ppt steps to 45 %,
  marginal ROI = Δnet-revenue/Δspend, elbow = last step ≥ 1) and the greedy
  **marginal-ROI waterline** capping spend at `--budget_pct` (0.12 in the Run
  Center) — every step priced by the kernel.
- `scenario_menu.py` — the negotiation menu: the same optimizer run per
  (KPI × constraint-tightness) scenario, read-only against the champion
  (`revenue_base` reproduces champion behavior), honoring per-cell counterpart
  constraints from `negotiation_feedback.csv`.
- `budget_glide.py` — the budget ladder (+2 % … −10 % rungs, uniform vs smart
  allocation): each rung is a single kernel evaluation, with ±1.96·`own_sd`
  uncertainty bands and explicit extrapolation flags; no verdicts, amounts only.

This single-kernel rule is the engine's central invariant: any change to demand
math lands in `de_optimizer.py` once, and the optimizer, what-if, allocator,
scenario menu and glide ladder all move together.

## Where the numbers go next

Engine outputs feed `agreement.csv` (two-engine cut agreement), the validation
suite (`scripts/validation/`: rolling backtest, 3-stage elasticity gates,
200-draw sensitivity shake, outlier-vs-promo audit) and the weekly tracker
(`scripts/tracker/`), which issues the KAM handoff under the six controls. The
Run Center order in [13-api.md](13-api.md) is the canonical execution sequence.
