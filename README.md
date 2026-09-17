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

Early scaffolding. The specification and authorization model are defined; implementation follows
the phased roadmap in the development prompt, starting with **Phase 0 (the scope engine + audit
log)** before any recon feature.

## Building the app (planned quick start)

Once Phase 0+ lands, the flow will be:

```bash
# Backend stack (API + workers + Postgres + Redis + tool runners)
cd deploy && docker compose up -d

# Desktop app (dev)
cd frontend && npm install && npm run tauri dev
```

Detailed setup — Python/Node versions, Docker requirements, and how to build signed installers —
lives in the development prompt (§16) and will be expanded in `OPERATOR_GUIDE.md`.

## Legal & acceptable use

Azami is for authorized security testing only. See the development prompt (§17) for the licensing
and acceptable-use posture; an `ACCEPTABLE_USE.md` and `LICENSE` are added with the first code drop.
Respect third-party API Terms of Service and data-source licenses; Azami records data provenance so
every fact can be traced to its source.
