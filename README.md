# Azami

**Azami is a cross-platform desktop console for _authorized_ reconnaissance and OSINT during
scoped security engagements** — penetration tests, red-team work, bug-bounty programs with a
defined scope, and organizations assessing their own assets.

> ### ⚠️ Authorization is required, and it is enforced
> Azami boots **locked**. It does nothing to any target until you load a **signed
> Rules-of-Engagement (RoE) scope** that declares which assets you are authorized to test, which
> actions are permitted per asset, and the authorized time window. Every action is checked against
> that scope and written to a tamper-evident audit log. There is no bypass or "force" flag.
>
> You are responsible for holding valid authorization for every asset you point Azami at. Using it
> to profile, surveil, or attack people or systems you are not authorized to test is not a supported
> use — the scope gate is designed to prevent exactly that.

## What it does

- **Load & verify an engagement scope** — targets, allowed actions, exclusions, time window, signed
  by the authorizer. See [`examples/scope.example.yaml`](examples/scope.example.yaml).
- **Passive OSINT** on in-scope assets — DNS, WHOIS/RDAP, certificate transparency, ASN/netblock
  ownership, breach-exposure reporting, public records confirming the client org's footprint.
- **Active recon & testing tools**, gated per scope — Nmap, Gobuster, Hydra, John the Ripper,
  Metasploit, tcpdump — run as containerized jobs with live output streamed to the UI.
- **Playbooks** that chain steps, re-checking scope on every derived target.
- **Normalized, confidence-scored findings** with an entity graph, map, charts, and timeline.
- **Reporting** — an engagement report plus the full audit trail as a signed appendix.

## Documentation

| Doc | What's in it |
|---|---|
| [`docs/DEVELOPMENT_PROMPT.md`](docs/DEVELOPMENT_PROMPT.md) | The complete end-to-end build spec: stack, architecture, backend, frontend, data model, packaging, MVP-first roadmap, and a coverage map of the original blueprint. **Start here.** |
| [`docs/AUTHORIZATION_MODEL.md`](docs/AUTHORIZATION_MODEL.md) | The scope / RoE model, the decision function, the kill-switch, and the tamper-evident audit log. |
| [`examples/scope.example.yaml`](examples/scope.example.yaml) | A complete, annotated authorization scope file. |

Additional docs referenced by the spec (`ARCHITECTURE.md`, `DATA_MODEL.md`, `API.md`,
`OPERATOR_GUIDE.md`) are produced during their respective build phases.

## Technology at a glance

- **Desktop app:** Tauri (Rust core) + React + TypeScript + Tailwind/shadcn
- **Backend:** Python 3.12 + FastAPI, Celery + Redis workers, PostgreSQL 16
- **Tooling:** each security tool in a pinned Docker runner (local or remote)
- **Packaging:** Tauri bundler → `.msi` / `.dmg` / `.AppImage`/`.deb`; backend as a `docker-compose` stack

## Project status

All phases of the roadmap are implemented and tested end to end:

- **Backend** (Python / FastAPI): the scope engine + tamper-evident audit log, operator auth/RBAC,
  passive OSINT collectors + entity model, the tool-integration layer (runners + job state machine +
  WebSocket streaming) with six gated tool wrappers, the wordlist manager, the playbook engine, and
  reporting. 46 tests pass (the scope-decision matrix, signature verification, audit chain/tamper
  detection, job lifecycle, and playbook re-gating).
- **Frontend** (React / Vite / TypeScript / Tailwind): the boot-locked scope gate, dashboard,
  live-streaming tools panel, OSINT + relationship graph, playbooks, wordlists, audit, and report
  screens. Verified with a live browser run against the backend.
- **Infra**: backend Dockerfile, `deploy/docker-compose.yml`, per-tool runner Dockerfiles, Tauri
  packaging config, and GitHub Actions CI.

## Quick start (local dev)

The backend defaults to zero external services (SQLite + in-process job execution), so it runs
immediately. One command brings up both tiers:

```bash
./scripts/dev.sh          # backend on :8099 + frontend dev server on :5173
```

Or run each tier manually:

```bash
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
AZAMI_ALLOW_UNSIGNED_SCOPES=true uvicorn azami.main:app --port 8099 --reload

# Frontend (proxies /api to the backend)
cd frontend && npm install && npm run dev   # http://127.0.0.1:5173
```

Sign in with `admin` / `changeme` (change via `AZAMI_BOOTSTRAP_ADMIN_PASSWORD`), then load a scope
(paste [`examples/scope.example.yaml`](examples/scope.example.yaml)). Run the tests with
`cd backend && pytest -q`. See [`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md) for the full flow.

## Production

```bash
# Backend stack: API + Postgres + Redis (tool runners are launched per-job as containers)
docker compose -f deploy/docker-compose.yml up -d --build

# Build the tool-runner images the Docker runner uses
for t in nmap gobuster hydra john metasploit tcpdump; do docker build -t azami/$t:latest runners/$t; done

# Desktop installer (Tauri) — add app icons first (frontend/src-tauri/icons/README.md)
cd frontend && VITE_API_BASE=http://127.0.0.1:8099 npm run tauri build
```

Production keeps `AZAMI_ALLOW_UNSIGNED_SCOPES=false` (scopes must be signed) and uses Postgres +
Redis. Detailed setup and packaging live in the development prompt (§16).

## Legal & acceptable use

Azami is for authorized security testing only. See the development prompt (§17) for the licensing
and acceptable-use posture; an `ACCEPTABLE_USE.md` and `LICENSE` are added with the first code drop.
Respect third-party API Terms of Service and data-source licenses; Azami records data provenance so
every fact can be traced to its source.
