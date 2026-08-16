# 18 — Performance & Memory

*Audience: engineers. The deployment machine has 5.9 GB of RAM with about
1 GB typically free. That is not a footnote — it produced real bugs and
real fixes, and several design choices only make sense once you know it.*

## 1. The hardware reality

Everything runs on one small Windows machine (Python 3.12 in `.venv`,
pinned `requirements.txt`). There is no cluster, no worker pool, no
horizontal scaling — "performance work" here means fitting an
8-stage statistical pipeline plus a differential-evolution optimizer into
roughly 1 GB of headroom without silently degrading the statistics. The
failure mode to fear is not slowness; it is a `MemoryError` that a
fallback path swallows into worse numbers. That exact thing happened once
(§2) and drove the current design.

## 2. Stage 4: the fixed-effects memory budget

**The incident.** Stage 4 fits a per-category fixed-effects regression
with a Huber loss; the formula path materializes `C(sku_city)` as
**dense dummy columns**. For the dominant category (hundreds of cells ×
tens of thousands of rows) the design matrix needs ~100 MB, with several
copies alive during IRLS/SVD. On this machine that failed as
`MemoryError: Unable to allocate 86.2 MiB` — and the failure was silent
at the report level: every cell in that category fell back to the
generic default elasticity. Quiet quality loss, not a crash.

**The fix** (`stage4_model/elasticity.py`, around `_FE_DUMMY_BUDGET_MB`):

- Before fitting, `_fit_category()` estimates the dummy-matrix footprint:
  `est_mb = rows × (n_cells + n_regressors + 5) × 8 / 1e6`.
- Above the budget — `_FE_DUMMY_BUDGET_MB = 32.0` — it never builds the
  dummy matrix. Instead `_fit_category_within()` fits the **same
  fixed-effects model via the within (FWL) transformation**: demean
  `log_units` and every regressor within each cell, then regress on the
  cells-free demeaned system. By Frisch–Waugh–Lovell this yields
  **identical OLS coefficients** to the dummy model (and the standard
  Huber-weighted FE estimator on the RLM path). Standard errors are
  scaled back by the absorbed-FE degrees of freedom (`dof_factor`), and
  cell intercepts are recovered from cell means so `.predict()` still
  works downstream.
- A `MemoryError` raised mid-fit on the dummy path also routes to the
  within path, so the budget number never has to be exactly right.

The important framing: **the within path is not an approximation or a
degraded mode**. It is the same estimator with a memory-free design
matrix. That is why §7's advice for bigger hardware is *not* "raise the
budget and get better numbers" — there are no better numbers to get.

## 3. Pipeline memory discipline

Two habits keep the 8-stage run (`pipeline.py`) inside the envelope:

**Chunked ingestion of all-brand exports.** The raw platform CSVs cover
every brand, not just the client's, and can be very large. Stage 1 reads
them with `pd.read_csv(..., dtype=str, chunksize=200000)` and applies the
own-brand filter **per chunk** before concatenating
(`stage1_ingestion/ingest.py::_read_source_own`). The full all-brand
frame never materializes; only own-brand rows survive into memory.

**Free the raw frame the moment it's consumed.** Even filtered, `raw_df`
is the largest object in the run. No stage after Stage 2 reads it, so
`pipeline.py` drops it immediately after the fact table is built
(`context.pop("raw_df", None)`, with a comment saying why) — Stage 4's
fits get that RAM.

Every stage also persists its main output to the run directory
(`fact_table.csv`, `features.csv`, `elasticity_estimates.csv`, …), which
is what lets `--stages` re-run later stages without holding earlier
intermediates alive.

## 4. The DE optimizer: where the CPU time goes

The pricing engine's optimizer (`scripts/pricing/de_optimizer.py`, driven
by `scripts/pricing/pricing_engine.py`) is the most expensive compute in
the repo. Two structural decisions keep it tractable:

**Exact decomposition instead of one giant search.**
`pricing_engine.py::optimize_decomposed` exploits the fact that
cross-price terms only link SKUs within the same (category, city): each
group is an **independent subproblem** (largest ~18 SKUs) rather than one
526-dimensional DE. This is exact — no cross-group coupling exists to
lose — and it is the single biggest cost reduction in the system.

**Bounded multi-run ensemble per group.** Each group runs
`scipy.optimize.differential_evolution` up to `n_seeds` times, run *s*
using `seed=s` and the varied config `ROBUST_GRID[s % 8]`
(mutation/recombination/popsize/init; entry 0 is the pre-protocol
champion config, so run 0 is bit-identical to the old behavior). Each run
is bounded by `maxiter=60` and a wall-clock callback. The convergence
record lands in `gates.json` under `de_robustness`.

## 5. The fast knobs (all config, no code changes)

| Knob | Default | Where | Effect |
|---|---|---|---|
| `n_seeds` | 2 in `pricing_engine.py::CONFIG` (optimizer clamps to 1–8) | config dict | Runs per group. The comment says it: "526-dim DE is costly; 2 seeds keeps a full run tractable." Biggest lever both ways. |
| `de_time_cap_s` | 120 s/run | config dict | Wall-clock cap per DE run via callback; the run returns best-so-far. `None` = uncapped. |
| `de_agree_tol` | 1e-3 (relative) | config dict | Agreement early-stop: once ≥2 runs' best objectives agree within tolerance, remaining runs are skipped. |
| `--maxiter` / `--popsize` | 40 / 12 | `scripts/pricing/scenario_menu.py` CLI | The scenario menu is a comparison artifact, not the adopted plan, so its DE effort is deliberately trimmed and CLI-tunable. |
| `--draws` | 200 | `scripts/validation/sensitivity.py` CLI | Perturbation draws for the fragility count. |
| `pytest -m "not slow"` | 67 tests | `pytest.ini` | `slow` marks tests that train models; the fast set is the default development loop. |

The optimizer's own smoke test shows the floor: it runs with
`de_time_cap_s=1e-6, n_seeds=1` (`de_optimizer.py`, bottom) — useful when
you need the plumbing exercised, not the optimum.

Note what is deliberately **not** a knob: validation depth in the
monthly chain (gates, DML, challenger, backtest). Those runs are the
product's credibility; trim DE effort, not evidence.

## 6. What must NOT change with the environment

`requirements.txt` pins the exact stack and explains why: numpy **must**
stay 1.26.4 (never install PyMC — it force-upgrades numpy≥2 and
binary-breaks statsmodels/scikit-learn). The 2026-07-11 run's diverged
RLM fit (OOS R² = −9.99) came from an unpinned environment. This is a
performance-adjacent trap because the natural first move on a new, bigger
machine is a fresh `pip install` of latest-everything. Don't. Recreate
`.venv` from the pinned file and confirm `pytest tests/ -m "not slow"`
(67 pass) before trusting any numbers.

## 7. On bigger hardware

What actually improves, in order of payoff:

1. **More DE robustness per month, not different answers.** Raise
   `n_seeds` toward 8 to sweep the full `ROBUST_GRID`, and raise or
   remove `de_time_cap_s`. This buys confidence (tighter
   `de_robustness` spread in `gates.json`), and occasionally a better
   optimum on the hardest groups.
2. **Parallel DE.** Every `differential_evolution` call already passes
   `updating="deferred"` — the mode SciPy requires for `workers=-1`.
   Workers is currently *not* passed (serial, deliberately, on a 1
   GB-free machine); enabling it is a one-line change per call site in
   `de_optimizer.py` and `scenario_menu.py`. Mind RAM: each worker holds
   its own population copies.
3. **Bigger ingestion chunks.** `chunksize=200000` in
   `stage1_ingestion/ingest.py` can rise; the gain is modest since
   parsing dominates.
4. **The stage-4 budget can stay.** Raising `_FE_DUMMY_BUDGET_MB` makes
   more categories take the dummy path, but per §2 the within path fits
   the identical model — there is no accuracy to reclaim. Leave it, and
   keep the fallback battle-tested.

And keep `raw_df` freeing and per-chunk filtering as they are — they cost
nothing on big hardware and save the next small machine.

---

*Siblings: [17-security.md](17-security.md) (why this all stays on one
machine in the first place), [../README.md](../README.md) (docs home).
The live numbers referenced here (67 tests, run `20260810_143823`) date
from 2026-08-16; concepts outlive them.*
