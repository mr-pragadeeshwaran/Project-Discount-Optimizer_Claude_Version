# The Business View

*What this product is, with almost no technical vocabulary.*

## What is the product?

A pricing-intelligence engine for CPG brands on quick-commerce platforms.
It answers four business questions, every week, with proof:

1. **Where is my discount money wasted?** (spend that buys no volume)
2. **Where does discounting actually work?** (worth protecting or growing)
3. **What exactly should I set this Monday?** (a sheet, not a philosophy)
4. **Were last week's calls right?** (self-scoring against reality)

## What problem does it solve?

Discounts are a brand's largest controllable trade expense, and the hardest
to evaluate: sales move for many simultaneous reasons, and whatever discount
was running takes the credit. Brands therefore either over-discount out of
fear or trust gut calls. This product replaces both with measurement: it
isolates the discount's own effect from everything else moving sales, and
turns that into small, reversible, monitored weekly actions.

## Who uses it?

- **The operator (you)** — runs the monthly rebuild and weekly loop, sends
  deliverables to the brand.
- **The brand's trade/growth team** — reads the Stage Report workbook and
  approves the plan.
- **The key-account manager (KAM)** — receives the Monday sheet, sets the
  discounts on the platform, marks what was applied.

## What does the user do?

Feeds it the platform's routine sales export (nothing confidential), presses
run, hands over a one-page weekly sheet, and brings back two things each
week: the applied sheet and the next export. That's the entire operating
burden.

## What does the system do behind the scenes?

Cleans and organizes the history; separates days that can teach (normal
trading) from days that can't (out-of-stock, festivals, events); measures
each product-city cell's true discount response and price sensitivity two
independent ways; validates everything through eight gates and an independent
causal double-check; sorts every cell into one action bucket; applies a
committee of safety controls; and writes the outputs.

## What information does it use?

Daily, per product and city: units, revenue, selling price, MRP, discount %,
shelf availability, advertising visibility share, category — plus competitor
rows from the same export, used only to measure competitive pressure. It
never needs the brand's costs; every client-facing number is observable.

## What decisions does it make?

Only bucket assignments and weekly discount settings — each governed by the
rules in [03-business-logic](03-business-logic.md). It deliberately does
NOT decide whether a finding is "big enough" (that's a contract question),
and it never invents a number where evidence is missing — it says "test".

## What does it produce?

- **The Monday KAM sheet** — exact discounts to set, with predictions and
  automatic retreat rules attached.
- **The Stage Report workbook** (versioned) — the client-facing evidence:
  where discount works, optimal levels, ROI, elasticity with accuracy,
  the unlock pipeline and the growth calendar.
- **The dashboard** — live status, receipts, run controls on your machine.
- **The weekly scorecard** — predicted vs actual, building the track record.

## What happens when something goes wrong?

The system prefers stopping loudly to being quietly wrong:

- Broken settings or missing data columns stop the run with a plain-English
  message *before* anything is computed.
- A statistical estimate that fails its sanity checks is discarded and the
  cell falls back to a safer, borrowed estimate — labeled as such.
- A price change whose real-world results miss prediction twice reverts
  automatically.
- A validation gate failing shows as a red receipt on the dashboard — the
  system never hides its own failures, including "not enough data yet."
