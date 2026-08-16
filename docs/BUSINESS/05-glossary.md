# Glossary / Technology Dictionary

*Every term used anywhere in this project, translated once. Business terms
first, then technical terms.*

## The product's own vocabulary

| Term | Simple meaning | Example here |
|---|---|---|
| Cell | One product-pack in one city — the unit every decision is made at | "Turbo Chocolate 250ml × Kolkata" |
| Isolated response (β) | How much units move per point of discount, with everything else held constant | −0.0014 on the Kolkata cell — near zero |
| Pay-line | The response level where a discount point exactly pays for itself | 0.0121 on that cell — response is far below it |
| Elasticity | % unit change per 1% price change; −1 is the break-even of mathematics | Epigamia portfolio ≈ −1.0 (borderline) |
| Confidence interval (CI) | The honest range around an estimate; "reliably" means the whole range agrees | Cut only when even the optimistic edge is below the pay-line |
| Bucket | The single verdict each cell gets | cut / fix-stock / competitive-hold / test / monitor |
| Champion | The main waste-finding model | the confounder-controlled regression |
| Challenger | An alternative model that tries to beat the champion each rebuild | "does competition explain the waste instead?" |
| Double ML | An independent causal method used purely as a double-check | confirmed the ₹90,402 finding |
| Gates (C1–C8) | Eight pass/fail validation receipts on every plan | shown as chips on the dashboard |
| Glide | Max discount change per week (3 points) | 17.7% → 14.7%, not 17.7% → 10% overnight |
| Proven floor | Lowest discount the cell has actually traded at | trims stop there; tests never go below |
| Kill-switch | Two missed predictions → automatic revert | strike level printed on every KAM row |
| Hero SKU | A flagship you've declared untouchable | set in settings; tracker never auto-cuts it |
| Wave | A scheduled batch of 2–3 week price experiments | Wave 1: 15 cells, issued 17 Aug |
| Unlock condition | The specific evidence that would free a held cell | "needs 2 more weeks — ready 30 Aug" |
| Value staircase | Bankable now → in test → reallocation upside | the Summary sheet's top block |
| Scorecard / receipts | Predicted-vs-actual record, built weekly | the trust engine |
| KAM sheet | The Monday handoff the key-account manager executes | `WAVE1_KAM_SHEET_v2.xlsx` |
| Run | One complete monthly rebuild, stored as a timestamped folder | `output/runs/20260810_143823/` |

## General technical terms, translated

| Term | Simple meaning | In this project |
|---|---|---|
| Pipeline | A factory line: each station transforms the data and passes it on | the 8 numbered stages |
| Regression | The statistical tool that measures "how much does X move Y, holding others constant" | how responses and elasticities are estimated |
| Fixed effects | Comparing each cell only against itself over time, so big-city vs small-city differences can't pollute the answer | `C(cell)` in the model |
| Out-of-sample (OOS) | Testing predictions on weeks the model never saw | R² 0.965 receipt |
| R² | "Share of the movement the model explains", 0–1 | fit receipts |
| wMAPE | Average prediction error, weighted by size | 14% on holdout |
| Shrinkage / prior | Letting a thin cell borrow its category's typical answer instead of trusting 9 noisy weeks | why many cells show category-level estimates |
| Kernel / demand model | The shared "if price changes, units respond like this" calculator | powers optimizer, what-if, glide ladder |
| Optimizer | A search procedure trying thousands of discount combinations for the best portfolio outcome | the pricing engine's second opinion |
| Dashboard / UI | The screens you interact with | localhost:8765 |
| API | The waiter between screen and engine — carries requests and answers | the dashboard's internal channel to files |
| CSV / XLSX | Plain spreadsheet file formats | everything the system reads/writes |
| Config / settings | Named values that control behavior without code changes | `config/settings.xlsx` |
| Repo / Git / GitHub | The change-history vault for the code, and its online backup | every improvement is a recorded, reversible commit |
| Script | A runnable task | each Run Center button runs one |
| Fail-loud | Stop with a clear message instead of continuing wrongly | settings and input validation |
