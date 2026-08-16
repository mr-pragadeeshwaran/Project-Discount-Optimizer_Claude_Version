# How the Product Works — the full journey, no jargon

*Follow one monthly cycle from raw file to Monday sheet.*

```text
Platform export lands in the inputs folder
        ↓
System reads it, keeps only the client's brand, checks nothing vital is missing
        ↓
History is organized into "cells" (one product-pack in one city)
        ↓
Days that can't teach are set aside (out-of-stock, festivals, freak spikes)
        ↓
For each cell: measure the discount's OWN effect, everything else held constant
        ↓
A second, independent method re-measures price sensitivity
        ↓
Eight validation gates + an independent causal double-check
        ↓
Every cell gets ONE action bucket (cut / fix stock / hold / test / monitor)
        ↓
Safety committee applies caps, floors, glide limits, two-engine agreement
        ↓
Outputs: Monday KAM sheet · Stage Report workbook · dashboard · scorecard
        ↓
Next week: reality comes back and every prediction is graded
```

## Each step, explained

**1. Reading the export.** The raw file is huge (hundreds of thousands of
rows, all brands). The system reads it in slices so an ordinary laptop can
handle it, keeps only rows belonging to the configured brand, and stops
immediately with a clear message if a required column is absent — bad input
is rejected at the door, not discovered as a wrong number later.

**2. Cells.** All analysis happens at the grain a KAM actually acts on: one
product-pack in one city ("Turbo Chocolate 250ml in Kolkata"). Epigamia
currently has 699 modelable cells.

**3. Days that can't teach.** A day the product was effectively off-shelf
says nothing about pricing. A festival day follows different rules. A freak
spike (data glitch or unlogged promo) would poison the measurement. These
days are set aside — and listed in an audit file, never silently deleted.

**4. Isolating the discount effect.** The heart of the system. For each
category it asks: across weeks where the discount differed but availability,
ad visibility, competitor prices and season were the same, how did sales
differ? What remains is the discount's own effect — not the credit it
usually steals from other factors.

**5. The second opinion.** A separate engine, built a different way,
independently estimates each cell's price sensitivity (including how the
brand's own products steal sales from each other when one gets cheaper).
Two methods that never share notes and still agree — that is the trust
argument the client workbook shows.

**6. Gates and the double-check.** Eight pass/fail gates (fit quality, money
reconciliation, out-of-sample accuracy, and more) plus "Double ML" — a
modern causal-inference technique whose only job is to try to overturn the
waste finding. A cut must survive all of it.

**7. Buckets.** Every cell gets exactly one verdict: cut (proven waste),
fix-stock-first (availability is the real problem), competitive-hold,
test (evidence insufficient — by design it says so), or monitor.

**8. The safety committee.** Between model and market stand: the budget cap,
the 3-points-per-week glide limit, the never-below-traded-floor rule, the
hero-SKU shield, the requirement that BOTH engines want the cut, and the
kill-switch (two missed predictions → automatic revert).

**9. Outputs.** One operational sheet for the KAM, one evidence workbook for
the brand (versioned — old copies are never overwritten), the live
dashboard, and the machine-readable logs the scorer uses.

**10. The loop.** Next week's export grades every prediction. Hits build the
track record; misses trigger the kill-switch. This step is what turns the
product from "a model" into "a service with receipts."
