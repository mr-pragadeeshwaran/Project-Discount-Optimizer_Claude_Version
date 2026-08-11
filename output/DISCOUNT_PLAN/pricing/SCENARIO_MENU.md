# Scenario Menu — negotiation-ready optimized options

*Run `20260810_143823` · round 5 · challenger artifact — the champion plan (pricing_reco.csv, cut list, tracker) is untouched. All scenarios share the validated demand kernel (de_optimizer.demand_model), so differences between rows are pure objective/constraint choices, not model noise.*

## The menu

Today (row 'current'): ₹36,952,729/wk revenue, ₹1,245,159/wk discount spend (3.3% of gross), weighted-avg discount 3.3%.

| Scenario | Objective | Preset (floor / max move) | Revenue ₹/wk (Δ%) | Units/wk (Δ%) | Disc spend ₹/wk (Δ₹) | Wavg disc | Profit* ₹/wk (Δ₹) | Cells up/down | Kernel check |
|---|---|---|---|---|---|---|---|---|---|
| current | — | — | ₹36,952,729 (+0.00%) | 449,265 (+0.00%) | ₹1,245,159 (+0) | 3.3% | ₹7,818,223 (+0) | 0/0 | OK |
| revenue_base | revenue | 98% / 3ppt | ₹37,479,408 (+1.43%) | 452,606 (+0.74%) | ₹1,055,211 (-189,948) | 2.7% | ₹8,064,124 (+245,901) | 1/401 | OK |
| revenue_tight | revenue | 99% / 2ppt | ₹37,327,285 (+1.01%) | 451,901 (+0.59%) | ₹1,119,597 (-125,562) | 2.9% | ₹7,985,742 (+167,519) | 1/401 | OK |
| revenue_loose | revenue | 96% / 4ppt | ₹37,627,222 (+1.83%) | 453,233 (+0.88%) | ₹989,342 (-255,816) | 2.6% | ₹8,142,525 (+324,302) | 1/400 | OK |
| volume_base | volume | 98% / 3ppt | ₹37,358,641 (+1.10%) | 453,075 (+0.85%) | ₹1,241,388 (-3,771) | 3.2% | ₹7,924,084 (+105,861) | 28/364 | OK |
| nrw_base | nrw | 98% / 3ppt | ₹36,995,795 (+0.12%) | 447,673 (-0.35%) | ₹997,271 (-247,888) | 2.6% | ₹7,973,160 (+154,936) | 198/194 | OK |
| share_base | share | 98% / 3ppt | ₹37,358,819 (+1.10%) | 453,065 (+0.85%) | ₹1,240,852 (-4,306) | 3.2% | ₹7,924,509 (+106,286) | 28/363 | OK |
| profit_base | profit | 98% / 3ppt | ₹37,479,406 (+1.43%) | 452,582 (+0.74%) | ₹1,053,032 (-192,126) | 2.7% | ₹8,065,455 (+247,232) | 1/411 | OK |
| margin_base | margin | 98% / 3ppt | ₹36,940,750 (-0.03%) | 447,155 (-0.47%) | ₹987,400 (-257,759) | 2.6% | ₹7,964,010 (+145,787) | 177/206 | OK |

_Weekly discount-spend policy cap: 12% of gross (v4_config.DEFAULT_BUDGET_PCT_CAP). Every row, including 'current', is within the cap._

_*Profit uses default cost assumptions (COGS 50% of MRP, 15% commission, ₹10/unit fulfillment) until true per-SKU costs are supplied — treat profit DELTAS as directional, levels as rough._

_Objective KPIs available in the optimizer this run: revenue, volume, nrw, share, spend, profit, margin. Profit/margin objectives were available and included._

## How to read this honestly

- Deltas are small because the validated (confounder-controlled) elasticities say discount moves demand weakly on this portfolio. A menu that promised big scenario spreads would be fabricating demand the model does not believe in.
- The optimizer only credits volume to a price cut where own-elasticity is *reliably* negative — same honesty clamp as the champion run.
- 'Cells up/down' counts moves > 0.25ppt; glide caps keep every move executable in one week.

## How a negotiation uses this

1. Pick the scenario matching the counterpart's constraint (finance wants margin -> `revenue_tight`/`nrw_base`; trade wants volume -> `volume_base`) and hand the KAM its per-cell sheet (`scenarios/round_05/reco_<scenario>.csv`).
2. KAM executes it as a glide-capped in-market test; counterpart pushback lands in `negotiation_feedback.csv` (lock/opt-out/max/min per cell) and the menu is re-run for the next round.
3. Actuals feed back through the weekly tracker, elasticities refresh, and the next round's menu is re-optimized on measured — not assumed — response. That is the closed loop.
