# Azami — Authorization Model

This document specifies the mechanism that makes Azami a legitimate, professional recon platform
rather than a general-purpose attack tool: **nothing runs against a target without a valid,
signed, in-window authorization scope, and every action is checked against that scope and audited.**
Read this alongside §4 of `DEVELOPMENT_PROMPT.md`. Build this before any recon feature.

## Design goals

1. **Fail closed.** With no scope loaded, Azami does nothing to any target. The default state is
   locked, not permissive.
2. **Central, unavoidable gate.** A single `scope.check(target, action)` sits in the call path of
   every collector, tool wrapper, and playbook step. There is no code path around it and no
   force/override flag in the product.
3. **Cryptographic authenticity.** A scope is only honored if a detached signature over its
   canonical bytes verifies against a configured authorizer key. A hand-edited scope does not load.
4. **Tamper-evident accountability.** Every decision (allow or deny) and every action is appended
   to a hash-chained audit log the app cannot silently edit.

## The scope object

Parsed and validated (Pydantic) from a signed YAML/JSON file (see `examples/scope.example.yaml`):

- `engagement` — id, client, assessing org, `authorization_ref` (the signed SOW/contract), and
  contacts including an emergency-stop contact.
- `time_window` — `not_before`, `not_after`, optional `blackout_windows`.
- `in_scope[]` — asset classes, each with `domains` / `ip_ranges` / `hosts` / `urls` / `asns` and
  an `allowed_actions` grant.
- `out_of_scope` — exclusions that always win.
- `constraints` — rate caps, concurrency caps, allowed source IPs, tool-specific limits.
- `integrity` — signature file reference, authorizer public-key fingerprint, scheme.

## Actions (asset-class grants)

Actions form an escalating ladder; a target's asset class must grant the action or it is denied.

| Action | Meaning | Example modules |
|---|---|---|
| `passive` | Observation only, no packets that probe the target's services beyond normal resolution | DNS, WHOIS/RDAP, cert transparency, public records, breach-exposure lookup |
| `active_scan` | Non-intrusive probing of in-scope network/web services | Nmap, Gobuster |
| `active_testing` | Intrusive testing that interacts with auth/credentials | Hydra, John the Ripper |
| `exploitation` | Verifying a vulnerability by exercising it | Metasploit exploit modules |

Passive is the floor; each higher rung must be granted explicitly per asset class. Granting
`active_scan` does **not** imply `active_testing`.

## The decision function

```
check(target, action):
    t = canonicalize(target)             # domain→registrable form, IP→canonical, url→host
    if t matches out_of_scope:           return Deny("excluded")
    if now not in time_window:           return Deny("outside authorized time window")
    if now in a blackout_window:         return Deny("blackout window")
    cls = in_scope class containing t
    if cls is None:                      return Deny("not in scope")
    if not cls.allowed_actions[action]:  return Deny(f"{action} not authorized for this asset")
    return Allow(cls, constraints)
```

Rules that matter:

- **Exclusions beat inclusions**, always, and are checked first.
- **Canonicalization before matching** so `HTTPS://Example.com/`, `example.com`, and a resolved IP
  are judged consistently, and so an attacker-typed near-miss cannot slip through.
- **Derived targets are re-checked.** A subdomain discovered by passive recon is not automatically
  scannable — it must itself match an in-scope class whose grant allows the intended action.
- **Every call is logged**, allow or deny, with the reason.

## Extra gates for intrusive actions

Beyond the scope grant, `active_testing` and `exploitation` require, at run time:

- an **operator confirmation** dialog naming the exact target, tool, and parameters;
- adherence to scope `constraints` (rate/concurrency caps, allowed source IPs, lockout-aware
  thresholds); and
- for `John`, that the input hashes live in the engagement's evidence store (obtained lawfully
  within the engagement) — no external hash sources.

## The kill-switch

A single operation that:

1. cancels all `QUEUED`/`RUNNING` jobs across the engagement,
2. revokes the active scope, returning the app to the locked state, and
3. writes a `KILL_SWITCH` audit record.

It is always reachable from the UI header. After a kill-switch, unlocking requires re-loading and
re-verifying the scope.

## The audit log

- Append-only table; the app's DB role has `INSERT` only (no `UPDATE`/`DELETE`) on it.
- Each record: `{id, ts, engagement_id, operator_id, action, target, tool, parameters(secrets
  redacted), scope_decision, result_hash, prev_hash}`.
- `prev_hash = H(previous_record)` chains records so any edit/deletion breaks the chain; a verifier
  walks it and reports the first break.
- Exported as a signed appendix to the engagement report.

## Failure modes and how the model handles them

| Situation | Behavior |
|---|---|
| No scope loaded | App locked; all active endpoints refuse. |
| Signature invalid / missing | Scope not loaded; app stays locked. |
| Target outside time window | Deny + audit. |
| Out-of-scope target typed by operator | Deny + audit; UI shows a deliberate refusal, not an error. |
| Intrusive tool without the grant | Deny + audit; no confirmation dialog is even offered. |
| Derived (discovered) target not in scope | Deny for active steps; it can still be recorded passively. |
| Scope expires mid-engagement | Running jobs finish or are stopped per policy; no new active work starts. |

Build these as the first test suite in the project (`§15`). If any of these can be made to run,
the gate is broken.
