# User Journeys — "what happens when I click this?"

*The dashboard (localhost:8765) is your control room. This is what each
important action actually does.*

## Journey 1 — Monthly rebuild (Run Center → steps 1–13, or "run all")

```text
I click "1. Build foundation"
↓ System reads every export in input_data, keeps my brand's rows
↓ Organizes history into cells; sets aside days that can't teach
↓ Measures response + elasticity; builds curves and economics
↓ Produces the run folder every later step reads
What I see: live log lines, then green completion; Inputs page updates
If it fails: a plain-English message names the missing column or bad setting
```

Steps 2–13 then, in order: the champion waste model, the Double-ML
double-check, the C-gates, the competitor challenger, the pricing engine,
budget allocator, promo calendar, scenario menu, budget glide ladder, rolling
backtest, elasticity gates, sensitivity shake, outlier audit. Each is one
button; each writes its receipt. **Order matters** — the dashboard runs them
correctly for you with "run all".

## Journey 2 — Issue the week (Weekly → "A. Recommend")

```text
I click "Recommend this week's cuts"
↓ System takes the validated plan
↓ Applies the safety committee (agreement, defense-hold, hero shield,
  glide limit, budget cap, kill-switch state)
↓ Writes the KAM handoff + the weekly workbook, records every prediction
What I see: "status GREEN | cut N hold M | projected ₹X/wk"
Business meaning: the model's opinion has become a governed, reversible plan
```

## Journey 3 — Score reality (Weekly → "B. Score last week")

```text
I click "Score last week vs actuals" (after the new export landed)
↓ System matches what really sold against every prediction it made
↓ Marks hits and misses; two misses on a cell → automatic revert
↓ Updates the accuracy scorecard the brand can audit
Business meaning: this click is where trust is manufactured
```

## Journey 4 — Change a setting (Inputs & Settings)

```text
I download the settings template, edit ONE value column, upload it
↓ System validates the file BEFORE accepting it
↓ A bad value is rejected with the exact reason; nothing half-applies
↓ Good values take effect on the next run
Business meaning: brand, competitors, caps and targets are spreadsheet
edits — never code changes. Onboarding a new client = new exports + a few
cells in this file.
```

## Journey 5 — Send the client report

```text
I run the stage-report script (or ask for it)
↓ System builds STATIQ_STAGE_REPORT_v<next>.xlsx from the latest run
↓ Old versions are never overwritten (what a client received stays intact)
What the brand gets: the value staircase, where discount works, optimal
levels, ROI, elasticity with accuracy receipts, the unlock pipeline and the
12-week confidence calendar — the whole argument in one file
```

## Journey 6 — Issue a test wave

```text
I run the wave sheet script (--wave N)
↓ System merges the governed cuts with wave-N experiment cells
↓ Each row: exact discount + price to set, predicted units, strike level
↓ An issue log is written so next week's scoring is automatic
Business meaning: this is how "not enough evidence" cells become evidence —
deliberately, on a calendar, with an automatic retreat rule
```

## What the KAM does with the sheet (the only journey off your machine)

Sets each row's discount on the platform console, marks Applied Y/N and any
deviation, returns the sheet. Amber rows are permanent steps; blue rows are
2–3 week experiments that must be left at the test level until the verdict.
