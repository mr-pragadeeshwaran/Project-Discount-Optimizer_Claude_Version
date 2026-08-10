# Budget Allocator — marginal-ROI waterline (Objectives 1 & 3)

*Cap discount spend at **12% of baseline revenue** (₹4,434,334/wk); spend it on the highest marginal-ROI discount first. Same demand kernel as the optimizer.*

## The budget picture

- Baseline revenue: **₹36,952,781/week**.
- Current discount spend: **₹1,245,161/wk (3.4% of revenue)** — vs the 12% cap.
- Under the cap the allocator spends **₹0/wk**, at a **waterline marginal ROI of 1.00** (every rupee of discount kept returns ≥₹1.00).
- Result: **409 cells cut · 0 raised · 306 held**.

**Read this honestly:** the allocator spends almost nothing (₹0 of a ₹4,434,334 cap) because — under these elasticities — discount barely clears break-even *anywhere*. Only a handful of cells have a discount step whose marginal ROI reaches 1; for the rest, once volume goes flat, marginal ROI sits at −1 (every rupee of discount is a rupee of pure margin given away). So the profit-optimal discount is near-zero — the *fourth* independent confirmation that discount is mostly waste on this portfolio, and an even more aggressive read than the ₹6.98L cut list.

**But do NOT slash all discount overnight.** This rests on the wide-band (≈unit-elastic) Bayesian elasticities — it's a directional cross-check, not an execution plan. The glide, reliability gates, engine-agreement, and in-market tests exist precisely because these estimates are uncertain.

## Marginal-ROI ladder (Objective 1 proof artifact)

`roi_ladder.csv` has every cell's full curve. The **elbow** is where marginal ROI crosses 1 — beyond it, more discount destroys net revenue. Example elbows:

| SKU | City | Elbow discount | Units there | Marginal ROI |
|---|---|---:|---:|---:|

_Budget % is set with `--budget_pct` (default 0.10). This is a separate constraint mode from the KPI optimizer; run it when you want a hard spend ceiling rather than a revenue floor._