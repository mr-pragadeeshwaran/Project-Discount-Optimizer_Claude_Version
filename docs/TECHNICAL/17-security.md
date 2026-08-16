# 17 — Security & Threat Model

*Audience: engineers. What the attack surface actually is for a local,
single-user tool — and which classic web-security concepts deliberately do
not apply here.*

## 1. Scope: what kind of system this is

Stat IQ Lab runs entirely on one machine, for one person. There is **no
database, no cloud service, no deployment, and no user accounts** — the
system is plain files on disk plus a stdlib HTTP dashboard bound to
loopback (`ui/app.py`). That erases most of the classic web threat model
(SQL injection, session hijacking, cloud IAM, secrets rotation) — those
concepts have no equivalent here and none is invented. What remains is a
small, concrete surface, described below.

The consequence to protect against is also different from a web app's:
the crown jewels are **the client's proprietary sales data**
(`input_data/`) and **the integrity of the numbers the engine reports**.
Both are covered in §5 and §6.

## 2. The one network surface: the dashboard

`ui/app.py` is the only process that opens a socket. Its security model
is stated at the top of the file and enforced in three places:

**Loopback binding.** The server binds `("127.0.0.1", PORT)` in `main()`
(port from env `UI_PORT`, default 8765). It is unreachable from any other
machine unless someone deliberately port-forwards or proxies it — see §4
for why that must never be done casually.

**Fixed step allowlist — never arbitrary commands.** The run endpoint
`POST /api/run/<step_id>` accepts **only** ids present in the `STEPS`
dict (`ui/app.py`, ~lines 32–91: `pipeline`, `champion`, `dml`, `gates`,
… `params`) plus the composite `monthly_all`. Anything else returns
"Unknown step". Each entry carries its exact command as an **argv list**;
execution is `subprocess.Popen([sys.executable, "-X", "utf8", *cmd],
cwd=ROOT)` with no `shell=True`, so there is no shell to inject into. The
only dynamic token, `@latest_fact`, is resolved server-side by
`_resolve()` to the newest run's `fact_table.csv` — the client never
supplies a path. `#reset_state` is an internal action (delete three known
tracker files), not a shell command.

**One job at a time.** `start_job()` takes `JOB.lock` and returns HTTP
409 if a job is already running. This is a correctness guard (two
pipeline runs would race on `output/`) that doubles as a
resource-exhaustion guard.

All GET endpoints are read-only views over files the engine already
wrote; unknown tables/reports 404.

## 3. The one write endpoint: settings upload

`POST /api/settings/upload` is the single way the browser can change
anything on disk, and it is validated-before-install with a fixed
destination (`ui/app.py::_settings_upload` + `settings_loader.py`):

1. **Size cap** — Content-Length must be >0 and ≤5 MB.
2. **Name is never a path** — `os.path.basename()` is applied to the
   uploaded filename; it is used **solely to pick the format** (extension
   must be `.csv` or `.xlsx`), never as a destination.
3. **Validate before write** — `settings_loader.validate_bytes()` writes
   the bytes to a throwaway temp dir and runs the full fail-loud parser
   (`_parse_settings` / `_parse_calendar` / `_parse_events`) there. A file
   that does not parse as a settings file is rejected with the parser's
   error message and never touches `config/`.
4. **Fixed destination** — `settings_loader.install_bytes()` only ever
   writes to `config/settings.csv` or `config/settings.xlsx`, and deletes
   the other format so exactly one source of truth exists.
5. **No mid-run swaps** — the upload is refused (409) while a job runs.

Note what validation buys beyond security: `settings_loader.py` and
`stage1_ingestion/validate.py` are fail-loud by design, so a malformed
file is a loud error at install/run time, never a silent wrong number in
a client deliverable. Integrity of reported numbers is part of this
system's threat model.

## 4. No authentication — by design, with a stated expiry

There is no login, no token, no session. This is a **deliberate design
decision**, not an omission, and it rests on one assumption:

> One operator, one machine, loopback only.

Under that assumption auth would add credential management and session
bugs while protecting against nobody: any local process that could call
`localhost:8765` could equally run `python pipeline.py` directly.

**The assumption breaks — and the design with it — the moment any of
these happens:**

- the bind address is changed from `127.0.0.1` to `0.0.0.0`;
- the port is exposed via port-forwarding, a tunnel, or a reverse proxy;
- the machine is shared between users;
- the product is hosted for a client ("can we just put the dashboard on
  a server?").

Any of those is a **rebuild trigger, not a config change**. A hosted or
multi-user Stat IQ Lab needs authentication, TLS, CSRF protection, and
per-client data isolation designed in — none of which can be bolted onto
a stdlib `ThreadingHTTPServer` responsibly.

**Known residual risk on loopback:** the server does not check the
`Origin` header, so a malicious web page open in the operator's browser
could fire cross-origin POSTs at `localhost:8765` (CSRF). The blast
radius is bounded by §2 and §3 — such a page could trigger an allowlisted
step re-run or attempt a settings install that still has to pass full
validation; it cannot execute arbitrary commands and cannot read
responses cross-origin. Accepted for a single-user tool; an `Origin`
check in `Handler.do_POST` is the fix if this ever matters.

## 5. Client-data privacy: data never leaves the machine

- **No outbound network calls exist anywhere in the codebase.** The only
  networking import in any `.py` file is `http.server` in `ui/app.py`,
  which serves; nothing fetches (no `requests`, no `urllib.request`).
  This is a checkable property — grep for outbound HTTP before merging
  anything that would break it.
- **Git hygiene** (`.gitignore`): `input_data/` (proprietary client
  exports — the comment says "never commit"), `data/`, `archive/`, and
  `output/*` are all ignored. The two deliberate exceptions:
  `output/README.md` and `output/DISCOUNT_PLAN/**` (weekly-tracker config
  and reports that were consciously committed).
- The pinned dependency set (`requirements.txt`) is installed once into
  `.venv`; routine operation needs no network at all.

So "client data never leaves the machine" is not a policy statement — it
is a property of the code as written, plus git hygiene.

## 6. Accepted risks

**No backup of raw data (the big one).** `input_data/` is a single copy:
gitignored, on one 5.9 GB Windows machine, not synced anywhere. Losing
the disk means re-requesting every export from the client. Derived
artifacts are regenerable (`output/runs/` from the pipeline, deliverables
from the run store) — the raw inputs are not. Mitigation is operational,
not code: periodic manual copy of `input_data/` to offline/external
storage, never into git.

**Supply chain.** Dependencies are exactly pinned in `requirements.txt`
(primarily for numerical stability — see
[18-performance.md](18-performance.md) §6 — but pinning also freezes the
supply-chain exposure to a known set).

**Local attacker.** Anyone with an account on the machine can read
`input_data/` directly; the dashboard adds nothing to their capabilities.
Full-disk encryption is the OS-level answer if the machine leaves a
trusted location.

## 7. Explicitly out of scope

No SQL/NoSQL injection surface (no database — see the architecture docs),
no stored-XSS-to-other-users (single user), no secrets management (there
are no secrets: no API keys, no credentials, no tokens anywhere in the
repo), no CI/CD pipeline hardening (there is no CI/CD; runs happen from
the Run Center or the terminal).

---

*Siblings: [18-performance.md](18-performance.md) (the memory budget that
shaped stage 4), [../BUSINESS/04-business-architecture.md](../BUSINESS/04-business-architecture.md)
(the same layers in business language), [../README.md](../README.md)
(docs home).*
