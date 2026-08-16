"""
budget_glide.py — the budget ladder: what happens to sales if the discount
budget moves ±2%…−10%?

WHAT THIS IS (business framing)
-------------------------------
A brand plans its trade budget in small moves ("trim 4% next quarter"), not in
optimizer language. This table answers, for budget changes of +2%, −2%, −4%,
−6%, −8% and −10% of the CURRENT discount spend, how much sales (units and
revenue) are projected to move — under two allocation styles per rung:

  UNIFORM — every cell's discount scaled by the same factor (what a brand does
            without help: "cut everything a bit").
  SMART   — worst-marginal-ROI discounts cut first (what the engine would do),
            using the budget allocator's own ROI ladder for the cut ORDER and
            the shared demand kernel for the IMPACT.

The gap between the two curves is the value of allocating the cut well.

HONESTY RAILS
-------------
* Projection only — no optimizer runs; each rung is one evaluation of the SAME
  clamped demand kernel the optimizer/scenario menu use (de_optimizer.
  demand_model via build_problem), so this can never diverge from the
  validated machinery.
* Every rung carries an uncertainty band from the elasticity posteriors
  (own_elast shifted ±1.96·own_sd, the optimistic side clamped at 0 — demand
  can not respond positively to a price increase).
* Every rung reports how many moved cells leave their OBSERVED discount range
  (below the discount the cell has actually traded at) — those projections are
  extrapolation and are flagged, not hidden.
* No target verdict anywhere: the table reports amounts; sufficiency is a
  contract question.

Run:  python -X utf8 scripts/pricing/budget_glide.py
Outputs: output/DISCOUNT_PLAN/pricing/budget_glide.csv       (rung x mode)
         output/DISCOUNT_PLAN/pricing/budget_glide_cells.csv (per-cell detail)
         output/DISCOUNT_PLAN/pricing/BUDGET_GLIDE.md        (the readout)
"""
import os
import sys
import json
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import de_optimizer as de            # noqa: E402  shared clamped demand kernel
import pricing_engine as pe          # noqa: E402  config anchor + fact-table locator
import scenario_menu as sm           # noqa: E402  financial_chain (shared weekly KPIs)

OUT = os.path.join(ROOT, "output", "DISCOUNT_PLAN", "pricing")
ROI_LADDER = os.path.join(OUT, "roi_ladder.csv")

# Budget rungs, as fractions of CURRENT discount spend. Small, planning-sized
# moves (the brand's language): +2% covers "we may raise the budget";
# −2%…−10% is the trim ladder. Rungs are evaluated independently.
RUNGS = [0.02, -0.02, -0.04, -0.06, -0.08, -0.10]
MONTH = 30.0 / 7.0                   # weekly kernel -> monthly display


# ── allocation: turn a spend target into a discount vector ──────────────────
def _spend(disc_vec, P):
    return sm.financial_chain(disc_vec, P)["disc_spend_wk"]


def _uniform_vector(P, spend_target, obs_max):
    """Scale every cell's discount by one factor k so portfolio spend hits the
    target. k found by bisection through the real kernel (spend is nonlinear in
    discount because units respond). Increases are capped per cell at the
    discount the cell has actually traded at (obs_max) — no invented depths."""
    d0 = P["disc0"]

    def vec(k):
        return np.clip(d0 * k, 0.0, obs_max if k > 1.0 else None)

    lo_k, hi_k = 0.0, 1.0
    if spend_target > _spend(d0, P):
        lo_k, hi_k = 1.0, 3.0
        if _spend(vec(hi_k), P) < spend_target:      # capped everywhere — best we can do
            return vec(hi_k), False
    for _ in range(40):
        mid = 0.5 * (lo_k + hi_k)
        if _spend(vec(mid), P) > spend_target:
            hi_k = mid
        else:
            lo_k = mid
    return vec(0.5 * (lo_k + hi_k)), True


def _roi_rank(P):
    """Marginal ROI at each cell's CURRENT rung, from the budget allocator's
    roi_ladder (used only to ORDER the smart cut; impacts always come from the
    shared kernel). Cells without a ladder entry rank WORST — no evidence their
    discount earns anything. IDs are normalised through pe._clean_pid on BOTH
    sides (Excel-era floats like 98706.0 must still match '98706')."""
    rank = np.full(P["n"], -np.inf)
    if not os.path.exists(ROI_LADDER):
        print("[glide] roi_ladder.csv missing — smart mode falls back to uniform order")
        return rank
    lad = pd.read_csv(ROI_LADDER)
    lad["pid"] = lad["product_id"].map(pe._clean_pid)
    by_cell = {k: g.sort_values("disc") for k, g in lad.groupby(["pid", "city"])}
    cells = P["cells"]
    matched = 0
    for i in range(P["n"]):
        key = (pe._clean_pid(cells.iloc[i]["product_id"]), str(cells.iloc[i]["city"]))
        g = by_cell.get(key)
        if g is None:
            continue
        matched += 1
        below = g[g["disc"] <= P["disc0"][i] + 1e-6]
        if len(below) and pd.notna(below.iloc[-1]["marginal_roi"]):
            rank[i] = float(below.iloc[-1]["marginal_roi"])
    print(f"[glide] ROI-ladder rank: {matched}/{P['n']} cells matched, "
          f"{int(np.isfinite(rank).sum())} with a usable marginal ROI")
    if matched == 0:
        print("[glide] WARNING: no ladder matches — smart cut order is effectively arbitrary")
    return rank


def _smart_vector(P, spend_target, obs_min, obs_max, roi):
    """Cut (or add) discount cell by cell in ROI order — worst marginal ROI
    first when trimming, best first when adding — until the spend target is
    met; the final cell is bisected for an exact landing.

    The cut FLOOR is each cell's OBSERVED minimum discount (the proven-safe
    floor the whole system glides toward) — smart mode never invents a depth
    the cell has not traded at, exactly like the tracker's historical-floor
    rule. If every cell is at its floor before the target is reached,
    target_hit=False is reported honestly rather than extrapolating."""
    d = P["disc0"].astype(float).copy()
    cutting = spend_target < _spend(d, P)
    order = np.argsort(roi) if cutting else np.argsort(-roi)
    for i in order:
        if cutting and d[i] <= obs_min[i] + 1e-9:
            continue
        if not cutting and d[i] >= obs_max[i] - 1e-9:
            continue
        trial = d.copy()
        trial[i] = obs_min[i] if cutting else obs_max[i]
        s = _spend(trial, P)
        if (cutting and s > spend_target) or (not cutting and s < spend_target):
            d = trial                                  # full move, keep walking
            continue
        lo_d, hi_d = (obs_min[i], d[i]) if cutting else (d[i], obs_max[i])
        for _ in range(40):                            # partial move on the last cell
            mid = 0.5 * (lo_d + hi_d)
            trial[i] = mid
            if _spend(trial, P) > spend_target:
                if cutting:
                    hi_d = mid
                else:
                    lo_d = mid
            else:
                if cutting:
                    lo_d = mid
                else:
                    hi_d = mid
        d[i] = 0.5 * (lo_d + hi_d)
        return d, True
    return d, False                                    # ran out of room before target


# ── uncertainty band: same vectors through shifted-elasticity kernels ───────
def _band_problems(elast_df, cross_df, baseline_df, config):
    """Kernels at the elasticity CI edges. 'least' = own shifted toward 0
    (clamped at 0 — a price rise cannot lift demand), 'most' = own 1.96 sd more
    negative. Applied to the SAME discount vectors, they bracket the sales move."""
    e_lo = elast_df.copy()
    e_lo["own_elast"] = np.minimum(e_lo["own_elast"] + 1.96 * e_lo["own_sd"], 0.0)
    e_hi = elast_df.copy()
    e_hi["own_elast"] = e_hi["own_elast"] - 1.96 * e_hi["own_sd"]
    return (de.build_problem(e_lo, cross_df, baseline_df, config),
            de.build_problem(e_hi, cross_df, baseline_df, config))


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    fact, run = pe._latest_fact_table()
    run_name = os.path.basename(run)
    print(f"[glide] fact_table: {run_name}")
    import pricing_panel as pp
    panel = pp.build_pricing_panel(fact)
    elast_df, cross_df, baseline_df, _gates = pe.eh.estimate_elasticities(panel)

    config = dict(pe.CONFIG)
    P = de.build_problem(elast_df, cross_df, baseline_df, config)
    P_lo, P_hi = _band_problems(elast_df, cross_df, baseline_df, config)
    print(f"[glide] {P['n']} cells | evaluating {len(RUNGS)} rungs x 2 allocation modes "
          f"(kernel evaluations only — no optimizer)")

    # Observed discount range per cell, from the weekly panel — the honesty rail.
    obs = panel.groupby(["product_id", "city"])["disc"].agg(["min", "max"])
    cells = P["cells"]
    keys = list(zip(cells["product_id"], cells["city"]))
    obs_min = np.array([obs.loc[k, "min"] if k in obs.index else 0.0 for k in keys])
    obs_max = np.array([obs.loc[k, "max"] if k in obs.index else P["disc0"][i]
                        for i, k in enumerate(keys)])
    roi = _roi_rank(P)

    base = sm.financial_chain(P["disc0"], P)
    rows, cell_rows = [], []
    for r in RUNGS:
        spend_target = base["disc_spend_wk"] * (1.0 + r)
        for mode, builder in (("uniform", _uniform_vector), ("smart", _smart_vector)):
            dv, hit = (builder(P, spend_target, obs_max) if mode == "uniform"
                       else builder(P, spend_target, obs_min, obs_max, roi))
            ch = sm.financial_chain(dv, P)
            ch_lo = sm.financial_chain(dv, P_lo)       # least-response kernel
            ch_hi = sm.financial_chain(dv, P_hi)       # most-response kernel
            base_lo = sm.financial_chain(P["disc0"], P_lo)
            base_hi = sm.financial_chain(P["disc0"], P_hi)
            moved = np.abs(dv - P["disc0"]) > 0.05
            below_obs = moved & (dv < obs_min - 1e-6)
            rows.append({
                "budget_change_pct": round(r * 100, 1),
                "mode": mode,
                "spend_mo": round(ch["disc_spend_wk"] * MONTH),
                "spend_delta_mo": round((ch["disc_spend_wk"] - base["disc_spend_wk"]) * MONTH),
                "weighted_disc_pct": round(ch["wavg_disc_pct"], 2),
                "sales_units_delta_pct": round((ch["units_wk"] / base["units_wk"] - 1) * 100, 3),
                "sales_units_delta_pct_least": round(
                    (ch_lo["units_wk"] / base_lo["units_wk"] - 1) * 100, 3),
                "sales_units_delta_pct_most": round(
                    (ch_hi["units_wk"] / base_hi["units_wk"] - 1) * 100, 3),
                "revenue_delta_pct": round((ch["revenue_wk"] / base["revenue_wk"] - 1) * 100, 3),
                "net_revenue_delta_mo": round(
                    ((ch["revenue_wk"]) - (base["revenue_wk"])) * MONTH),
                # NB: no profit column by design — profit would need a COGS
                # assumption; this surface stays in observable revenue space.
                "cells_moved": int(moved.sum()),
                "cells_below_observed_range": int(below_obs.sum()),
                "target_hit": bool(hit),
            })
            for i in np.where(moved)[0]:
                cell_rows.append({
                    "product_id": cells.iloc[i]["product_id"],
                    "cell_id": f"{cells.iloc[i]['product_id']}_{cells.iloc[i]['city']}",
                    "city": cells.iloc[i]["city"],
                    "budget_change_pct": round(r * 100, 1), "mode": mode,
                    "disc_now": round(float(P["disc0"][i]), 2),
                    "disc_new": round(float(dv[i]), 2),
                    "below_observed_range": bool(below_obs[i]),
                })

    glide = pd.DataFrame(rows)
    glide.to_csv(os.path.join(OUT, "budget_glide.csv"), index=False)
    pd.DataFrame(cell_rows).to_csv(os.path.join(OUT, "budget_glide_cells.csv"), index=False)
    _write_md(glide, base, run_name)
    print(f"[glide] wrote {os.path.join(OUT, 'budget_glide.csv')}, "
          f"budget_glide_cells.csv, BUDGET_GLIDE.md ({time.time()-t0:.0f}s)")
    return glide


def _write_md(glide, base, run_name):
    spend_mo = base["disc_spend_wk"] * MONTH
    L = [
        "# Budget Glide Ladder — if the discount budget moves, what happens to sales?",
        f"\n*Run `{run_name}` · current spend Rs.{spend_mo:,.0f}/mo "
        f"(weighted discount {base['wavg_disc_pct']:.2f}%) · projections from the "
        f"validated demand kernel — no optimizer, no target verdicts.*\n",
        "Each budget rung is shown under two allocation styles: **uniform** (every "
        "discount scaled equally — what a brand does unaided) and **smart** (worst "
        "marginal-ROI discounts cut first, per the budget allocator's ladder). The "
        "gap between them is the value of allocating the change well.\n",
        "| Budget | Mode | Spend/mo | Wt disc | Sales Δ (band) | Revenue Δ | Net revenue Δ/mo | Cells moved | Extrapolating |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for _, x in glide.iterrows():
        band = (f"{x['sales_units_delta_pct']:+.2f}% "
                f"({x['sales_units_delta_pct_least']:+.2f}..{x['sales_units_delta_pct_most']:+.2f})")
        L.append(f"| {x['budget_change_pct']:+.0f}% | {x['mode']} | "
                 f"Rs.{x['spend_mo']:,.0f} | {x['weighted_disc_pct']:.2f}% | {band} | "
                 f"{x['revenue_delta_pct']:+.2f}% | Rs.{x['net_revenue_delta_mo']:+,.0f} | "
                 f"{x['cells_moved']} | {x['cells_below_observed_range']}")
    L += [
        "",
        "**How to read it** — 'Sales Δ' is projected unit change vs today; the band is "
        "the elasticity-uncertainty range (optimistic edge clamped: demand cannot rise "
        "when a discount is cut). 'Extrapolating' counts cells pushed below any "
        "discount they have actually traded at — treat those rungs as directional, "
        "not confident. Any budget change actually executed is scored "
        "predicted-vs-actual by the weekly tracker — the ladder projects, the "
        "scorecard proves.",
        "",
        "*The engine reports amounts; whether a rung is acceptable is a business "
        "decision, not a model verdict.*",
    ]
    open(os.path.join(OUT, "BUDGET_GLIDE.md"), "w", encoding="utf-8").write("\n".join(L))


if __name__ == "__main__":
    main()
