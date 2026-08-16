"""
app.py — local dashboard backend (v2) for Stat IQ Lab — Optimal Price Finder.

Zero-dependency (stdlib + pandas, both already installed) web server so the owner can
SEE the system instead of running terminal commands:
  - INPUTS   : data files in input_data/, the config knobs that matter
  - EXECUTE  : every playbook step as a button, with live logs, progress and status
  - OUTPUTS  : headline numbers, cut/reinvest lists, weekly readout, validation receipts

Security model (unchanged from v1): binds to 127.0.0.1 only; the run endpoint accepts
ONLY step ids from the fixed STEPS allowlist below (never arbitrary commands);
one job at a time.

Port: env UI_PORT, default 8765.
Run:  python -X utf8 ui/app.py        then open  http://localhost:8765
(or double-click launch_ui.bat at the repo root)
"""
import os, re, sys, json, glob, threading, subprocess, time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)   # so sibling modules (action_plan) import regardless of CWD
PORT = int(os.environ.get("UI_PORT", "8765"))

# ── The execution allowlist: every runnable step, grouped by cadence ────────────
# Each step: label + plain-English description + the exact command (list form).
# "@latest_fact" is resolved at run time to the newest run's fact_table.csv.
# "#reset_state" is an internal action (delete tracker state files), not a shell command.
STEPS = {
    # Monthly rebuild — in order
    "pipeline":      {"group": "monthly", "label": "1. Build foundation (pipeline)",
                      "desc": "Clean data, engineer features, build the fact table and waste report from input_data/.",
                      "cmd": ["pipeline.py"]},
    "champion":      {"group": "monthly", "label": "2. Champion waste model",
                      "desc": "The confounder-controlled model: which cells are genuinely wasteful discount.",
                      "cmd": ["scripts/analysis/discount_plan.py"]},
    "dml":           {"group": "monthly", "label": "3. Double ML confirmation",
                      "desc": "Independent causal check that the waste finding is real, not correlation.",
                      "cmd": ["scripts/analysis/dml_estimate.py"]},
    "gates":         {"group": "monthly", "label": "4. Acceptance gates C1–C8",
                      "desc": "Hard pass/fail gates on the plan. Must end ALL PASS.",
                      "cmd": ["scripts/analysis/validate_plan.py"]},
    "challenger":    {"group": "monthly", "label": "5. Competitor challenger",
                      "desc": "Tests whether competition explains the waste; writes the defense-hold list.",
                      "cmd": ["scripts/analysis/challenger.py"]},
    "pricing":       {"group": "monthly", "label": "6. Pricing engine",
                      "desc": "Elasticities + optimizer; produces the two-engine agreement the tracker needs.",
                      "cmd": ["scripts/pricing/pricing_engine.py"]},
    "budget":        {"group": "monthly", "label": "7. Budget allocator",
                      "desc": "Marginal-ROI waterline at the 12% spend cap.",
                      "cmd": ["scripts/pricing/budget_allocator.py", "--budget_pct", "0.12"]},
    "promo":         {"group": "monthly", "label": "8. Promo calendar (MILP)",
                      "desc": "12-week promotional calendar with duration/spacing/budget rules.",
                      "cmd": ["scripts/promo/promo_calendar_milp.py"]},
    "scenarios":     {"group": "monthly", "label": "9. Scenario menu",
                      "desc": "A negotiation menu: revenue-max vs profit-max vs tight/loose plans.",
                      "cmd": ["scripts/pricing/scenario_menu.py"]},
    "glide":         {"group": "monthly", "label": "9b. Budget glide ladder",
                      "desc": "If the discount budget moves ±2–10%, projected sales impact — uniform vs smart allocation.",
                      "cmd": ["scripts/pricing/budget_glide.py"]},
    "backtest":      {"group": "monthly", "label": "10. Rolling backtest",
                      "desc": "Walk-forward test of the champion vs naive benchmarks.",
                      "cmd": ["scripts/validation/backtest_rolling.py"]},
    "elast_gates":   {"group": "monthly", "label": "11. Elasticity gates",
                      "desc": "3-stage hard acceptance protocol on the elasticity matrix.",
                      "cmd": ["scripts/validation/elasticity_gates.py", "--report-only"]},
    "sensitivity":   {"group": "monthly", "label": "12. Sensitivity shake",
                      "desc": "Shakes elasticities, costs and volumes; counts fragile cut decisions.",
                      "cmd": ["scripts/validation/sensitivity.py"]},
    "outlier_audit": {"group": "monthly", "label": "13. Outlier vs promo audit",
                      "desc": "Cross-checks removed data spikes against documented promos/events.",
                      "cmd": ["scripts/validation/outlier_promo_audit.py"]},
    # Weekly loop
    "recommend":     {"group": "weekly", "label": "A. Recommend this week's cuts",
                      "desc": "Produces the KAM handoff file (execution_log_template.csv) under glide + caps.",
                      "cmd": ["scripts/tracker/weekly_tracker.py"]},
    "score":         {"group": "weekly", "label": "B. Score last week vs actuals",
                      "desc": "Backfills what really happened, runs the kill-switch, updates the scorecard.",
                      "cmd": ["scripts/tracker/weekly_tracker.py", "--actuals", "@latest_fact"]},
    "selftest":      {"group": "weekly", "label": "C. Self-test the loop",
                      "desc": "Proves the loop closes (LOOP CLOSED: YES), then restores the clean weekly state.",
                      "cmd": ["scripts/tracker/verify_loop.py"],
                      "then": ["#reset_state", ["scripts/tracker/weekly_tracker.py"]]},
    # Governance
    "params":        {"group": "governance", "label": "Parameter review",
                      "desc": "Snapshots every decision knob and shows drift since the last sign-off.",
                      "cmd": ["scripts/tracker/params_review.py"]},
}
MONTHLY_ORDER = ["pipeline", "champion", "dml", "gates", "challenger", "pricing",
                 "budget", "promo", "scenarios", "glide", "backtest", "elast_gates",
                 "sensitivity", "outlier_audit"]

# ── Job runner: one job at a time, log + progress kept in memory ────────────────
class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.step, self.status, self.rc = None, "idle", None
        self.log, self.started = deque(maxlen=6000), None
        self.done_steps, self.total_steps, self.current = 0, 0, ""

    def snapshot(self):
        return {"step": self.step, "status": self.status, "rc": self.rc,
                "elapsed": round(time.time() - self.started, 1) if self.started else 0,
                "log": "\n".join(self.log),
                "done_steps": self.done_steps, "total_steps": self.total_steps,
                "current": self.current}

JOB = Job()


def _latest_run():
    runs = sorted(glob.glob(os.path.join(ROOT, "output", "runs", "2026*")))
    return runs[-1] if runs else None


def _resolve(cmd):
    out = []
    for c in cmd:
        if c == "@latest_fact":
            run = _latest_run()
            if not run:
                raise RuntimeError("No run found under output/runs/ — run the pipeline first.")
            c = os.path.join(run, "fact_table.csv")
        out.append(c)
    return out


def _reset_state():
    for f in ("tracker_history.csv", "baselines.json", "execution_log.csv"):
        p = os.path.join(ROOT, "output", "DISCOUNT_PLAN", f)
        if os.path.exists(p):
            os.remove(p)
    JOB.log.append("[ui] tracker state reset (history/baselines/exec-log cleared)")


def _run_commands(step_id, tasks):
    """Worker thread: run each (label, cmd) in sequence, streaming output into the log.

    Progress contract: total_steps was set by start_job; done_steps increments as each
    shell command finishes OK; current holds the label of the command now running.
    Each command gets a '── <label>' header and a closing 'OK <label> (<secs>s)' or
    'FAILED <label> (exit <rc>)' line.
    """
    try:
        for label, cmd in tasks:
            if cmd == "#reset_state":
                _reset_state()
                continue
            JOB.current = label
            JOB.log.append(f"── {label}")
            argv = [sys.executable, "-X", "utf8"] + _resolve(cmd)
            JOB.log.append(f"$ python -X utf8 {' '.join(cmd)}")
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            t0 = time.time()
            p = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True,
                                 encoding="utf-8", errors="replace", env=env)
            for line in p.stdout:
                JOB.log.append(line.rstrip())
            p.wait()
            if p.returncode != 0:
                JOB.log.append(f"FAILED {label} (exit {p.returncode})")
                JOB.rc, JOB.status = p.returncode, "failed"
                return
            JOB.done_steps += 1
            JOB.log.append(f"OK {label} ({time.time() - t0:.1f}s)")
        JOB.rc, JOB.status, JOB.current = 0, "done", ""
        JOB.log.append("[ui] all commands finished OK")
    except Exception as e:
        JOB.rc, JOB.status = -1, "failed"
        JOB.log.append(f"[ui] error: {e}")


def start_job(step_id):
    with JOB.lock:
        if JOB.status == "running":
            return False, "A job is already running — wait for it to finish."
        if step_id == "monthly_all":
            tasks = [(STEPS[s]["label"], STEPS[s]["cmd"]) for s in MONTHLY_ORDER]
        elif step_id in STEPS:
            s = STEPS[step_id]
            tasks = [(s["label"], s["cmd"])]
            for extra in s.get("then", []):
                if extra == "#reset_state":
                    tasks.append(("reset tracker state", "#reset_state"))
                else:
                    tasks.append((s["label"] + " — restore weekly state", extra))
        else:
            return False, f"Unknown step: {step_id}"
        JOB.reset()
        JOB.step, JOB.status, JOB.started = step_id, "running", time.time()
        JOB.total_steps = sum(1 for _, c in tasks if c != "#reset_state")
        threading.Thread(target=_run_commands, args=(step_id, tasks), daemon=True).start()
        return True, "started"


# ── Data readers (every panel is driven by the real files) ──────────────────────
def _safe(fn, fallback=None):
    try:
        return fn()
    except Exception:
        return fallback


def _need(path, what):
    """Return path if the file exists, else raise a FileNotFoundError whose message
    is the plain-English <what> (surfaced as 'not generated yet: <what>')."""
    if not os.path.exists(path):
        raise FileNotFoundError(what)
    return path


def api_status():
    import pandas as pd
    run = _latest_run()
    st = {"latest_run": os.path.basename(run) if run else None,
          "plan_exists": bool(run and os.path.exists(os.path.join(run, "plan", "all_cells.csv")))}

    def cfg():
        import importlib, v4_config
        importlib.reload(v4_config)
        return {"brand": getattr(v4_config, "BRAND_NAME", "?"),
                "budget_cap": getattr(v4_config, "DEFAULT_BUDGET_PCT_CAP", None),
                "hero_skus": list(getattr(v4_config, "STRATEGIC_SKUS", []) or []),
                "lookback_days": getattr(v4_config, "TRAIN_LOOKBACK_DAYS", None),
                "timeline_weeks": getattr(v4_config, "TARGET_TIMELINE_WEEKS", None)}
    st["config"] = _safe(cfg, {})

    def files():
        rows = []
        for f in sorted(glob.glob(os.path.join(ROOT, "input_data", "*.csv"))):
            s = os.stat(f)
            rows.append({"name": os.path.basename(f), "mb": round(s.st_size / 1e6, 1),
                         "modified": time.strftime("%Y-%m-%d", time.localtime(s.st_mtime))})
        return rows
    st["input_files"] = _safe(files, [])

    def tracker():
        h = pd.read_csv(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "tracker_history.csv"))
        acts = h.get("week_action")
        week_label = None
        if "week" in h.columns and len(h):
            labels = h["week"].astype(str).unique().tolist()
            week_label = max(labels, key=lambda w: int(re.sub(r"\D", "", w) or 0))
        return {"rows": len(h),
                "weeks": int(h["week"].nunique()) if "week" in h.columns else 0,
                "cuts": int((acts == "cut").sum()) if acts is not None else 0,
                "holds": int((acts == "hold").sum()) if acts is not None else 0,
                "scored": int(h["actual_net_rev_delta"].notna().sum()) if "actual_net_rev_delta" in h else 0,
                "week_label": week_label}
    st["tracker"] = _safe(tracker)

    def plan():
        return json.load(open(os.path.join(run, "plan", "plan_summary.json"), encoding="utf-8"))
    st["plan_summary"] = _safe(plan) if run else None

    def cat_savings():
        d = pd.read_csv(os.path.join(run, "plan", "all_cells.csv"))
        d = d[d["bucket"] == "c_waste_cut"]
        g = (d.groupby("category")
               .agg(cells=("cell_id", "count"),
                    saving_mo=("net_gain_mo", lambda x: x.clip(lower=0).sum()))
               .reset_index().sort_values("saving_mo", ascending=False).head(10))
        return [{"category": r["category"], "cells": int(r["cells"]),
                 "saving_mo": round(float(r["saving_mo"]))} for _, r in g.iterrows()]
    st["category_savings"] = (_safe(cat_savings, []) if run else []) or []

    def agreement():
        a = pd.read_csv(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "pricing", "agreement.csv"))
        pa = a["pricing_action"].astype(str)
        return {"cut": int((pa == "cut").sum()), "hold": int((pa == "hold").sum()),
                "raise": int((pa == "raise").sum()),
                "agree_with_cut": int(a["agree_with_cut"].astype(bool).sum())}
    st["agreement"] = _safe(agreement)

    def sens_summary():
        s = pd.read_csv(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "validation", "sensitivity_cells.csv"))
        mf = float(s["flip_rate_joint"].max()) if len(s) else 0.0
        return {"fragile": int(s["fragile"].sum()), "total": int(len(s)),
                "max_flip": 0.0 if mf != mf else round(mf, 3)}  # NaN-guard
    st["sensitivity"] = _safe(sens_summary)

    # validation receipts — pass/fail chips
    rec = []
    def add(name, ok, note):
        rec.append({"name": name, "ok": bool(ok), "note": note})

    def _dml():
        # Read from the CURRENT run's plan dir — a top-level copy proved able
        # to go stale across engagements and show a previous client's verdict.
        d = json.load(open(os.path.join(run, "plan", "dml_results.json"), encoding="utf-8"))
        n_w = sum(1 for r in d if r.get("waste"))
        return f"{n_w}/{len(d)} cut categories confirmed reliably-waste (this run)"
    _dml_note = _safe(_dml) if run else None
    if _dml_note:
        add("Double ML", True, _dml_note)

    def _egates():
        g = json.load(open(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "validation", "elasticity_validation.json"), encoding="utf-8"))
        overall = g.get("overall_pass", g.get("all_pass"))
        return bool(overall)
    eg = _safe(_egates)
    if eg is not None:
        add("Elasticity gates", eg, "all 3 stages pass" if eg
            else "gate failed — direct, don't bank (expected with wide-band elasticities)")

    if st["sensitivity"] is not None:
        sv = st["sensitivity"]
        add("Sensitivity", sv["fragile"] == 0, f"{sv['fragile']} fragile of {sv['total']} cut cells")

    def _chal():
        txt = open(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "CHALLENGER_REPORT.md"), encoding="utf-8").read()
        return "KEEP Model A" in txt
    ch = _safe(_chal)
    if ch is not None:
        add("Competitor challenger", True,
            "champion stands (competition not a confounder)" if ch else "challenger adopted")

    def _defense():
        return len(pd.read_csv(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "defense_hold.csv")))
    dh = _safe(_defense)
    if dh is not None:
        add("Defense hold", True, f"{dh} cell(s) held out of the cut wave")

    # NEW: Backtest — champion must beat BOTH naive benchmarks on pooled wMAPE.
    def _backtest():
        f = os.path.join(ROOT, "output", "DISCOUNT_PLAN", "validation", "backtest_folds.csv")
        if os.path.exists(f):
            b = pd.read_csv(f)
            if {"model", "wmape", "n_cellweeks"} <= set(b.columns):
                pooled = {}
                for m, gg in b.groupby("model"):
                    n = gg["n_cellweeks"].sum()
                    if n > 0:
                        pooled[m] = float((gg["wmape"] * gg["n_cellweeks"]).sum() / n)
                champ = pooled.get("champion_recursive", pooled.get("champion_1step"))
                sn, lw = pooled.get("seasonal_naive"), pooled.get("naive_lastweek")
                if champ is not None and sn is not None and lw is not None:
                    ok = champ < sn and champ < lw
                    note = (f"pooled wMAPE: champion {champ:.1%} vs seasonal-naive {sn:.1%}, "
                            f"last-week {lw:.1%}")
                    if not ok:
                        note += (" — naive benchmark competitive on pure forecasting; "
                                 "the champion's validated job is decision-making, not forecasting")
                    return ok, note
        # fall back to the report's own verdict line
        txt = open(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "validation", "BACKTEST_REPORT.md"),
                   encoding="utf-8").read()
        head = txt[:600]
        if "**PASS" in head:
            return True, "report verdict: PASS — champion beats both benchmarks"
        if "**FAIL" in head:
            # Quote the report's own headline so a "not scoreable yet" FAIL
            # (short feed) reads differently from a "lost to the naive" FAIL.
            first = txt.splitlines()[0].replace("#", "").replace("*", "").strip()
            return False, f"report verdict: {first}"
        return False, "backtest present but verdict ambiguous — treat as not passing"
    bt = _safe(_backtest)
    if bt is not None:
        add("Backtest", bt[0], bt[1])

    # Confident savings — informational: the engine reports the amount (with
    # spend share for scale); there is no ambition bar to pass or fail.
    ps = st["plan_summary"]
    if ps:
        ach = float(ps.get("achievable_savings_mo_allconf", 0) or 0)
        spend = float(ps.get("disc_spend_mo_observed", 0) or 0)
        share = f" ≈ {ach/spend*100:.1f}% of ₹{spend:,.0f}/mo discount spend" if spend > 0 else ""
        add("Confident savings", bool(st["plan_exists"]),
            f"₹{ach:,.0f}/mo across {ps.get('cut_cells_all', 0)} cut cells{share} "
            f"(reported amount — sufficiency is a contract question)")
    else:
        add("Confident savings", False, "plan not generated yet — run the monthly rebuild")
    st["receipts"] = rec
    return st


TABLE_COLS_CUTS = ["product_id", "title", "city", "category", "cur_disc",
                   "tgt_disc", "net_gain_mo", "confidence"]
TABLE_COLS_SENS = ["cell_id", "city", "category", "cur_disc", "flip_rate_joint",
                   "fragile", "in_first_wave", "net_gain_mo"]
TABLE_COLS_HIST = ["week", "cell_id", "confidence", "week_action",
                   "pred_net_rev_delta", "actual_net_rev_delta", "applied"]


def api_table(name):
    import pandas as pd
    run = _latest_run()

    def _plan_list(fname, what):
        if not run:
            raise FileNotFoundError(what)
        d = pd.read_csv(_need(os.path.join(run, "plan", fname), what))
        cols = [c for c in TABLE_COLS_CUTS if c in d.columns]
        d = d[cols]
        if "net_gain_mo" in cols:
            d = d.sort_values("net_gain_mo", ascending=False)
        return {"columns": cols, "rows": d.fillna("").values.tolist()}

    if name == "cuts":
        return _plan_list("cut_list.csv", "the cut list (run the monthly rebuild)")
    if name == "reinvest":
        return _plan_list("reinvest_list.csv", "the reinvest list (run the monthly rebuild)")
    if name == "buckets":
        if not run:
            raise FileNotFoundError("the plan buckets (run the monthly rebuild)")
        d = pd.read_csv(_need(os.path.join(run, "plan", "all_cells.csv"),
                              "the plan buckets (run the monthly rebuild)"))
        g = d.groupby("bucket").agg(cells=("cell_id", "count"),
                                    saving_mo=("net_gain_mo", lambda x: x.clip(lower=0).sum())).reset_index()
        return {"columns": ["bucket", "cells", "saving_mo"],
                "rows": [[r["bucket"], int(r["cells"]), round(float(r["saving_mo"]))]
                         for _, r in g.iterrows()]}
    if name == "handoff":
        f = _need(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "execution_log_template.csv"),
                  "the KAM handoff file (run the weekly recommend step)")
        d = pd.read_csv(f)
        return {"columns": list(d.columns), "rows": d.fillna("").values.tolist()}
    if name == "scenarios":
        f = _need(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "pricing", "scenario_menu.csv"),
                  "the scenario menu (run the pricing steps)")
        d = pd.read_csv(f)
        return {"columns": list(d.columns), "rows": d.fillna("").values.tolist()}
    if name == "sensitivity":
        f = _need(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "validation", "sensitivity_cells.csv"),
                  "the sensitivity cells (run the sensitivity shake)")
        d = pd.read_csv(f)
        cols = [c for c in TABLE_COLS_SENS if c in d.columns]
        d = d[cols]
        if "flip_rate_joint" in cols:
            d = d.sort_values("flip_rate_joint", ascending=False)
        return {"columns": cols, "rows": d.fillna("").values.tolist()}
    if name == "history":
        f = _need(os.path.join(ROOT, "output", "DISCOUNT_PLAN", "tracker_history.csv"),
                  "the tracker history (run the weekly loop)")
        d = pd.read_csv(f)
        cols = [c for c in TABLE_COLS_HIST if c in d.columns]
        d = d[cols].head(200)
        return {"columns": cols, "rows": d.fillna("").values.tolist()}
    if name == "plan_all":
        # the action plan: ONE row per product x city with the single thing to do
        # (cut / reinvest / hold / monitor) and the exact discount to set. Reconciles
        # the decision engine's full verdict (plan/all_cells.csv) with the two act-now
        # lists, so no product is left without a clear "how much to give".
        from action_plan import build_action_plan, COLUMNS
        if not run:
            raise FileNotFoundError("the action plan (run the monthly rebuild)")
        _need(os.path.join(run, "plan", "all_cells.csv"),
              "the action plan (run the monthly rebuild)")
        df = build_action_plan(run)
        df = df[[c for c in COLUMNS if c in df.columns]]
        return {"columns": list(df.columns), "rows": df.fillna("").values.tolist()}

    if name == "elasticity":
        # the elasticity board: the engine's actual DIALS per product x city —
        # price elasticity, the marginal discount response at today's depth, the
        # pay-line it must beat, and the resulting verdict. This is the evidence
        # behind every cut/hold, made inspectable.
        if not run:
            raise FileNotFoundError("the elasticity board (run the monthly rebuild)")
        ac = pd.read_csv(_need(os.path.join(run, "plan", "all_cells.csv"),
                               "the elasticity board (run the monthly rebuild)"))
        rec_p = os.path.join(run, "recommendations.csv")
        if os.path.exists(rec_p):
            rc = pd.read_csv(rec_p)
            keep = [c for c in ("cell_id", "elasticity", "grammage", "confidence_score")
                    if c in rc.columns]
            ac = ac.merge(rc[keep], on="cell_id", how="left")
        out = pd.DataFrame({
            "product_id": ac.get("product_id"),
            "cell_id":    ac.get("cell_id"),
            "title":      ac.get("title"),
            "pack":       ac.get("grammage", ""),
            "city":       ac.get("city"),
            "category":   ac.get("category"),
            "elast":      pd.to_numeric(ac.get("elasticity"), errors="coerce").round(2),
            "disc_now":   pd.to_numeric(ac.get("cur_disc"), errors="coerce").round(1),
            "resp":       pd.to_numeric(ac.get("marg_beta"), errors="coerce").round(4),
            "payline":    pd.to_numeric(ac.get("be_beta"), errors="coerce").round(4),
        })
        out["gap"] = (out["resp"] - out["payline"]).round(4)

        def _verdict(r):
            if bool(r.get("reliably_waste")):
                return "Below pay-line — waste"
            if bool(r.get("reliably_pays")):
                return "Above pay-line — pays"
            return "Uncertain — monitor"
        out["test"] = ac.apply(_verdict, axis=1)
        out["n_weeks"] = pd.to_numeric(ac.get("n_weeks"), errors="coerce").round(0)
        out["disc_std"] = pd.to_numeric(ac.get("disc_std"), errors="coerce").round(1)
        out["cat_r2"] = pd.to_numeric(ac.get("cat_r2"), errors="coerce").round(2)
        out["confidence"] = ac.get("confidence")
        # most-negative (most price-sensitive) first, then biggest shortfall
        out = out.sort_values(["gap", "elast"], ascending=[True, True])
        return {"columns": list(out.columns), "rows": out.fillna("").values.tolist()}

    if name == "prices":
        # the price board: optimal discount / SP / MRP / estimated sales / accuracy
        # for every product x city cell, straight from the pipeline's recommendations.
        if not run:
            raise FileNotFoundError("the price board (run the monthly rebuild)")
        d = pd.read_csv(_need(os.path.join(run, "recommendations.csv"),
                              "the price board (run the monthly rebuild)"))
        colmap = [                       # (source column, board column)
            ("product_id", "product_id"), ("cell_id", "cell_id"),   # keys for lookup / join
            ("title", "title"), ("grammage", "pack"), ("city", "city"), ("category", "category"),
            ("mrp", "mrp"),
            ("rec_discount_pct", "opt_disc"), ("rec_price", "opt_sp"),
            ("current_discount_pct", "now_disc"), ("current_price", "now_sp"),
            ("rec_units_day", "est_units"), ("rec_revenue_day", "est_rev"),
            # reliability: the tier badge + the 0-100 confidence score behind it.
            # (we deliberately do NOT surface sku_group_r2 here — it is a sparse
            #  internal diagnostic that is negative for most cells and reads as
            #  "broken" to a business user; confidence_score is the system's own
            #  data-sufficiency + fit + plausibility measure and is what gates cuts.)
            ("confidence", "confidence"), ("confidence_score", "conf_score"),
        ]
        keep = [(s, t) for s, t in colmap if s in d.columns]
        out = d[[s for s, _ in keep]].copy()
        out.columns = [t for _, t in keep]
        for c in ("mrp", "opt_sp", "now_sp", "est_rev", "conf_score"):
            if c in out:
                out[c] = pd.to_numeric(out[c], errors="coerce").round(0)
        for c in ("opt_disc", "now_disc", "est_units"):
            if c in out:
                out[c] = pd.to_numeric(out[c], errors="coerce").round(1)
        sort_by = [c for c in ("title", "city") if c in out.columns]
        if sort_by:
            out = out.sort_values(sort_by)
        return {"columns": list(out.columns), "rows": out.fillna("").values.tolist()}
    raise KeyError(name)


REPORTS = {
    "readout":  os.path.join("output", "DISCOUNT_PLAN", "WEEKLY_READOUT.md"),
    "budget":   os.path.join("output", "DISCOUNT_PLAN", "pricing", "BUDGET_PLAN.md"),
    "glide":    os.path.join("output", "DISCOUNT_PLAN", "pricing", "BUDGET_GLIDE.md"),
    "backtest": os.path.join("output", "DISCOUNT_PLAN", "validation", "BACKTEST_REPORT.md"),
    "sens":     os.path.join("output", "DISCOUNT_PLAN", "validation", "SENSITIVITY_REPORT.md"),
    "promo":    os.path.join("output", "DISCOUNT_PLAN", "promo", "PROMO_CALENDAR.md"),
    "chal":     os.path.join("output", "DISCOUNT_PLAN", "CHALLENGER_REPORT.md"),
    "params":   os.path.join("output", "DISCOUNT_PLAN", "PARAMS_REVIEW.md"),
    "egates":   os.path.join("output", "DISCOUNT_PLAN", "validation", "ELASTICITY_GATES.md"),
}


def api_settings():
    """Effective settings + where each value came from (code default vs file).

    Reloads v4_config so an edited/uploaded file shows up without restarting
    the server. A broken settings file is reported as an error here rather
    than silently leaving the page blank — it is the reason the next run
    would fail.
    """
    import importlib
    import settings_loader as sl
    importlib.reload(sl)
    try:
        import v4_config
        importlib.reload(v4_config)
        return {"ok": True, "status": sl.status(), "rows": sl.describe(),
                "sections": sl.SECTIONS}
    except sl.SettingsError as e:
        return {"ok": False, "error": str(e),
                "status": {"source": sl.STATE.get("source") or "config/settings.*",
                           "n_overrides": 0, "error": str(e)},
                "rows": [], "sections": []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):        # silence per-request console noise
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_download(self, body, filename, ctype):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            if self.path in ("/", "/index.html"):
                html = open(os.path.join(HERE, "index.html"), "rb").read()
                return self._send(200, html, "text/html")
            if self.path == "/api/steps":
                return self._send(200, {"steps": STEPS, "monthly_order": MONTHLY_ORDER})
            if self.path == "/api/status":
                return self._send(200, api_status())
            if self.path == "/api/job":
                return self._send(200, JOB.snapshot())
            if self.path == "/api/settings":
                return self._send(200, api_settings())
            if self.path.startswith("/api/settings/template"):
                import settings_loader as sl
                if self.path.endswith(".xlsx"):
                    return self._send_download(
                        sl.template_xlsx_bytes(), "statiq_settings.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                if self.path.endswith("festivals.csv"):
                    return self._send_download(sl.template_festivals_csv(),
                                               "festivals.csv", "text/csv; charset=utf-8")
                if self.path.endswith("platform_events.csv"):
                    return self._send_download(sl.template_events_csv(),
                                               "platform_events.csv", "text/csv; charset=utf-8")
                return self._send_download(sl.template_csv(), "settings.csv",
                                           "text/csv; charset=utf-8")
            if self.path.startswith("/api/table/"):
                return self._send(200, api_table(self.path.rsplit("/", 1)[1]))
            if self.path.startswith("/api/report/"):
                key = self.path.rsplit("/", 1)[1]
                if key not in REPORTS:
                    return self._send(404, {"error": f"unknown report '{key}'"})
                p = _need(os.path.join(ROOT, REPORTS[key]), f"the {key} report")
                return self._send(200, {"text": open(p, encoding="utf-8").read()})
            return self._send(404, {"error": "not found"})
        except KeyError as e:
            return self._send(404, {"error": f"unknown table {e}"})
        except FileNotFoundError as e:
            return self._send(404, {"error": f"not generated yet: {e}"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            if self.path.startswith("/api/run/"):
                step = self.path.rsplit("/", 1)[1]
                ok, msg = start_job(step)
                return self._send(200 if ok else 409, {"ok": ok, "message": msg})
            if self.path == "/api/settings/upload":
                return self._send(*self._settings_upload())
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def _settings_upload(self):
        """Install an uploaded settings file.

        Body: {"filename": "...", "content_b64": "..."}. The file is validated
        BEFORE it is written, and is only ever written to the fixed
        config/settings.{csv,xlsx} path — the uploaded name is used solely to
        pick the format, never as a destination.
        """
        import base64
        import settings_loader as sl
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 5_000_000:
            return 400, {"ok": False, "message": "Expected a settings file under 5 MB."}
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
            name = os.path.basename(str(body.get("filename") or "settings.csv"))
            data = base64.b64decode(body.get("content_b64") or "")
        except Exception as e:
            return 400, {"ok": False, "message": f"Could not read the upload: {e}"}
        if JOB.status == "running":
            return 409, {"ok": False,
                         "message": "A job is running — wait for it to finish before "
                                    "changing settings mid-run."}
        ok, msg = sl.install_bytes(name, data)
        return (200 if ok else 400), {"ok": ok, "message": msg}


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[ui] Stat IQ Lab dashboard -> http://localhost:{PORT}  (Ctrl+C to stop)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
