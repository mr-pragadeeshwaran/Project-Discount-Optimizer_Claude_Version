"""
build_stage_workbook.py — the three-stage end-user workbook, SKU x city level.

One Excel file that walks a business reader through the maturity ladder:
  Stage 1 — Discount Response : where does discount actually increase sales?
  Stage 2 — Optimal Discount  : how much discount should each cell carry?
  Stage 3 — Promotion ROI     : did the discount create ECONOMIC value?
                                (incremental contribution / discount cost)

Everything is read from the latest run's existing outputs — no model is
re-fitted here. Derived columns are computed with the same local response
(marg_beta) and cost structure (COGS proxy + commission + fulfilment) the
engine itself uses, and every derivation is documented on the READ ME sheet.

Baselines are HONEST: "what the discount buys" is measured against each
cell's OBSERVED historical floor (the discount it has actually traded at),
never against an extrapolated zero.

Values-only workbook by design (an analysis snapshot, not a financial model
to edit): no live formulas, so nothing can mis-recalculate downstream.

Run:  python -X utf8 scripts/reports/build_stage_workbook.py
Out:  output/STATIQ_STAGE_REPORT.xlsx
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import v4_config as cfg

OUT_XLSX = os.path.join(ROOT, "output", "STATIQ_STAGE_REPORT.xlsx")
MONTH = 30.0 / 7.0

# ── house style ─────────────────────────────────────────────────────────────
INK, BODY, MUTED = "0F172A", "334155", "64748B"
HEAD_FILL = PatternFill("solid", fgColor="1E293B")
GOOD_FILL = PatternFill("solid", fgColor="DCFCE7")   # creates value
BAD_FILL = PatternFill("solid", fgColor="FEE2E2")    # destroys value
GREY_FILL = PatternFill("solid", fgColor="F1F5F9")   # uncertain
NOTE_FONT = Font(name="Arial", size=9, italic=True, color=MUTED)
HAIR = Border(bottom=Side(style="hair", color="CBD5E1"))


def F(sz=10, bold=False, color=BODY, italic=False):
    return Font(name="Arial", size=sz, bold=bold, color=color, italic=italic)


def _latest_run():
    runs = sorted(glob.glob(os.path.join(ROOT, "output", "runs", "20*")))
    for r in reversed(runs):
        if os.path.exists(os.path.join(r, "plan", "all_cells.csv")):
            return r
    raise SystemExit("no run with a plan found — run the monthly rebuild first")


def _clean_pid(v):
    s = str(v).strip()
    try:
        f = float(s)
        if abs(f - round(f)) < 1e-9:
            return str(int(round(f)))
    except ValueError:
        pass
    return s


def _contribution_unit(price, mrp):
    """Per-unit contribution under the engine's cost structure (COGS proxy)."""
    return (price - (float(cfg.DEFAULT_COGS_PCT) * mrp
                     + float(cfg.DEFAULT_COMMISSION_PCT) * price
                     + float(cfg.DEFAULT_FULFILLMENT_FEE)))


def load_joined(run):
    ac = pd.read_csv(os.path.join(run, "plan", "all_cells.csv"))
    rec = pd.read_csv(os.path.join(run, "recommendations.csv"))
    keep = ["cell_id", "grammage", "historical_floor_disc", "elasticity",
            "rec_discount_pct", "elbow_discount_pct", "confidence_score",
            "confidence_tier", "phasing_plan"]
    rec = rec[[c for c in keep if c in rec.columns]]
    d = ac.merge(rec, on="cell_id", how="left")

    pr_path = os.path.join(ROOT, "output", "DISCOUNT_PLAN", "pricing", "pricing_reco.csv")
    if os.path.exists(pr_path):
        pr = pd.read_csv(pr_path)
        pr["pid"] = pr["product_id"].map(_clean_pid)
        d["pid"] = d["product_id"].map(_clean_pid)
        d = d.merge(pr[["pid", "city", "opt_disc", "pred_units_delta_pct",
                        "pred_rev_delta_pct"]], on=["pid", "city"], how="left")
    ag_path = os.path.join(ROOT, "output", "DISCOUNT_PLAN", "pricing", "agreement.csv")
    if os.path.exists(ag_path):
        ag = pd.read_csv(ag_path)[["cell_id", "agree_with_cut"]]
        d = d.merge(ag, on="cell_id", how="left")

    # ── derived, per cell (documented on READ ME) ──
    d["floor"] = pd.to_numeric(d.get("historical_floor_disc"), errors="coerce") \
        .fillna(pd.to_numeric(d.get("tgt_disc"), errors="coerce")) \
        .fillna(d["cur_disc"]).clip(lower=0)
    d["floor"] = np.minimum(d["floor"], d["cur_disc"])          # floor never above today
    beta = pd.to_numeric(d["marg_beta"], errors="coerce").fillna(0.0)
    gap = (d["cur_disc"] - d["floor"]).clip(lower=0)

    u_now = pd.to_numeric(d["cur_units_wk"], errors="coerce").fillna(0.0)
    mrp = pd.to_numeric(d["mrp"], errors="coerce")
    p_now = pd.to_numeric(d["cur_price"], errors="coerce")
    p_floor = mrp * (1 - d["floor"] / 100.0)
    u_floor = u_now * np.exp(-beta * gap)                       # local response model

    d["uplift_pct"] = (np.where(u_floor > 0, u_now / u_floor - 1.0, 0.0)) * 100
    d["incr_units_wk"] = u_now - u_floor
    d["rev_uplift_wk"] = u_now * p_now - u_floor * p_floor
    contrib_now = u_now * _contribution_unit(p_now, mrp)
    contrib_floor = u_floor * _contribution_unit(p_floor, mrp)
    d["margin_impact_wk"] = contrib_now - contrib_floor
    d["incr_contrib_mo"] = d["margin_impact_wk"] * MONTH

    spend_now_wk = pd.to_numeric(d["disc_spend_mo"], errors="coerce").fillna(0.0) / MONTH
    spend_floor_wk = u_floor * mrp * (d["floor"] / 100.0)
    d["slice_cost_mo"] = ((spend_now_wk - spend_floor_wk) * MONTH).clip(lower=0)
    d["contrib_roi"] = np.where(d["slice_cost_mo"] > 1.0,
                                d["incr_contrib_mo"] / d["slice_cost_mo"], np.nan)

    # Verdicts carry the engine's BUCKET-BEFORE-ACTION rule: a cell can be
    # statistically below the pay-line yet availability-constrained — the
    # action there is FIX STOCK, never trim. Only bucket-c cells say "trim".
    def _verdict(r):
        if bool(r.get("reliably_pays")):
            return "DISCOUNT WORKS — creates value"
        if bool(r.get("reliably_waste")):
            b = str(r.get("bucket", ""))
            if b == "c_waste_cut":
                return "NOT WORKING — trim to floor"
            if b == "a_stock":
                return "NOT WORKING, but stock-constrained — FIX AVAILABILITY first"
            if b == "b_competitive":
                return "NOT WORKING, but competitive pressure — HOLD, defensive"
            return "NOT WORKING — monitor (gates keep it out of the cut wave)"
        return "UNCERTAIN — monitor / test"
    d["verdict"] = d.apply(_verdict, axis=1)
    return d


# ── sheet writers ───────────────────────────────────────────────────────────
def _write_table(ws, title, subtitle, headers, rows, widths, fmts, verdict_col=None):
    ws.cell(1, 1, title).font = F(14, bold=True, color=INK)
    ws.cell(2, 1, subtitle).font = NOTE_FONT
    hr = 4
    for j, h in enumerate(headers, 1):
        c = ws.cell(hr, j, h)
        c.font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center",
                                horizontal="center" if j > 6 else "left")
    for i, row in enumerate(rows, hr + 1):
        for j, v in enumerate(row, 1):
            c = ws.cell(i, j, v)
            c.font = F(9)
            c.border = HAIR
            fmt = fmts.get(j)
            if fmt:
                c.number_format = fmt
            if verdict_col and j == verdict_col and isinstance(v, str):
                # red ONLY where the action is actually "trim" — a below-pay-line
                # cell held for stock/competitive reasons is grey (bucket rule).
                c.fill = (GOOD_FILL if "WORKS" in v or "CREATES" in v
                          else BAD_FILL if "trim to floor" in v or "DESTROYS" in v
                          else GREY_FILL)
    for j, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(hr + 1, 3).coordinate
    ws.auto_filter.ref = f"A{hr}:{get_column_letter(len(headers))}{hr + len(rows)}"


def sheet_stage1(wb, d):
    ws = wb.create_sheet("Stage 1 — Discount Response")
    dd = d.sort_values(["verdict", "margin_impact_wk"])
    headers = ["product_id", "cell_id", "Product", "Pack", "City", "Category",
               "Weeks", "OSA %", "Disc % now", "Price now", "MRP", "Units/wk",
               "Response per +1pt (% units)", "Pay-line per pt (%)",
               "Sales uplift % (vs proven floor)", "Incremental units/wk",
               "Revenue uplift Rs/wk", "Margin impact Rs/wk", "Verdict", "Confidence"]
    rows = [[r["product_id"], r["cell_id"], str(r["title"])[:38],
             r.get("grammage", ""), r["city"], r["category"], r.get("n_weeks"),
             round(float(r["osa_mean"]), 0), round(float(r["cur_disc"]), 1),
             round(float(r["cur_price"]), 1), round(float(r["mrp"]), 0),
             round(float(r["cur_units_wk"]), 1),
             round(float(r["marg_beta"]) * 100, 3) if pd.notna(r["marg_beta"]) else None,
             round(float(r["be_beta"]) * 100, 3) if pd.notna(r["be_beta"]) else None,
             round(float(r["uplift_pct"]), 2), round(float(r["incr_units_wk"]), 1),
             round(float(r["rev_uplift_wk"])), round(float(r["margin_impact_wk"])),
             r["verdict"], r["confidence"]]
            for _, r in dd.iterrows()]
    fmts = {10: "0.0", 12: "#,##0.0", 17: "#,##0", 18: "#,##0"}
    _write_table(ws, "Stage 1 — Where does discount increase sales?",
                 "Response ISOLATED from availability, ad visibility, competition and "
                 "season. Uplift measured vs each cell's OBSERVED floor discount — never "
                 "an extrapolated zero. Margin uses the 50%-of-MRP COGS PROXY.",
                 headers, rows,
                 [10, 22, 30, 9, 12, 15, 6, 6, 8, 8, 7, 9, 11, 10, 11, 11, 11, 11, 30, 12],
                 fmts, verdict_col=19)


def sheet_stage2(wb, d):
    ws = wb.create_sheet("Stage 2 — Optimal Discount")
    dd = d.sort_values(["title", "city"])
    headers = ["product_id", "cell_id", "Product", "Pack", "City", "Category",
               "Disc % now", "Proven floor %", "Champion target %",
               "Pipeline elbow %", "Optimizer optimal %", "Engines agree on cut?",
               "SET THIS WEEK (governed) %", "Projected units Δ%", "Projected revenue Δ%",
               "Confidence"]
    rows = []
    for _, r in dd.iterrows():
        is_cut = (r.get("bucket") == "c_waste_cut") and bool(r.get("agree_with_cut", False))
        set_now = float(r["tgt_disc"]) if (is_cut and pd.notna(r.get("tgt_disc"))) \
            else float(r["cur_disc"])
        rows.append([r["product_id"], r["cell_id"], str(r["title"])[:38],
                     r.get("grammage", ""), r["city"], r["category"],
                     round(float(r["cur_disc"]), 1), round(float(r["floor"]), 1),
                     round(float(r["tgt_disc"]), 1) if pd.notna(r.get("tgt_disc")) else None,
                     round(float(r["rec_discount_pct"]), 1) if pd.notna(r.get("rec_discount_pct")) else None,
                     round(float(r["opt_disc"]), 1) if pd.notna(r.get("opt_disc")) else None,
                     "YES" if bool(r.get("agree_with_cut", False)) else "",
                     round(set_now, 1),
                     round(float(r["pred_units_delta_pct"]), 2) if pd.notna(r.get("pred_units_delta_pct")) else None,
                     round(float(r["pred_rev_delta_pct"]), 2) if pd.notna(r.get("pred_rev_delta_pct")) else None,
                     r["confidence"]])
    _write_table(ws, "Stage 2 — How much discount should each cell carry?",
                 "Three independent answers (champion target, pipeline elbow, portfolio "
                 "optimizer) and the governed number the tracker actually issues — a cut "
                 "executes only where BOTH engines agree, glide-limited weekly.",
                 headers, rows,
                 [10, 22, 30, 9, 12, 15, 8, 8, 9, 9, 9, 9, 11, 9, 9, 12], {})


def sheet_stage3(wb, d):
    ws = wb.create_sheet("Stage 3 — Promotion ROI")
    dd = d.sort_values("contrib_roi")
    headers = ["product_id", "cell_id", "Product", "Pack", "City", "Category",
               "Disc % now", "Discount cost Rs/mo (total)",
               "Trimmable slice cost Rs/mo (floor→now)",
               "Incremental contribution Rs/mo (slice)",
               "CONTRIBUTION ROI (incr. contribution ÷ slice cost)",
               "Marginal ROI (last point)", "Net gain if trimmed Rs/mo",
               "Economic verdict", "Why (engine's reason)"]
    rows = []
    for _, r in dd.iterrows():
        roi = r["contrib_roi"]
        b = str(r.get("bucket", ""))
        if bool(r.get("reliably_pays")):
            ev = "CREATES VALUE — protect / consider reinvest"
        elif bool(r.get("reliably_waste")) and b == "c_waste_cut":
            ev = "DESTROYS VALUE — trim to floor"
        elif bool(r.get("reliably_waste")) and b == "a_stock":
            ev = "BELOW PAY-LINE, stock-constrained — fix availability, don't trim"
        elif bool(r.get("reliably_waste")) and b == "b_competitive":
            ev = "BELOW PAY-LINE, competitive — hold, defensive"
        elif bool(r.get("reliably_waste")):
            ev = "BELOW PAY-LINE — monitor (kept out of cut wave)"
        else:
            ev = "UNCERTAIN — monitor / test"
        rows.append([r["product_id"], r["cell_id"], str(r["title"])[:38],
                     r.get("grammage", ""), r["city"], r["category"],
                     round(float(r["cur_disc"]), 1),
                     round(float(r["disc_spend_mo"])) if pd.notna(r["disc_spend_mo"]) else None,
                     round(float(r["slice_cost_mo"])),
                     round(float(r["incr_contrib_mo"])),
                     round(float(roi), 2) if pd.notna(roi) else None,
                     round(float(r["marginal_roas"]), 2) if pd.notna(r.get("marginal_roas")) else None,
                     round(float(r["net_gain_mo"])) if pd.notna(r.get("net_gain_mo")) else None,
                     ev, str(r.get("decision_reason", ""))[:80]])
    fmts = {8: "#,##0", 9: "#,##0", 10: "#,##0", 13: "#,##0"}
    _write_table(ws, "Stage 3 — Did the discount create ECONOMIC value?",
                 "The metric is Incremental Contribution ÷ Discount Cost (not sales "
                 "uplift). ROI < 1 = the discount costs more than the margin it brings. "
                 "Contribution uses the 50% COGS PROXY until real per-SKU costs arrive — "
                 "every rupee figure inherits it.",
                 headers, rows,
                 [10, 22, 30, 9, 12, 15, 8, 11, 12, 12, 13, 9, 11, 26, 50],
                 fmts, verdict_col=14)


def sheet_summary(wb, d, run):
    ws = wb.create_sheet("Portfolio Summary", 1)
    ws.cell(1, 1, "Portfolio Summary — the whole story on one sheet").font = F(14, True, INK)
    ws.cell(2, 1, f"Run {os.path.basename(run)} · {cfg.BRAND_NAME} on "
                  f"{cfg.PLATFORM_NAME} · amounts only, no verdicts on sufficiency"
            ).font = NOTE_FONT
    n_works = int(d["reliably_pays"].fillna(False).astype(bool).sum())
    n_trim = int((d["bucket"] == "c_waste_cut").sum())
    n_held = int((d["reliably_waste"].fillna(False).astype(bool)
                  & (d["bucket"] != "c_waste_cut")).sum())
    n_unc = len(d) - n_works - n_trim - n_held
    spend = float(pd.to_numeric(d["disc_spend_mo"], errors="coerce").sum())
    cut_gain = float(pd.to_numeric(
        d.loc[d["bucket"] == "c_waste_cut", "net_gain_mo"], errors="coerce")
        .clip(lower=0).sum())
    facts = [
        ("Cells analysed (SKU-pack x city)", len(d)),
        ("Total discount spend, Rs/mo", round(spend)),
        ("Cells where discount reliably WORKS", n_works),
        ("Cells to TRIM now (below pay-line, all gates clear)", n_trim),
        ("Below pay-line but HELD (stock/competitive/monitor)", n_held),
        ("Cells uncertain (monitor/test)", n_unc),
        ("Confident recoverable value if trimmed, Rs/mo", round(cut_gain)),
    ]
    r0 = 4
    for i, (k, v) in enumerate(facts):
        ws.cell(r0 + i, 1, k).font = F(10)
        c = ws.cell(r0 + i, 2, v)
        c.font = F(11, bold=True, color=INK)
        c.number_format = "#,##0"
    r0 += len(facts) + 2
    ws.cell(r0, 1, "By category").font = F(11, True, INK)
    g = (d.groupby("category")
         .agg(cells=("cell_id", "count"),
              spend_mo=("disc_spend_mo", "sum"),
              works=("reliably_pays", "sum"),
              not_working=("reliably_waste", "sum"))
         .reset_index().sort_values("spend_mo", ascending=False))
    hdr = ["Category", "Cells", "Discount spend Rs/mo", "Works", "Not working"]
    for j, h in enumerate(hdr, 1):
        c = ws.cell(r0 + 1, j, h)
        c.font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
    for i, (_, r) in enumerate(g.iterrows(), r0 + 2):
        ws.cell(i, 1, r["category"]).font = F(9)
        ws.cell(i, 2, int(r["cells"])).font = F(9)
        c = ws.cell(i, 3, round(float(r["spend_mo"])))
        c.font = F(9); c.number_format = "#,##0"
        ws.cell(i, 4, int(r["works"])).font = F(9)
        ws.cell(i, 5, int(r["not_working"])).font = F(9)
    for j, w in enumerate([34, 8, 16, 8, 11], 1):
        ws.column_dimensions[get_column_letter(j)].width = w


def sheet_readme(wb):
    ws = wb.create_sheet("READ ME", 0)
    lines = [
        ("StatIQ Lab — Three-Stage Discount Report", 14, True),
        ("How to read this workbook, and exactly how every number is made.", 9, False),
        ("", 9, False),
        ("STAGE 1 — WHERE DOES DISCOUNT INCREASE SALES?", 11, True),
        ("The engine isolates discount's effect from availability (OSA), ad visibility,", 9, False),
        ("competitor price/availability and season, per SKU-pack x city cell.", 9, False),
        ("'Response per +1pt' = % unit change per extra discount point, everything else held equal.", 9, False),
        ("'Pay-line' = the response needed for a discount point to pay for itself.", 9, False),
        ("Uplift/units/revenue/margin are measured vs the cell's OBSERVED floor discount", 9, False),
        ("(the lowest it has actually traded at) — never vs an extrapolated 0%.", 9, False),
        ("", 9, False),
        ("STAGE 2 — HOW MUCH DISCOUNT SHOULD EACH CELL CARRY?", 11, True),
        ("Champion target = confounder-model target (floor-based).  Pipeline elbow =", 9, False),
        ("margin-optimal point on the saturation curve.  Optimizer optimal = portfolio", 9, False),
        ("optimum with cross-SKU substitution.  'SET THIS WEEK' is the governed number:", 9, False),
        ("a cut is issued only where BOTH engines agree, moved max 3ppt/week (glide).", 9, False),
        ("", 9, False),
        ("STAGE 3 — DID THE DISCOUNT CREATE ECONOMIC VALUE?", 11, True),
        ("CONTRIBUTION ROI = incremental contribution / cost of the trimmable discount", 9, False),
        ("slice (floor→today), on the engine's cost structure. ROI < 1 destroys value.", 9, False),
        ("'Marginal ROI' asks the same at the margin: does the LAST point pay?", 9, False),
        ("", 9, False),
        ("HONESTY NOTES — READ BEFORE QUOTING", 11, True),
        (f"1. Costs use the {float(cfg.DEFAULT_COGS_PCT)*100:.0f}%-of-MRP COGS PROXY + "
         f"{float(cfg.DEFAULT_COMMISSION_PCT)*100:.0f}% commission + Rs.{float(cfg.DEFAULT_FULFILLMENT_FEE):.0f}/unit "
         "fulfilment. Real per-SKU costs will move every margin figure.", 9, False),
        ("2. ~10 weeks of data: many cells carry category-level (shrunk) estimates and are", 9, False),
        ("   marked Low/Experimental confidence. Act on High; test the rest.", 9, False),
        ("3. Values-only snapshot generated from the run named on the Summary sheet;", 9, False),
        ("   regenerate with scripts/reports/build_stage_workbook.py after each rebuild.", 9, False),
        ("4. Colour code: green = reliably creates value, red = reliably below pay-line,", 9, False),
        ("   grey = uncertain (monitor/test).", 9, False),
    ]
    for i, (t, sz, b) in enumerate(lines, 1):
        ws.cell(i, 1, t).font = F(sz, bold=b, color=INK if b else BODY)
    ws.column_dimensions["A"].width = 110


def main():
    run = _latest_run()
    d = load_joined(run)
    print(f"[stage-report] run {os.path.basename(run)} | {len(d)} cells")
    wb = Workbook()
    wb.remove(wb.active)
    sheet_readme(wb)
    sheet_summary(wb, d, run)
    sheet_stage1(wb, d)
    sheet_stage2(wb, d)
    sheet_stage3(wb, d)
    wb.save(OUT_XLSX)
    print(f"[stage-report] wrote {OUT_XLSX}")


if __name__ == "__main__":
    main()
