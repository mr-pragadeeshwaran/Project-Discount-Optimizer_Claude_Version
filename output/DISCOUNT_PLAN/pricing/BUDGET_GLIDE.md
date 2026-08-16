# Budget Glide Ladder — if the discount budget moves, what happens to sales?

*Run `20260810_143823` · current spend Rs.5,336,394/mo (weighted discount 3.26%) · projections from the validated demand kernel — no optimizer, no target verdicts.*

Each budget rung is shown under two allocation styles: **uniform** (every discount scaled equally — what a brand does unaided) and **smart** (worst marginal-ROI discounts cut first, per the budget allocator's ladder). The gap between them is the value of allocating the change well.

| Budget | Mode | Spend/mo | Wt disc | Sales Δ (band) | Revenue Δ | Net revenue Δ/mo | Cells moved | Extrapolating |
|---|---|---:|---:|---|---:|---:|---:|---:|
| +2% | uniform | Rs.5,443,122 | 3.34% | -0.19% (-0.19..+0.04) | -0.41% | Rs.-645,943 | 134 | 0
| +2% | smart | Rs.5,434,645 | 3.32% | -0.04% (-0.04..+0.22) | -0.16% | Rs.-258,015 | 33 | 0
| -2% | uniform | Rs.5,229,666 | 3.19% | +0.07% (+0.12..-0.02) | +0.17% | Rs.+277,821 | 220 | 82
| -2% | smart | Rs.5,229,666 | 3.14% | +1.05% (+1.30..+0.69) | +1.88% | Rs.+2,976,591 | 84 | 0
| -4% | uniform | Rs.5,122,938 | 3.12% | +0.13% (+0.24..-0.05) | +0.35% | Rs.+553,460 | 363 | 220
| -4% | smart | Rs.5,122,938 | 3.08% | +1.03% (+1.31..+0.61) | +1.90% | Rs.+3,013,138 | 84 | 0
| -6% | uniform | Rs.5,016,211 | 3.05% | +0.20% (+0.36..-0.07) | +0.52% | Rs.+827,059 | 409 | 267
| -6% | smart | Rs.5,016,211 | 3.01% | +1.00% (+1.33..+0.53) | +1.93% | Rs.+3,050,560 | 84 | 0
| -8% | uniform | Rs.4,909,483 | 2.99% | +0.26% (+0.48..-0.09) | +0.69% | Rs.+1,098,686 | 409 | 269
| -8% | smart | Rs.4,909,483 | 2.95% | +0.98% (+1.34..+0.45) | +1.95% | Rs.+3,088,895 | 84 | 0
| -10% | uniform | Rs.4,802,755 | 2.92% | +0.32% (+0.60..-0.11) | +0.86% | Rs.+1,368,411 | 409 | 271
| -10% | smart | Rs.4,802,755 | 2.89% | +0.95% (+1.35..+0.37) | +1.97% | Rs.+3,124,523 | 85 | 0

**How to read it** — 'Sales Δ' is projected unit change vs today; the band is the elasticity-uncertainty range (optimistic edge clamped: demand cannot rise when a discount is cut). 'Extrapolating' counts cells pushed below any discount they have actually traded at — treat those rungs as directional, not confident. Any budget change actually executed is scored predicted-vs-actual by the weekly tracker — the ladder projects, the scorecard proves.

*The engine reports amounts; whether a rung is acceptable is a business decision, not a model verdict.*