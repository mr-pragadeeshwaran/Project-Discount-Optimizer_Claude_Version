# PricingAI — Portfolio Elasticity & Optimized Discount Plan

*Adapted from PepsiCo PricingAI (hierarchical elasticity → differential-evolution optimizer). Run `20260810_143823` · 92 SKUs × 10 cities · no Gurobi, no cloud — runs on your laptop.*

## 1. What this adds over the per-cell tool

Your current tool judges each SKU×city **in isolation**. This adds the missing portfolio physics: **cross-price elasticity (cannibalization)** — cutting one SKU's discount changes its siblings' sales. That's the difference between 'this SKU's sales held' and 'the *portfolio* gained'.

## 2. Elasticities (conjugate_bayes_empirical_hierarchical)

- Own-price: median **-0.99** with median posterior SD **±0.80** — **true Bayesian bands, no hard clip**. An informative negative prior + hierarchical shrinkage replaces the old clip.
- **7/7 categories are LOW-CONFIDENCE** (wide band): once confounders are controlled, within-cell price variation barely identifies own-price. That's the honest signal — the same weak-identification wall, now shown as uncertainty instead of a fabricated point estimate.
- Cross-price substitute links: **26832** (positive = siblings gain when a SKU's price rises).

**Per-category confidence** (own-price posterior; low-confidence = wide band, act via TEST only — do NOT bank the saving):

| Category | Own-price | ± SD | Confidence |
|---|---:|---:|---|
| Curd | -0.99 | 0.80 | LOW — test only |
| Milkshake | -0.99 | 0.80 | LOW — test only |
| Mishti Doi | -0.99 | 0.80 | LOW — test only |
| Lassi | -1.00 | 0.80 | LOW — test only |
| Yogurt | -0.99 | 0.80 | LOW — test only |
| Almond Milk | -0.99 | 0.79 | LOW — test only |
| Protein Milkshake | -0.93 | 0.77 | LOW — test only |

**7/7 categories are low-confidence.** The Bayesian path applies NO clip — a wide band is reported honestly as uncertainty, not squeezed into a fabricated point estimate. **Low-confidence cells should be acted on only via a live test, never banked as a booked saving.**

**Strongest cannibalization links** (cut one → the other absorbs it):

- 566324 ↔ 472127: cross-elast +0.15
- 566324 ↔ 472127: cross-elast +0.15
- 472127 ↔ 566324: cross-elast +0.15
- 566324 ↔ 472127: cross-elast +0.15
- 472127 ↔ 566324: cross-elast +0.15
- 566324 ↔ 472127: cross-elast +0.15
- 472127 ↔ 566324: cross-elast +0.15
- 472127 ↔ 566324: cross-elast +0.15

## 3. The honesty check — does the ₹6.98L cut list survive cross-price?

- Simulated the existing **7 waste-cuts** through the cross-price model.
- Portfolio revenue impact: **+0.04%**; 5 sibling cells gain volume.
- **Verdict: cuts hold at PORTFOLIO level.**

## 4. Optimized discount plan (portfolio-aware)

Objective = **revenue**, subject to: revenue ≥ 98% of baseline, ≤3ppt weekly change, price-per-kg ladders (bigger pack cheaper/kg), psychological ₹-thresholds.

- Projected: revenue **+1.4%**, volume **+0.7%**, NRW **+0.7%**.
- 4 cells get more discount, 426 get less.

| SKU | City | Disc now→opt | Pred rev Δ% |
|---|---|---|---:|
| 541681 | Mumbai | 15%→12% | +8.0% |
| 540432 | Mumbai | 17%→14% | +7.9% |
| 560813 | Mumbai | 18%→15% | +7.9% |
| 540438 | Mumbai | 18%→15% | +7.9% |
| 541681 | Others | 15%→12% | +7.8% |
| 541681 | Delhi-NCR | 15%→12% | +7.8% |
| 540432 | Others | 17%→14% | +7.7% |
| 540432 | Delhi-NCR | 17%→14% | +7.7% |
| 560813 | Others | 18%→15% | +7.7% |
| 540438 | Others | 18%→15% | +7.7% |

## 5. Reinvest — where discount reliably PAYS

_reinvest_list empty_

## Engine agreement

Of the **7 discount_plan waste-cuts**, the pricing optimizer independently agrees to **cut 7**. On the rest it would instead **hold 0** and **raise 0** `agreement.csv` records this per cell; the tracker only actually cuts a waste cell when the optimizer also says cut (`agree_with_cut=True`) — otherwise it HOLDs and tests first, so the two engines never quietly contradict each other.

- Both engines cut: **7/7**
- Pricing engine would HOLD (test first): **0**
- Pricing engine would RAISE discount: **0**

_Schema: `agreement.csv` = cell_id, product_id, city, pricing_action ('cut'|'raise'|'hold'), agree_with_cut (bool). agree_with_cut = (cell in waste cut_list) AND (pricing_action=='cut')._


_Elasticities are TRUE Bayesian posteriors (conjugate, informative negative prior, empirical-Bayes hierarchical shrinkage) — mean **and** SD, no hard clip. PyMC was attempted but forces numpy≥2 which binary-breaks the repo's sklearn stack; the analytic conjugate posterior is the same Bayesian object without the dependency conflict._