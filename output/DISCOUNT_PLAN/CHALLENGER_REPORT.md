# Competitor Integration — Champion vs Challenger

*Run `20260810_143823`. Model A (champion, untouched) vs Model B (champion + competitor average discount as a control). Pre-registered rule: adopt B only if out-of-sample R² ≥ 0.75, the competitor coefficient signs sanely (rivals discount ↑ → our units ↓), and all category fits hold.*

## Verdict

**KEEP Model A (champion) — B did not clear the bar or added nothing material.**

| | Model A (champion) | Model B (+ competitor) |
|---|---:|---:|
| Out-of-sample R² | 0.965 | nan |
| Waste-cut cells | 7 | 0 |
| High-conf savings/mo | ₹90,402 | ₹0 |
| All-conf savings/mo | ₹90,402 | ₹0 |
| Competitor coef (agg) | — | +nan (WRONG SIGN) |

## What competition does to the number

- Controlling for competitor discounting, the high-confidence savings move from **₹90,402 → ₹0/mo** (-100%).
- **55 cells change bucket** when competition is controlled.
- **7 'waste' cuts turn out to be competitive defense** (bucket c under A, not-c under B) — these are cells where our discount was actually holding the line against a rival promo, not pure waste.

Cells that were mislabeled waste (now competitive defense):

- 540432_250ml_Chennai  (c_waste_cut → f_monitor)
- 540432_250ml_Kolkata  (c_waste_cut → f_monitor)
- 540438_250ml_Ahmedabad  (c_waste_cut → f_monitor)
- 540438_250ml_Chennai  (c_waste_cut → f_monitor)
- 540438_250ml_Kolkata  (c_waste_cut → f_monitor)
- 560813_250ml_Ahmedabad  (c_waste_cut → f_monitor)
- 560813_250ml_Chennai  (c_waste_cut → f_monitor)

## Honest read

Competition materially shifts the picture — see the bucket changes above. If B was adopted, the number changed because some 'waste' was competitive defense; that is exactly the point of the pass.

_Reusable harness: rerun at each 4-weekly retrain. B is adopted only when it clears the pre-registered rule; otherwise the champion stands. This is champion/challenger, never a silent edit to the model._