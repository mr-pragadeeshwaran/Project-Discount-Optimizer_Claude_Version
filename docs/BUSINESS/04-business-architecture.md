# Business Architecture — the system's layers, in business language

```text
YOU (operator)  ·  THE KAM  ·  THE BRAND
        ↓ files in, sheets out
PRODUCT EXPERIENCE — the dashboard + the deliverable files
        ↓
SYSTEM PROCESSING — the measurement factory (runs on your laptop)
        ↓
BUSINESS RULES — the gates and the safety committee
        ↓
INFORMATION — organized files on disk (no external servers)
        ↓
RESULT — Monday sheet · Stage Report · scorecard
```

## Layer by layer

### 1. Product experience
**Purpose:** let a non-engineer run, inspect and trust the system.
**Inputs:** your clicks; uploaded settings.  **Outputs:** progress, receipts,
tables, downloads.
**Risks:** it only *shows* state — if it's down, nothing is lost; restart it.
**Business importance:** this is where you check the receipts before quoting
anything to a client.
*(Technically: a small local web dashboard, `ui/`, serving only your machine.)*

### 2. System processing
**Purpose:** turn a raw export into validated measurements.
**Inputs:** platform exports; settings.  **Outputs:** a timestamped "run"
folder containing every intermediate and final table.
**Risks:** heavy steps take minutes-to-hours on a small laptop; a crash
mid-run just means re-running — nothing corrupts, each run is a fresh folder.
**Business importance:** the factory floor; its quality gates are your
product's credibility.
*(Technically: the 8-stage pipeline + the analysis scripts in `scripts/`.)*

### 3. Business rules
**Purpose:** ensure no model opinion reaches a real price unchecked.
**Inputs:** measurements + your settings (caps, heroes, timelines).
**Outputs:** buckets, gates receipts, the governed weekly plan.
**Risks:** rules can hold value back when evidence is thin — by design; the
unlock pipeline turns that into a schedule instead of a refusal.
**Business importance:** this layer IS the sellable difference — "governed,
reversible, receipt-backed" is the pitch.

### 4. Information
**Purpose:** keep everything the system knows, transparently.
**Inputs/outputs:** plain files in folders — inputs, settings, runs,
deliverables. No external database, no cloud; every number is inspectable in
Excel.
**Risks:** one laptop = one point of failure. Deliverables are versioned and
code+key outputs are backed up to GitHub; raw data currently is not — the
single most important operational gap.
**Business importance:** client data never leaves your machine — a real
selling point for privacy-sensitive brands.

### 5. Result
**Purpose:** the three artifacts the business runs on — the Monday sheet
(action), the Stage Report (evidence), the scorecard (trust).
**Risks:** an artifact is only as current as the run behind it; the docs
convention is that *numbers always come from the latest run's files*, never
from memory or older documents.
