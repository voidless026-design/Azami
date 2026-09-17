# Azami — Master Development Prompt

> **What this document is.** This is a complete, hand-to-a-developer (or hand-to-a-coding-agent)
> specification for building **Azami**, a cross-platform desktop application for **authorized**
> reconnaissance and OSINT during scoped security engagements. It covers the project end to end:
> guiding principles, the authorization model that gates everything, the technology stack for each
> layer, the repository layout, the backend engine, the tool-integration layer, the data model,
> the frontend, packaging into an executable, testing, deployment, and a phased roadmap that starts
> from an MVP. Read it top to bottom before writing code. Where it says **MUST**, treat it as a
> hard requirement; where it says **SHOULD**, treat it as the strong default you deviate from only
> with a recorded reason.

---

## 0. The one rule that shapes the whole design

Azami is a tool for **authorized** security work — penetration tests, red-team engagements,
bug-bounty programs with a defined scope, and organizations assessing their own assets. It is
**not** a tool for profiling, surveilling, or attacking an arbitrary person or system that you
have not been authorized to test. That distinction is not a disclaimer bolted on at the end; it is
the **central architectural constraint**, and it drives more of the design than anything else:

- **Nothing active runs without an authorization scope loaded.** The application boots into a
  locked state. No scan, lookup, or tool invocation targeting a host, domain, IP, or account can
  execute until a signed **Rules-of-Engagement (RoE) scope** has been loaded, validated, and is
  currently within its authorized time window.
- **Every target is checked against the scope, every time.** Before any module touches a target,
  a central **Scope Engine** decides in-scope / out-of-scope. Out-of-scope targets are refused and
  the refusal is logged. There is no bypass flag in the product.
- **Everything is audited.** Every action — passive lookup, active scan, tool run, its parameters,
  the operator, the timestamp, and a hash of the result — is written to an append-only engagement
  log intended to be part of the deliverable an assessor hands their client.
- **Active/intrusive modules are gated twice.** Passive OSINT is allowed for any in-scope asset.
  Intrusive modules (credential testing, exploitation, brute-forcing) additionally require an
  explicit `active_testing: true` grant in the scope for that asset class *and* a per-run operator
  confirmation.

If a design decision ever conflicts with the above, the authorization constraint wins. Build the
Scope Engine and the audit log **first** (Phase 0), before any recon feature, so that every
feature added afterward is gated by construction rather than as an afterthought.

---

## 1. Product summary

Azami is a **sleek, modern, cross-platform desktop console** that gives an authorized operator a
single pane of glass over an engagement:

1. Load and validate an engagement's authorization scope (targets, allowed actions, time window).
2. Run **passive OSINT** against in-scope organizations and assets — DNS, WHOIS, certificate
   transparency, public directory / registry data, breach-exposure checks, and public social /
   handle enumeration — to build a normalized, confidence-scored profile of the *attack surface*.
3. Run **active reconnaissance and testing tools** — Nmap, Gobuster, Hydra, John the Ripper,
   Metasploit modules — against in-scope assets only, through a uniform job API, with live output
   streamed to the UI.
4. Chain these into **playbooks** (e.g., enumerate subdomains → resolve to IPs → port-scan in-scope
   IPs → directory-brute in-scope web services), each step re-checked against scope.
5. Persist, normalize, de-duplicate, and **visualize** the findings (entity graph, map for
   geolocated assets, source-distribution charts, engagement timeline).
6. Export a clean engagement report plus the full audit trail.

The tools themselves run in **containerized runners** (local Docker by default, remote/cloud
runners optionally), so the desktop app stays thin and the tool versions stay current and
reproducible. The GUI never needs to know how Nmap works — only how to submit a job and render a
result.

---

## 2. Technology stack (with rationale)

Pick boring, well-supported technology. The recommended stack:

| Layer | Choice | Why |
|---|---|---|
| Desktop shell | **Tauri (Rust core) + React + TypeScript** | Small binaries, low memory, real cross-platform executables, a hardened webview, and a Rust side that's a natural home for the local secrets vault. (Electron + React is an acceptable fallback if the team is JS-only.) |
| UI framework | **React 18 + TypeScript + Vite** | Mature ecosystem, fast HMR, strong typing across the IPC boundary. |
| UI styling | **Tailwind CSS + shadcn/ui + Radix** | Fast path to a clean dark-mode, high-contrast, accessible interface. |
| State management | **Zustand** (client state) + **TanStack Query** (server state) | Simple, predictable; Query handles polling/streaming job state well. |
| Charts / viz | **Recharts** (charts) + **Cytoscape.js** (entity graph) + **MapLibre GL** (maps) | Covers timelines, distributions, relationship graphs, and geolocated assets without proprietary keys. |
| API gateway | **Python 3.12 + FastAPI + Uvicorn** | Async, typed (Pydantic v2), automatic OpenAPI, ideal glue for the recon/tool ecosystem which is Python-heavy. |
| Real-time | **WebSockets** (FastAPI) for live job output + **Server-Sent Events** fallback | Stream tool stdout/stderr and job-state transitions to the UI. |
| Task queue / workers | **Celery + Redis** (broker + result backend) | Long-running scans must not block the API; workers scale independently. |
| Tool execution | **Docker** runners orchestrated by the workers (each tool in its own image) | Isolation, reproducible tool versions, easy to move to remote/cloud runners later. |
| Relational store | **PostgreSQL 16** | Canonical entities, findings, jobs, audit log, engagement metadata. |
| Graph/relationships | Postgres with recursive CTEs for MVP; **Neo4j** optional later | Avoid premature complexity; the entity graph is small at engagement scale. |
| Cache / rate-limit state | **Redis** | Shared token buckets and backoff counters across workers. |
| Secrets at rest | **OS keychain via Tauri** for the app; **SOPS-encrypted** env / Vault for the backend | API keys and RoE signing material never sit in plaintext. |
| Auth (multi-operator) | **OAuth2 password flow + JWT** with role-based access (RBAC) | Operators, leads, and read-only reviewers have different rights. |
| Packaging | **Tauri bundler** (`.msi`, `.dmg`, `.AppImage`/`.deb`) for the desktop; **docker-compose** for the backend stack | One installer per OS; the backend is a compose bundle the app can launch or connect to. |
| Testing | **pytest** (backend), **Vitest + React Testing Library** (frontend), **Playwright** (e2e) | Full pyramid. |
| CI/CD | **GitHub Actions** | Lint, typecheck, test, build installers, scan dependencies. |

> **Deployment topology.** The recommended default is **local-first**: the desktop app ships with
> a bundled `docker-compose` stack (API + workers + Postgres + Redis + tool runners) that runs on
> the operator's machine or a dedicated engagement box. A "connect to remote backend" mode lets a
> team point the desktop app at a shared, hardened backend instead. Design the API boundary so both
> work without code changes.

---

## 3. Repository structure

```
Azami/
├── README.md                     # Project overview, legal stance, quick start
├── LICENSE                       # See §17 (license + acceptable-use)
├── SECURITY.md                   # Vulnerability disclosure for Azami itself
├── docs/
│   ├── DEVELOPMENT_PROMPT.md     # This document
│   ├── AUTHORIZATION_MODEL.md    # The scope / RoE model in depth
│   ├── ARCHITECTURE.md           # Diagrams + component contracts
│   ├── DATA_MODEL.md             # Canonical schema, normalization, confidence
│   ├── API.md                    # REST + WS contract (generated from OpenAPI)
│   └── OPERATOR_GUIDE.md         # How to run an engagement with Azami
├── examples/
│   └── scope.example.yaml        # A complete, annotated RoE scope file
├── backend/
│   ├── pyproject.toml
│   ├── azami/
│   │   ├── main.py               # FastAPI app factory
│   │   ├── config.py             # Pydantic settings
│   │   ├── auth/                 # Operator auth, RBAC, JWT
│   │   ├── scope/                # Scope Engine: parse, validate, gate  ← build first
│   │   ├── audit/                # Append-only audit log            ← build first
│   │   ├── osint/                # Passive collectors (one module per source)
│   │   ├── tools/                # Tool wrappers (nmap, gobuster, hydra, john, metasploit)
│   │   ├── runners/              # Docker/remote runner abstraction + job state machine
│   │   ├── orchestration/        # Playbooks, workflow/DAG engine
│   │   ├── entities/             # Normalization, entity resolution, confidence scoring
│   │   ├── ratelimit/            # Token buckets + backoff
│   │   ├── wordlists/            # Dictionary/list manager + updater
│   │   ├── persistence/          # SQLAlchemy models, migrations (Alembic)
│   │   ├── api/                  # Routers (REST) + ws/ (WebSocket handlers)
│   │   └── workers/              # Celery tasks
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── app/                  # Routing, providers, theme
│   │   ├── features/
│   │   │   ├── scope/            # Load/validate/inspect scope (the gate UI)
│   │   │   ├── dashboard/        # Engagement overview
│   │   │   ├── osint/            # Passive results, entity profile
│   │   │   ├── tools/            # One panel per tool + live output
│   │   │   ├── playbooks/        # Build/run chained workflows
│   │   │   ├── graph/            # Cytoscape entity graph
│   │   │   ├── map/              # Geolocated assets
│   │   │   └── report/           # Export + audit trail viewer
│   │   ├── components/           # shadcn/ui-based shared components
│   │   ├── lib/                  # API client, WS client, types (shared with backend via codegen)
│   │   └── store/                # Zustand stores
│   └── src-tauri/                # Rust: window, secrets vault, backend launcher
├── runners/                      # Dockerfiles for each tool image
│   ├── nmap/Dockerfile
│   ├── gobuster/Dockerfile
│   ├── hydra/Dockerfile
│   ├── john/Dockerfile
│   ├── metasploit/Dockerfile
│   └── tcpdump/Dockerfile
├── data_sources/                 # Source configs + provenance manifests + wordlist catalog
│   ├── collectors.yaml           # Which OSINT sources are enabled, their API config refs
│   ├── wordlists.catalog.yaml    # Managed wordlists: name, source URL, license, checksum, ver
│   └── provenance/               # Per-source data-license + attribution records
├── scripts/                      # Dev bootstrap, codegen, seed, wordlist sync
├── deploy/
│   └── docker-compose.yml        # API + workers + postgres + redis + runners
└── .github/workflows/            # CI: lint, test, build, dependency scan
```

---

## 4. Phase 0 — Authorization & audit (build this before any recon feature)

This is the foundation. Detailed model lives in `docs/AUTHORIZATION_MODEL.md`; the essentials:

### 4.1 The scope file (Rules of Engagement)

An engagement is defined by a signed **scope file** (YAML or JSON). See
`examples/scope.example.yaml` for the full annotated form. It declares:

- **Engagement metadata**: id, client name, assessing org, authorizing contact, and a reference to
  the signed authorization document (contract/SOW id).
- **Time window**: `not_before` / `not_after` timestamps. Outside the window, active modules refuse.
- **In-scope assets**: explicit lists of `domains`, `ip_ranges` (CIDR), `hosts`, `urls`, and
  optionally `asns`. Wildcards are allowed only where the authorization explicitly grants them.
- **Out-of-scope / exclusions**: assets that must never be touched even if they fall inside a range
  (e.g., a shared-hosting neighbor, a third-party dependency). Exclusions always win over inclusions.
- **Allowed actions per asset class**: e.g., `passive: true`, `active_scan: true`,
  `active_testing: true`, `exploitation: false`. Intrusive tools consult these flags.
- **Constraints**: max scan rate, blackout windows, allowed source IPs, contact for emergency stop.
- **Integrity**: a detached signature (e.g., minisign / GPG) over the file, plus the public key /
  fingerprint of the authorizer. Azami verifies the signature before honoring the scope.

### 4.2 The Scope Engine (`backend/azami/scope/`)

- `load(path)` → parse + schema-validate (Pydantic) + verify signature + check time window.
- `check(target, action)` → returns `Allow | Deny(reason)`. This function is called by **every**
  collector, tool wrapper, and playbook step, with no exceptions. Resolve the target to its
  canonical form (domain, IP, URL host) first; check exclusions before inclusions; check the
  action against the asset class's allowed-actions; check the time window and any blackout.
- A **global kill-switch**: a single call that immediately halts all running jobs, revokes the
  active scope, and returns the app to the locked state. Surface it prominently in the UI.

### 4.3 The audit log (`backend/azami/audit/`)

- Append-only table; each record: `{id, ts, engagement_id, operator_id, action, target,
  tool, parameters(redacted secrets), scope_decision, result_hash, prev_hash}`.
- `prev_hash` chains records (hash of the previous record) so the log is **tamper-evident**; a
  verifier can walk the chain and detect edits/deletions.
- Nothing writes to the audit log except through one `record()` function; the DB user for the app
  has `INSERT` but not `UPDATE`/`DELETE` on the audit table.
- The audit trail is a first-class export in the report module.

**Definition of done for Phase 0:** the app boots locked; loading a valid signed scope unlocks it;
`scope.check()` gates a trivial passive lookup and refuses an out-of-scope target; every attempt
(allowed or denied) appears in a tamper-evident audit log; the kill-switch halts and re-locks.

---

## 5. Backend — passive OSINT layer (`backend/azami/osint/`)

Modular collectors, one file per source, all implementing a common interface:

```python
class Collector(Protocol):
    name: str
    produces: list[EntityType]           # what canonical entities it can emit
    requires_action: Action = Action.PASSIVE
    async def collect(self, target: Target, ctx: RunContext) -> list[RawRecord]: ...
```

Every collector, before doing anything, calls `ctx.scope.check(target, self.requires_action)` and
`ctx.ratelimit.acquire(self.name)`. Collectors emit **RawRecord**s that the entities layer (§8)
normalizes into canonical entities. Build these collectors (all passive, all keyed to authorized
assets or the client organization):

- **DNS / subdomain enumeration**: A/AAAA/MX/NS/TXT/CNAME, passive subdomain discovery via
  certificate transparency logs (crt.sh-style) and passive DNS APIs.
- **WHOIS / RDAP**: registrant org, registrar, name servers, creation/expiry, abuse contacts.
- **Certificate transparency**: certs for in-scope domains → additional hostnames / SANs.
- **ASN / netblock mapping**: map in-scope domains/IPs to owning org and netblocks (to confirm
  ownership, and to *avoid* touching netblocks the client doesn't own).
- **Breach / credential-exposure check**: query breach-index APIs (e.g., HaveIBeenPwned-style) for
  in-scope corporate email domains to report exposure — **report only**, never re-use credentials.
- **Public business/registry data**: business registration, professional-license, and property/deed
  lookups **for the client organization / its stated assets** via official/public-record APIs — used
  to confirm ownership and corporate footprint, not to profile private individuals.
- **Public web / social footprint**: public company handles, public employee-directory listings
  relevant to the attack surface (e.g., an exposed staff portal), and openly published content — via
  official APIs where they exist; respect each platform's Terms of Service and `robots.txt`.
- **Geolocation enrichment**: map IPs/assets to city/region for the map view (IP-geo APIs).

> **Scraping discipline.** Prefer official APIs. Where scraping is unavoidable, honor `robots.txt`,
> set a truthful `User-Agent` that identifies the engagement, respect rate limits (§9), and never
> attempt to defeat access controls, CAPTCHAs, or paywalls — that is out of scope for a passive
> collector by definition.

---

## 6. Backend — tool integration layer (`backend/azami/tools/` + `backend/azami/runners/`)

The "online tools" from the original concept — **Nmap, Gobuster, Hydra, John the Ripper,
Metasploit, tcpdump** — are integrated as **gated, containerized jobs**, not run inline in the app.
They run in pinned tool-runner containers (local Docker by default, remote/cloud runners
optionally), which is how the original brief's "online / cloud tools" idea is realized: reproducible
remote runners kept current, rather than tools baked into the desktop binary.

### 6.1 Runner abstraction (`runners/`)

A `Runner` submits a tool job to an execution backend and streams results back:

```python
class Runner(Protocol):
    async def submit(self, job: ToolJob) -> JobHandle: ...
    async def stream(self, handle: JobHandle) -> AsyncIterator[JobEvent]:  # stdout/stderr/state
    async def status(self, handle: JobHandle) -> JobState: ...
    async def cancel(self, handle: JobHandle) -> None: ...
```

- **DockerRunner** (default): each tool has a pinned image under `runners/<tool>/`. The runner
  launches a container with the target/args, no host networking beyond what's needed, a CPU/mem
  cap, a hard timeout, and read-only mounts for wordlists. Output is streamed line-by-line.
- **RemoteRunner** (optional): submits to a remote runner service over an authenticated API for
  teams that centralize tooling ("online" tool hosting). Same interface, so the app is agnostic.

### 6.2 Job state machine

`QUEUED → RUNNING → (SUCCEEDED | FAILED | CANCELLED | TIMED_OUT)`. Persist state transitions; emit
each as a `JobEvent` over the WebSocket so the UI shows a real progress state, not a spinner that
lies. Store the full stdout/stderr, exit code, parsed structured result, and a result hash.

### 6.3 Tool wrappers — and how each is gated

Each wrapper builds a validated command line (never string-concatenate user input; use argument
arrays and allow-listed flags), maps the target through `scope.check`, and parses output into
canonical findings.

| Tool | Purpose in an authorized engagement | Required scope grant | Extra gate |
|---|---|---|---|
| **Nmap** | Port/service/version discovery on in-scope IPs/hosts | `active_scan` | Rate cap from scope; refuse non-scope IPs even if user types them |
| **Gobuster** | Content/subdomain discovery on in-scope web services | `active_scan` | Wordlist from managed store; per-host concurrency cap |
| **Hydra** | Credential-strength testing against in-scope, authorized services | `active_testing` | Per-run operator confirmation; lockout-aware low rate; **only** targets the scope marks testable |
| **John the Ripper** | Offline cracking of hashes **obtained lawfully within the engagement** (e.g., a captured hash the client authorized testing on) | `active_testing` | Hashes must be attached to the engagement's evidence store; no external hash sources |
| **Metasploit** | Verification of specific findings via authorized modules on in-scope hosts | `exploitation` | Per-run confirmation; module allow-list; default to check/scanner modules, not payload delivery, unless exploitation is explicitly granted |
| **tcpdump** | Capturing/analyzing traffic **on an interface or segment the engagement is authorized to monitor** (e.g., the tester's own test VLAN or an authorized SPAN port) | `active_testing` | Capture only on operator-designated, authorized interfaces recorded in the scope — never a capture aimed at intercepting a third party's traffic; BPF filter allow-listed; capped duration/size |

For each wrapper implement: `plan(params) -> ToolJob` (validate + scope-check + build args),
`parse(raw) -> list[Finding]`, and structured error mapping (timeout, tool-not-found, permission,
target-unreachable) surfaced to the UI as actionable diagnostics.

> Wrappers **must** refuse to run when the scope grant is missing, when the target is out of scope,
> or when outside the time window — and log the refusal. There is no "force" parameter.

---

## 7. Backend — orchestration & playbooks (`backend/azami/orchestration/`)

A workflow engine that chains collectors and tools into **playbooks** — a DAG of steps where each
step's output feeds the next, and **every step re-checks scope on the concrete targets it derived**
(a subdomain discovered passively is not automatically in scope for active scanning — it must match
the scope's inclusions and its asset class must allow the action).

- Model a playbook as a serializable DAG (`steps`, `depends_on`, `inputs`, `on_error`).
- Ship starter playbooks: *Passive footprint*, *Attack-surface map* (passive → resolve → in-scope
  port scan), *Web content discovery* (in-scope web service → gobuster), *Credential-strength check*
  (explicitly authorized service → hydra with confirmation).
- Execution runs on Celery workers; each step emits progress events; a failed/denied step records
  why and either stops or continues per `on_error`. The whole run is cancellable via the kill-switch.

---

## 8. Backend — data model, normalization, entity resolution, confidence

Full schema in `docs/DATA_MODEL.md`. Core ideas:

### 8.1 Canonical entities

A small set of typed entities with canonical fields, so that a "Mobile Phone Number" from one
source and a "Cell Number" from another map to the **same** normalized field:

- `Organization`, `Person` (only in the context of authorized attack-surface, e.g., a listed
  admin contact), `Domain`, `Host`, `IPAddress`, `NetBlock`, `Service` (port+proto+product),
  `EmailAddress`, `PhoneNumber`, `Credential` (hash/exposure reference, never plaintext at rest),
  `SocialProfile`, `Location`, `Certificate`, `Finding`.
- Each entity carries: `id`, canonical fields, `sources` (which collectors/tools asserted it),
  `first_seen`, `last_seen`, `confidence`, and `engagement_id`.

### 8.2 Normalization

- Phone numbers → E.164 (libphonenumber). Emails → lowercased, validated, MX-checked. Domains →
  IDNA/punycode-normalized, registrable-domain extracted (public-suffix list). IPs → canonical
  form, v4/v6 aware. Locations → geocoded to a canonical `{lat, lon, city, region, country}`.
- Maintain a `field_mapping` registry so each source's raw field names map to canonical fields;
  adding a source means adding mappings, not touching consumers.

### 8.3 Entity resolution (de-duplication)

- Deterministic keys first (same email, same IP, same normalized phone → same entity).
- Probabilistic merge for fuzzy cases (name + org + location similarity) behind a threshold, with
  **merge provenance** kept so a merge can be explained and undone.

### 8.4 Confidence scoring (answers "if the input is ambiguous, how do we rank matches?")

- Each asserted fact gets a source-reliability weight (official API > verified record > scraped
  page > single social post) and a corroboration boost (independent sources agreeing raise
  confidence multiplicatively toward 1.0).
- Candidate identities for an ambiguous input are ranked by aggregate confidence and shown as
  **ranked candidates with their evidence**, never silently collapsed into one "answer." The
  operator confirms which candidate is the real in-scope asset before active steps proceed.

---

## 9. Backend — rate limiting, backoff, and being a good citizen

- Central **token-bucket** rate limiter in Redis, keyed per source/host, so all workers share one
  budget and public services aren't hammered.
- Exponential backoff with jitter on `429`/`5xx`; respect `Retry-After`.
- Per-engagement global concurrency cap and per-target caps from the scope's `constraints`.
- Circuit-breaker per source: after repeated failures, open the breaker and surface a clear status
  rather than retrying blindly.
- Active tools inherit scan-rate caps from the scope (e.g., Nmap `--max-rate`, Hydra low `-t`).

---

## 10. Backend — wordlist / dictionary management (`backend/azami/wordlists/`)

- A managed store of wordlists (directory/vhost lists for Gobuster, credential-strength lists for
  Hydra/John). Metadata per list: name, source URL, license, checksum, size, category, version.
- An **updater** that fetches curated open-source lists (e.g., SecLists) from their canonical
  sources, verifies checksums, records provenance, and versions them — with an explicit "update"
  action, not silent background pulls.
- Lists are mounted **read-only** into tool runners. The store is the single source of truth so runs
  are reproducible (a report can cite exactly which list version was used).
- Never bundle lists whose license forbids redistribution; fetch those at runtime with attribution.

---

## 11. Frontend — the experience layer (`frontend/`)

### 11.1 Design language

- **Dark-first, high-contrast, professional.** A restrained accent color, generous spacing,
  monospace for tool output, and a clear visual language for state (queued / running / done /
  failed / **denied-by-scope**). Meet WCAG AA contrast. Support light mode via CSS variables.
- Never render out-of-scope state as if it were a normal error — it's a deliberate, prominent,
  explained refusal.

### 11.2 The scope gate (first screen)

- On launch the app is **locked**. The first screen is "Load engagement scope": drop in the signed
  scope file; Azami verifies the signature, shows the parsed scope (targets, allowed actions, time
  window, exclusions, authorizer) for the operator to confirm, and only then unlocks the console.
- A persistent header shows the active engagement, the time-window countdown, and the **kill-switch**.

### 11.3 Dashboard

- Engagement overview: in-scope asset counts, entities discovered, open findings by severity, jobs
  running, recent audit events. One primary input to add/inspect an in-scope target.

### 11.4 Tool panels (`features/tools/`)

- One tab/module per tool (Nmap, Gobuster, Hydra, John, Metasploit). Each shows a **parameter form**
  (with the target constrained to in-scope assets via a picker, not free text), a **Run** button
  that submits the job, a **live output stream** (the actual stdout over WebSocket, auto-scrolling,
  searchable), a real **progress/state** indicator driven by the job state machine, and a parsed
  **results** view. Intrusive tools show the required scope grant and a confirmation dialog before
  running.

### 11.5 OSINT / entity views

- Passive results feed an **entity profile**: canonical fields with per-field source + confidence,
  ranked candidates for ambiguous inputs, and drill-down to raw records.

### 11.6 Visualizations

- **Entity graph** (Cytoscape): domains ↔ hosts ↔ IPs ↔ services ↔ findings, with confidence-
  weighted edges.
- **Map** (MapLibre): geolocated in-scope assets.
- **Charts** (Recharts): source-distribution, findings-by-severity, an **engagement timeline** of
  actions (also the human-readable face of the audit log).

### 11.7 Report & audit viewer

- Compose an engagement report (scope summary, methodology, findings with evidence, remediation)
  and export (PDF/Markdown/JSON). Include the **full tamper-evident audit trail** as an appendix.

### 11.8 Real-time & errors

- One WebSocket client multiplexes job events, playbook progress, and audit events into the
  relevant panels. All failures — API timeouts, failed scrapes, tool errors, scope denials — are
  logged locally and surfaced to the UI as **actionable diagnostics** (what failed, why, next step),
  never a silent spinner.

---

## 12. Security of Azami itself

Azami handles sensitive engagement data, so harden the app, not just the targets:

- **Operator auth + RBAC**: roles `lead` (load scope, run everything), `operator` (run within
  scope), `reviewer` (read-only). JWT with short expiry + refresh.
- **Secrets**: API keys and scope-signing keys in the OS keychain (desktop) / Vault or SOPS
  (backend). Never in the repo, never in logs (redact in audit records).
- **Data at rest**: encrypt the engagement database volume; encrypt exported reports by default.
- **Transport**: TLS between app and backend even when local; validate certs.
- **Input handling**: argument arrays + allow-listed flags for every tool; strict Pydantic
  validation at the API boundary; no shell string interpolation anywhere.
- **Least privilege**: tool containers run non-root, no host mounts beyond read-only wordlists,
  network egress limited to what a job needs, hard timeouts and resource caps.
- **Supply chain**: pin dependencies, generate SBOMs, run dependency + image scans in CI.

---

## 13. Refinement checklist — direct answers to the four open questions

1. **Data normalization** — a `field_mapping` registry maps every source's raw field names to a
   small set of canonical entity fields (§8.2); values are normalized to canonical formats (E.164
   phones, IDNA domains, geocoded locations) at ingest, so "Mobile Phone Number" and "Cell Number"
   land in the same `PhoneNumber.e164` field.
2. **Rate limiting** — shared Redis token buckets per source/host, exponential backoff with jitter,
   `Retry-After` respect, per-engagement concurrency caps, and per-source circuit breakers (§9);
   active tools additionally inherit scan-rate caps from the scope.
3. **Target ambiguity** — inputs resolve to **ranked candidate entities** with evidence and an
   aggregate confidence score (source reliability × corroboration, §8.4); the operator confirms the
   real in-scope asset before any active step runs. Ambiguity never auto-resolves into an attack.
4. **Tool state management** — every tool run is a persisted **job** with an explicit state machine
   (`QUEUED → RUNNING → SUCCEEDED/FAILED/CANCELLED/TIMED_OUT`), and each transition streams to the
   UI over WebSocket (§6.2), so the interface always reflects true state, not a guess.

---

## 14. MVP first, then iterate

Build in phases; ship each phase working before starting the next.

- **Phase 0 — Foundation (auth gate + audit).** Scope Engine (`load`/`check`/kill-switch), signed
  scope verification, tamper-evident audit log, operator auth/RBAC, Postgres + migrations, FastAPI
  skeleton, Tauri shell that boots **locked** and unlocks on a valid scope. *No recon yet.*
- **Phase 1 — Passive MVP.** DNS + WHOIS/RDAP + certificate-transparency collectors → canonical
  entities → entity profile UI + entity graph. Proves the scope-gated collector pattern and the
  data model end to end.
- **Phase 2 — First active tool (Nmap) end to end.** DockerRunner + job state machine + WebSocket
  streaming + Nmap wrapper (gated on `active_scan`) + tool panel with live output. This is the
  reference implementation every other tool follows.
- **Phase 3 — Content discovery + wordlists.** Gobuster wrapper + wordlist manager/updater + map
  view + charts.
- **Phase 4 — Orchestration.** Playbook DAG engine + the starter playbooks (each step re-scoped).
- **Phase 5 — Intrusive tools (gated).** Hydra, John, Metasploit wrappers behind `active_testing` /
  `exploitation` grants + per-run confirmation + evidence store for hashes.
- **Phase 6 — Reporting & polish.** Report composer, audit-trail export, remote-runner option,
  packaging installers, hardening pass, docs.

At every phase: the Scope Engine and audit log are in the call path. A feature that can run
un-gated is a bug.

---

## 15. Testing strategy

- **Unit** (pytest / Vitest): scope decisions (in/out/exclusion/time-window/action-class — this is
  the most important test suite in the project), normalizers, parsers, confidence math.
- **Integration**: collectors against recorded fixtures/VCR cassettes (never live third parties in
  CI); tool wrappers against a runner stub; audit-chain verification.
- **Contract**: OpenAPI schema drives generated TS types; a test fails the build if front/back
  types drift.
- **E2E** (Playwright): load scope → run a passive collector → run Nmap against a **local
  intentionally-vulnerable target you control** (e.g., a containerized lab box in the compose
  stack) → see live output → see a finding → export a report. Never point e2e at third-party hosts.
- **Security tests**: attempt out-of-scope targets and assert refusal + audit entry; attempt
  intrusive tools without the grant and assert refusal; fuzz the tool-arg builders.

---

## 16. Packaging & distribution

- **Desktop executable**: Tauri bundler produces `.msi` (Windows), `.dmg` (macOS), and
  `.AppImage`/`.deb` (Linux). Code-sign per platform. The installer bundles the frontend + Rust
  core; the backend ships as a `docker-compose` stack the app can launch (local mode) or the app
  can be configured to connect to a remote backend.
- **Backend image set**: build and publish the API, worker, and tool-runner images via CI; pin
  versions; generate SBOMs.
- **First-run**: the app checks for Docker (local mode), offers to pull the backend stack, and walks
  the operator through loading their first scope.
- **Updates**: Tauri's updater for the app; an explicit "update tool images / wordlists" action for
  the runtime pieces (never silent).

---

## 17. Licensing, acceptable use, and legal posture

- Choose an OSS license (e.g., MIT or Apache-2.0) **plus** an `ACCEPTABLE_USE.md` that states
  Azami is for authorized security testing only and that the operator is responsible for holding
  valid authorization for every asset they target. The scope gate enforces this technically; the
  policy states it explicitly.
- `README.md` must lead with the authorization requirement, not bury it.
- `SECURITY.md` covers responsible disclosure for vulnerabilities in **Azami itself**.
- Respect third-party API Terms of Service and data-source licenses; record data provenance so a
  client can see exactly where each fact came from.

---

## 18. What Azami is not

To keep scope honest as the project grows, Azami explicitly does **not**:

- Target assets, systems, or individuals without a loaded, valid, in-window authorization scope.
- Provide any bypass/force flag for the Scope Engine.
- Profile or surveil private individuals as an end in itself; person data appears only as part of
  an authorized organization's attack surface (e.g., an exposed admin contact), and is minimized.
- Defeat access controls, CAPTCHAs, or paywalls in its passive collectors.
- Store credentials in plaintext, or re-use discovered/breached credentials outside an explicitly
  authorized `active_testing` action.

Build the gate first, keep it in every path, and everything above becomes a capable, legitimate,
professional recon console.

---

## 19. Coverage map of the original blueprint

Every item from the original project blueprint, and where it lives in this spec. The only items
marked **Reframed** are those that changed *what the tool is aimed at* (authorized scoped assets
instead of an arbitrary individual); the engineering behind them is unchanged. Items marked
**Out** are the ones excluded on purpose, with the reason.

| Original blueprint item | Status | Where / how |
|---|---|---|
| Cross-platform executable desktop app | **In** | Tauri shell, bundler installers per OS (§2, §16) |
| GitHub repo named Azami, meticulously organized | **In** | Repo layout with `backend/ frontend/ scripts/ docs/ data_sources/` (§3) |
| Modular backend "acquisition engine" | **In** | `osint/` collectors + `tools/` wrappers + `orchestration/` (§5–§7) |
| Data-source integration layer (APIs + scraping: BeautifulSoup/Scrapy) | **In** | Collector interface; official APIs first, disciplined scraping (httpx + selectolax/BeautifulSoup for static, Playwright/Scrapy for dynamic) honoring robots.txt/ToS (§5) |
| Google Maps Platform / geolocation | **In** | Geolocation enrichment collector + MapLibre map view (§5, §11.6) |
| Tool integration layer: Nmap, Gobuster, Hydra, John, Metasploit, tcpdump, as remote/"online" services | **Reframed** | Gated containerized runners (local Docker or remote), uniform job API — aimed at in-scope authorized assets only (§6) |
| Cascading pipeline (domain → gobuster → nmap → hydra …) | **Reframed** | Playbook DAG engine; each derived target re-checked against scope before active steps (§7) |
| Data persistence (PostgreSQL/MongoDB), relational mapping | **In** | PostgreSQL canonical store + entity graph; Mongo is an acceptable document-store variant but Postgres is the default (§2, §8) |
| Dictionary/list management with auto-update | **In** | Wordlist manager + checksum-verified updater + `data_sources/wordlists.catalog.yaml` (§10) |
| Sleek modern dark-mode GUI, state management | **In** | Tauri + React + Tailwind/shadcn, Zustand + TanStack Query (§2, §11) |
| Primary target input + dashboard | **In** | Scope-constrained target picker + engagement dashboard (§11.2–§11.3) |
| Tool panels: click-run, progress bar, real-time output stream | **In** | Per-tool panels, job state machine, WebSocket live stdout (§6.2, §11.4) |
| Data visualization: maps, pie/distribution charts, timelines | **In** | MapLibre + Recharts + Cytoscape graph + engagement timeline (§11.6) |
| README/onboarding covering all deps (Python, Node, Docker) | **In** | README quick start + `OPERATOR_GUIDE.md`; compose-based backend (§3, §16, README) |
| Execution packaging (PyInstaller/Electron Builder style) | **In** | Tauri bundler for the app (Electron Builder is the fallback path); backend as published images (§16) |
| Robust logging + errors surfaced to UI as diagnostics | **In** | Structured logging + actionable UI diagnostics + tamper-evident audit log (§4.3, §11.8) |
| Data normalization (canonical fields) | **In** | `field_mapping` registry + canonical formats (§8.2, §13.1) |
| Rate limiting / backoff | **In** | Shared Redis token buckets, backoff, circuit breakers (§9, §13.2) |
| Target ambiguity → confidence scoring | **In** | Ranked candidate entities with evidence + confidence (§8.4, §13.3) |
| Tool state management (is it scanning / done?) | **In** | Persisted job state machine streamed to UI (§6.2, §13.4) |
| MVP-first, then iterate; per-component tech stack | **In** | Phased roadmap (§14) + stack table (§2) |
| Network identifiers (IPs, netblocks) | **Reframed** | The authorized org's IPs/netblocks, confirmed via RDAP/ASN ownership (§5) |
| WiFi SSID discovery | **Reframed** | Only within an authorized wireless assessment of the client's own premises/networks — never a person's home network |
| Public records: property deeds, professional licenses, business registration | **Reframed** | Used to confirm the **client organization's** ownership/footprint, not to profile a private individual (§5) |
| Exhaustive personal profile of a chosen individual (personal cell, home address, personal social footprint) | **Out** | This is personal surveillance of a private person; excluded on purpose. Person data appears only as part of an authorized org's attack surface (e.g., an exposed admin contact) and is minimized (§5, §18) |
| Attacking a person/system without authorization (Hydra brute-force, John cracking, Metasploit exploitation aimed at an arbitrary target) | **Out (as an ungated capability)** | These tools exist in Azami but only fire against in-scope assets whose scope grants `active_testing`/`exploitation`, plus per-run confirmation. There is no "attack an arbitrary target" mode (§6.3, `AUTHORIZATION_MODEL.md`) |

The takeaway: your architecture is intact — GUI, backend engine, tool integration, pipeline,
persistence, wordlists, visualizations, packaging, and all four refinement answers. The scope gate
is what turns "point it at anyone" into "point it at what you're authorized to test," and that is
the difference between a professional recon platform and something I won't build.
