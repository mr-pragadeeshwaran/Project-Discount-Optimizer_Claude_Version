# Stat IQ Lab — Documentation Home

*The single entry point to understanding this product. Last full refresh:
2026-08-16, against the live Epigamia engagement (run `20260810_143823`).*

## Read in this order

**If you have 30 minutes** → [BUSINESS-QUICKSTART.md](BUSINESS-QUICKSTART.md).
It's the whole product in one sitting, written for a business reader.

**If you own the product** → the `BUSINESS/` folder, top to bottom:

| Doc | Answers |
|---|---|
| [00-business-view](BUSINESS/00-business-view.md) | What is this? Who uses it? What does it produce? |
| [01-how-the-product-works](BUSINESS/01-how-the-product-works.md) | The full journey, screen to result, no jargon |
| [02-user-journeys](BUSINESS/02-user-journeys.md) | "What happens when I click this?" for every button that matters |
| [03-business-logic](BUSINESS/03-business-logic.md) | Every important rule the system enforces, as a catalog + decision trees |
| [04-business-architecture](BUSINESS/04-business-architecture.md) | The system's layers in business language |
| [05-glossary](BUSINESS/05-glossary.md) | Every technical term used anywhere, translated once |

**If you are an engineer** → `TECHNICAL/` (how it's built) and
`ENGINEERING/` (how to work on it). `diagrams/` holds both business-level
and engineering-level pictures.

## The deep library (pre-existing)

The older, deeper teaching library now lives inside this tree:

- [`reference/ARCHITECTURE_HANDBOOK.md`](reference/ARCHITECTURE_HANDBOOK.md) —
  book-length architecture course for a business owner. **Still-true concepts;
  some numbers predate Epigamia.**
- [`reference/EXECUTION_PLAYBOOK.md`](reference/EXECUTION_PLAYBOOK.md) — every
  command, copy-pasteable.
- `reference/OPERATIONS_MANUAL.md` / `COMPLETE_SYSTEM_GUIDE.md` — end-to-end
  operations and statistics. **Pinned to the earlier 24 Mantra engagement** —
  read for mechanism, not for current numbers.
- `legacy/` — frozen project history; `assets/` — teaching diagrams;
  `pdf/` — the generated system-guide PDF.
- `output/` learning docs (MASTERCLASS, FROM_ZERO, THE_8DIAL_DANCE, …) —
  the statistics taught from zero, on real cells.

**Rule of thumb: numbers come from the live dashboard and the latest
STATIQ_STAGE_REPORT workbook; concepts can come from any doc.**

## How these docs stay honest

Documentation rots when it duplicates what code already says. These docs
therefore describe *purpose, rules and flows* (which change rarely) and point
to *live artifacts* for numbers (which change weekly). When behavior changes,
the change-guide (`ENGINEERING/32-change-guide.md`) lists which doc to touch.
