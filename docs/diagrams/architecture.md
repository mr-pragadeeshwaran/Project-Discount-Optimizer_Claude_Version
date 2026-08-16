# Architecture — the components and how they hang together

*A file-based analytical engine with a thin local web front. No database,
no cloud, no services — the "architecture" is a disciplined arrangement of
Python modules around a shared filesystem contract.*

Sibling diagrams: [system-context](system-context.md) ·
[user-flow](user-flow.md) · [data-flow](data-flow.md) ·
[critical-workflows](critical-workflows.md) ·
Deeper prose: `docs/TECHNICAL/10-system-architecture.md`

---

## The business picture

```
SETTINGS (one Excel file, every knob)
   -> ENGINE (8 stages: clean -> model -> recommend)
   -> JUDGES (champion model + independent DML + C-gates + challenger)
   -> PLANNERS (pricing engine, budget, promo calendar, scenarios)
   -> SAFETY (weekly tracker: glide, caps, agreement, kill-switch)
   -> DELIVERABLES (versioned workbooks the KAM can execute)
   ... all watched from ONE local dashboard with live receipts
```

Layers only ever talk through files on disk. Any layer can be re-run alone;
the result is the same because the inputs are the same files.

## Technical component diagram

```mermaid
flowchart TB
    subgraph cfg["Configuration layer"]
        vc["v4_config.py (defaults)"]
        sl["settings_loader.py\nconfig/settings.xlsx overrides\nunknown key = SettingsError (fail-loud)"]
        sl --> vc
    end

    subgraph eng["Engine — pipeline.py orchestrates stages 1-8"]
        s1["stage1_ingestion\ningest + validate (hard fails)"]
        s2["stage2_preparation\nfact table, outlier log"]
        s3["stage3_features"]
        s4["stage4_model/elasticity.py\nper-category FE + Huber RLM\nwithin/FWL above 32MB dummy budget\nJames-Stein shrunk cell elasticities"]
        s5["stage5_curves"]
        s6["stage6_economics\n(cost knobs internal-only)"]
        s7["stage7_guardrails\ntiering -> recommendations.csv"]
        s8["stage8_output\nwaste & reinvest report"]
        s1 --> s2 --> s3 --> s4 --> s5 --> s6 --> s7 --> s8
    end

    subgraph causal["Causal chain — scripts/analysis/"]
        champ["discount_plan.py (champion)\nweekly panel, MODEL v2.1:\nlog1p(units) ~ C(cell) + disc + controls\n(rpi_w + comp, OSA, Ad SOV, month)"]
        dml["dml_estimate.py\nDouble ML, HistGBR nuisances,\nK=5 cross-fit, Neyman-orthogonal"]
        gates["validate_plan.py\ngates C1-C5, C7, C8\n(C6 savings-target gate REMOVED by design)"]
        chal["challenger.py\nModel B + competitor controls\npre-registered adoption rule\n-> defense_hold.csv"]
        champ --> dml --> gates
        champ --> chal
    end

    subgraph plans["Planning suite — scripts/pricing/ + scripts/promo/"]
        pe["pricing_engine.py\npanel -> hier elasticities -> DE optimizer\n-> agreement.csv (engine #2)"]
        ba["budget_allocator.py\nmarginal-ROI waterline @ 12% cap"]
        sm["scenario_menu.py + budget_glide.py"]
        milp["promo_calendar_milp.py\n12-week calendar, spacing rules"]
    end

    subgraph safety["Weekly safety loop — scripts/tracker/"]
        wt["weekly_tracker.py (orchestrator)"]
        gr["guardrail.py\nglide <=3ppt/wk, revenue-protect,\n12% budget cap"]
        ks["killswitch.py\n2 strikes -> revert, confounders excused,\nportfolio drift brake"]
        sc2["scorecard.py + actuals.py + seasonality.py"]
        wbk["workbook.py -> WEEKLY_TRACKER.xlsx"]
        vl["verify_loop.py\nproves LOOP CLOSED: YES"]
        wt --> gr
        wt --> ks
        wt --> sc2
        wt --> wbk
    end

    subgraph verify["Validation — scripts/validation/"]
        bt["backtest_rolling.py (honest FAIL now:\nneeds 12 training weeks, feed has 10)"]
        eg["elasticity_gates.py (3/3 PASS)"]
        sens["sensitivity.py (200 draws, 0 fragile)"]
        oa["outlier_promo_audit.py"]
    end

    subgraph deliver["Reports — scripts/reports/"]
        bsw["build_stage_workbook.py\nSTATIQ_STAGE_REPORT_v&lt;N&gt;.xlsx (versioned)"]
        bwk["build_wave_kam_sheet.py\nWAVE&lt;N&gt;_KAM_SHEET_v&lt;K&gt;.xlsx\n+ wave&lt;N&gt;_issued.csv"]
    end

    subgraph front["Frontend — ui/"]
        app["app.py — stdlib ThreadingHTTPServer\n127.0.0.1:8765, STEPS allowlist,\none job at a time, live log"]
        html["index.html (single file, polls JSON)"]
        app --- html
    end

    cfg --> eng
    cfg --> causal
    cfg --> safety
    eng -- "runs/&lt;ts&gt;/ files" --> causal
    causal -- "plan/ + defense_hold" --> safety
    plans -- "agreement.csv" --> safety
    eng -- "fact_table" --> plans
    eng --> verify
    safety --> deliver
    front -- "subprocess (allowlisted)" --> eng
    front -- "reads artifacts as receipts" --> deliver
```

## Component responsibilities in one line each

| Component | Responsibility | Key files |
|---|---|---|
| Config | Every knob from a file; blank = default, unknown key = error | `settings_loader.py`, `v4_config.py`, `config/settings.xlsx` |
| Engine | Raw CSV → cleaned facts → elasticities → tiered recommendations | `pipeline.py`, `stage1_…`–`stage8_…` |
| Causal chain | Prove the waste is real: champion estimate, independent DML check, hard gates, competitor challenger | `scripts/analysis/` |
| Planning | Turn "true waste" into an executable plan: prices, budget, calendar, scenarios | `scripts/pricing/`, `scripts/promo/` |
| Safety loop | Small guarded weekly steps, self-scoring, automatic revert | `scripts/tracker/` |
| Validation | Attack the model: walk-forward, gates, perturbation, audit | `scripts/validation/` |
| Reports | Versioned, KAM-executable workbooks | `scripts/reports/` |
| Frontend | See + run everything locally; receipts from current-run files | `ui/app.py`, `ui/index.html` |

## Where classic architecture concepts map to

- **Database →** the filesystem contract: immutable `output/runs/<ts>/`
  folders plus the living `output/DISCOUNT_PLAN/` state directory. Joins
  happen in pandas; the join key is `product_id`/`cell_id`, present first
  in every table.
- **Service boundaries →** process boundaries. Each script is a standalone
  `python -X utf8 <script>` run from repo root; the UI composes them via
  subprocess with an allowlist, never imports them into its own process.
- **Deployment →** `launch_ui.bat` (or `.claude/launch.json` →
  `dashboard`). Python 3.12 venv at `.venv`, pinned `requirements.txt`.
- **Monitoring →** the receipts panel + `stage8_monitoring/` +
  `scripts/tracker/scorecard.py`; alerts are rows in files, not pages.
- **CI/CD →** none; local `pytest tests/ -m "not slow"` (67 pass) is the
  merge bar, and the validation suite is the release bar.

## Design decisions an engineer must not "fix"

1. **No savings target anywhere** — gate C6 was deliberately removed;
   the engine reports amounts + spend share, never grades sufficiency.
2. **No COGS/margin user-facing** — revenue-space ROI only; cost knobs
   feed guardrails internally.
3. **Versioned deliverables** — never overwrite a delivered workbook.
4. **Fail-loud everywhere** — bad settings or bad input stop the run with
   the offending key/column named; silence is the only forbidden outcome.
5. **Stale receipts are bugs** — every dashboard chip is recomputed from
   the current run's artifacts at request time.

## Legend

- **Champion / engine #2** — `discount_plan.py` and `pricing_engine.py`;
  a cut ships only where `agreement.csv` shows both engines agree.
- **FWL / within transform** — fitting fixed effects by demeaning within
  cell instead of building the dummy matrix; identical coefficients,
  bounded memory.
- **Receipt** — a pass/fail chip in the UI backed by a current-run file.
- **Allowlist** — the `STEPS` dict in `ui/app.py`; the complete set of
  things the frontend can execute.
