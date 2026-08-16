# Business Quickstart — the whole product in 30 minutes

*Written for the owner. No programming knowledge assumed. Current as of
2026-08-16 (Epigamia engagement, run `20260810_143823`).*

---

## In one sentence

Stat IQ Lab is a weekly pricing-intelligence service that takes a CPG brand's
raw quick-commerce sales export and tells it — with statistical proof — which
discounts are wasted money, which actually drive sales, exactly what to set
this Monday, and then checks its own predictions against reality every week.

## In one paragraph

Brands on platforms like Blinkit spend heavily on discounts without knowing
which ones work. Sales move for many reasons — stock availability, ad
visibility, festivals, competitors — and a discount running at the same time
usually takes the credit. This system separates those causes. It rebuilds the
brand's history into product-city "cells," measures each cell's true response
to discounting with every other factor held constant, double-checks that
finding with a second independent method, and only then recommends changes —
small weekly steps, never below prices the product has already traded at,
with an automatic retreat rule if reality disagrees. Everything it claims is
either backed by a validation receipt or explicitly labeled as needing a test.

## The main workflow (what you do)

1. **Monthly**: drop the platform's export files into the `input_data` folder,
   open the dashboard, press the Run Center steps in order (or "run all").
   ~1–2 hours of machine time; you watch progress live.
2. **Weekly**: hand the Monday sheet (the KAM handoff) to the key-account
   manager; they set the listed discounts and mark what they applied.
3. **Weekly**: when the next export arrives, run the scoring step. The system
   compares what it predicted against what actually happened, updates its
   accuracy scorecard, and auto-reverts anything that missed twice.
4. **For the brand**: send the versioned Stage Report workbook — it contains
   the findings, the evidence, and the plan, self-defending against the
   questions brands actually ask.

## Behind the scenes (what the system does)

It cleans the raw export; filters to the client's brand; groups history into
product×pack×city cells; marks days that can't teach anything (out-of-stock,
festivals); measures each cell's isolated discount response **and** its price
elasticity by two independent methods; runs eight validation gates plus an
independent causal double-check; sorts every cell into an action bucket
(cut / fix-stock-first / competitive-hold / test / monitor); and produces the
weekly sheet, the dashboard, and the client workbook. A committee of controls
(budget cap, glide limit, hero-SKU shield, two-engine agreement, kill-switch)
stands between any model opinion and a real price change.

## The important business rules (the short list)

- **A discount must beat its pay-line** — the response level where one point
  of discount pays for itself. Below the line reliably = waste.
- **No action without reliability** — a bad point estimate isn't enough; the
  whole confidence interval must be on the wrong side of the line.
- **Both engines must agree** before a cut is issued.
- **Never price below a level the product has already traded at.**
- **Max 3 points of discount change per week** (the glide).
- **Two missed predictions = automatic revert** (the kill-switch).
- **The engine reports amounts; it never grades them** — "is ₹X enough?" is a
  contract question, deliberately removed from the software.
- **No invented costs** — every number a brand sees is observable (units,
  prices, spend). No COGS assumptions anywhere client-facing.

## The important information (what data it uses)

Daily platform exports per product and city: units sold, revenue, price, MRP,
discount %, shelf availability, ad visibility share, category, plus
competitor rows used only to measure competitive pressure. It needs nothing
confidential from the brand — no cost sheets, no strategy documents.

## Current live position (Epigamia)

- ₹90,402/month of **confident** discount waste found (7 cells, all proofs
  passed) — first weekly step issued.
- ₹8.0 lakh/month **at stake in the test queue** — 3 waves of designed
  experiments, first wave issued for Monday 17 Aug (22-row KAM sheet).
- Portfolio accuracy receipts: out-of-sample R² 0.965, elasticity gates all
  pass, zero fragile recommendations under 200 stress shakes.
- Biggest single insight: **423 of 699 cells are availability-constrained** —
  Epigamia's largest recoverable lever on Blinkit is stock, not price.

## Biggest risks (honest list)

1. **The feedback loop must close.** Until applied sheets and weekly exports
   come back, the track record stays theoretical. This is the #1 asset to build.
2. **Ten weeks of history is thin.** Many cells carry borrowed (category-level)
   estimates, honestly labeled low-confidence. Time and test waves fix this.
3. **Single platform.** Blinkit only today; a shopper switching to Zepto is
   invisible. Contained by floors + kill-switch; solved by onboarding more
   platform exports (a data ask, not an engineering project).
4. **Single laptop.** All data and code live on one 6 GB machine. Until backed
   up externally, one hardware failure is an existential business risk.

## Where everything lives

| Thing | Where |
|---|---|
| The dashboard | `launch_ui.bat` → localhost:8765 |
| Raw inputs | `input_data/` |
| All settings (brand, competitors, knobs) | `config/settings.xlsx` — edited via the dashboard |
| Client deliverables (versioned, never overwritten) | `output/STATIQ_STAGE_REPORT_v*.xlsx`, `output/WAVE*_KAM_SHEET_v*.xlsx` |
| Weekly operational files | `output/DISCOUNT_PLAN/` |
| The engine's code | `pipeline.py`, numbered `stage*` folders, `scripts/` |
| This documentation | `docs/` (start here — deep library in `docs/reference/`, learning docs in `output/`) |
