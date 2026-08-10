# Promo Calendar — MILP challenger (PromoAI-style, advisory)

*715 cells x 12 weeks on grid [0, 5, 10, 15, 20]% · decomposed per category x city · HiGHS via scipy.optimize.milp · run `20260810_143823` · total solve wall-clock **33.2s** across 70 subproblems.*

## The calendar in one paragraph

- Horizon net revenue of the chosen calendar: **Rs444,261,955** vs **Rs442,851,977** if every cell just held its current (grid-snapped) discount — **+0.32%**. (Note: that hold-current plan is itself NOT rule-feasible — holding a promo discount 12 straight weeks breaks the max-duration rule — so it is a reference point, not an available alternative.)
- Promo cell-weeks scheduled: **320** of 8580 (4%). Weekly discount spend ranges Rs8,819–Rs30,790.
- Defense-held cells (kept at current level, all weeks): **0 cell-solves**.

**Read this honestly:** the demand kernel's validated honesty clamps credit volume from a discount only where own-price elasticity is *reliably* negative — which on this portfolio is almost nowhere. A net-revenue-max calendar therefore parks most cells at 0% discount and the 'calendar' structure you see comes from the constraints (holds, budget, duration rules), not from demand seasonality (the kernel is stationary across weeks). This is the same conclusion as the budget allocator and the confounder-controlled study: discount spend on this portfolio is mostly margin giveaway.

## Solver receipts (val_14: per-solve MIP gap, status, runtime)

- Gap target: **1.0%** relative; time limit 60.0s per subproblem.
- **70/70** subproblems solved to the gap target; **0** hit the time limit (kept incumbent, residual gap flagged below); **0** infeasible.
- Worst achieved gap: **0.0007%**.
- Total runtime: **33.2s**.

| Category | City | Cells | Status | Gap target | Achieved gap | Time (s) | Stop reason |
|---|---|---:|---:|---:|---:|---:|---|
| Yogurt | Mumbai | 60 | 0 | 1.0% | 0.0000% | 4.58 | target_gap_hit |
| Yogurt | Others | 56 | 0 | 1.0% | 0.0000% | 3.97 | target_gap_hit |
| Yogurt | Delhi-NCR | 54 | 0 | 1.0% | 0.0000% | 3.50 | target_gap_hit |
| Yogurt | Pune | 52 | 0 | 1.0% | 0.0000% | 3.20 | target_gap_hit |
| Yogurt | Ahmedabad | 52 | 0 | 1.0% | 0.0000% | 3.19 | target_gap_hit |
| Yogurt | Kolkata | 52 | 0 | 1.0% | 0.0000% | 3.08 | target_gap_hit |
| Yogurt | Lucknow | 52 | 0 | 1.0% | 0.0000% | 3.05 | target_gap_hit |
| Yogurt | Bangalore | 48 | 0 | 1.0% | 0.0000% | 2.64 | target_gap_hit |
| Yogurt | Hyderabad | 44 | 0 | 1.0% | 0.0000% | 2.19 | target_gap_hit |
| Yogurt | Chennai | 39 | 0 | 1.0% | 0.0000% | 1.59 | target_gap_hit |
| Almond Milk | Ahmedabad | 2 | 0 | 1.0% | 0.0000% | 0.25 | target_gap_hit |
| Protein Milkshake | Others | 11 | 0 | 1.0% | 0.0000% | 0.08 | target_gap_hit |
| Protein Milkshake | Delhi-NCR | 11 | 0 | 1.0% | 0.0000% | 0.08 | target_gap_hit |
| Protein Milkshake | Mumbai | 13 | 0 | 1.0% | 0.0000% | 0.08 | target_gap_hit |
| Protein Milkshake | Pune | 10 | 0 | 1.0% | 0.0000% | 0.06 | target_gap_hit |

_(top 15 by solve time shown; full table in `promo_solver_report.csv` — 70 rows)_

## Active constraint templates (from promo_constraints.json)

| Template | Rows generated | Cells touched | Note |
|---|---:|---:|---|
| competitive_defense_hold | 0 | 0 | held at current level (defense_hold.csv) |
| promotion_exclusivity | 8580 | 715 | one level per cell-week |
| min_promo_duration | 8580 | 715 | min run 2 wk |
| max_promo_duration | 4290 | 715 | max run 6 wk |
| min_promo_spacing | 6435 | 715 | starts >= 4 wk apart |
| max_simultaneous_promos | 840 | 715 | <= 3 live promos/wk |
| weekly_budget_cap | 792 | 715 | spend <= 12% of group baseline revenue/wk (pro-rata per category x city) |

## How to read / operate

- `promo_calendar.csv`: one row per cell x week — the chosen discount level, plus the kernel's predicted units, net revenue and discount spend at that level. `held=True` rows are competitive-defense cells pinned at their current level.
- `promo_solver_report.csv`: one row per (category, city) MILP — the paper-style gap certificate. `achieved_gap` <= `gap_target` means the schedule is provably within that % of the best possible under these rules. `hit_time_limit=True` rows carry a residual gap: the incumbent is kept but is NOT certified to target.
- To onboard another market/brand: copy `promo_constraints.json`, edit params — zero code changes. Unknown template names fail loud.
- **This calendar is advisory (challenger).** Week-1 execution still goes through the champion cut list, the 3 ppt glide, and the weekly tracker. Cross-effects of simultaneous moves are frozen at baseline in the objective (PWL step), and demand carries no week-of-year seasonality — treat week-to-week structure as rule-driven.