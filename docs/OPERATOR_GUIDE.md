# Azami — Operator Guide

How to run an engagement with Azami. Assumes the app is running (see the README quick start).

## 1. Sign in

The first boot creates a default **lead** operator (`admin` / `changeme` by default — change these
via `AZAMI_BOOTSTRAP_ADMIN_PASSWORD`). Roles:

- **lead** — load scopes, run everything, use the kill-switch, manage operators.
- **operator** — run collectors/tools within the loaded scope.
- **reviewer** — read-only (entities, audit, report).

## 2. Prepare and load an authorization scope

The console boots **locked**. Nothing runs until a scope is loaded.

1. Write the engagement scope from [`examples/scope.example.yaml`](../examples/scope.example.yaml).
2. (Production) sign it:
   ```bash
   python scripts/sign_scope.py keygen --out-dir ./keys
   # paste the printed public key into integrity.authorizer_pubkey, finalize the file, then:
   python scripts/sign_scope.py sign --scope my-scope.yaml --private-key ./keys/authorizer.key
   ```
3. In the **locked** screen, paste the scope YAML (and the base64 signature in production), then
   **Verify & load scope**. Production keeps `AZAMI_ALLOW_UNSIGNED_SCOPES=false`, so an unsigned or
   tampered scope will not load.

The header now shows the engagement id, whether the signature verified, and the expiry. The
**kill-switch** (lead only) cancels all jobs, revokes the scope, and re-locks the app at any time.

## 3. Passive OSINT

**OSINT** tab → enter an in-scope target (domain, IP, or email) → **Collect**. Runs DNS, RDAP,
certificate transparency, and GeoIP — all scope-gated and audited. Results populate the entity list
(with confidence) and the relationship graph. Out-of-scope targets are refused and logged.

## 4. Active tools

**Tools** tab → pick a tool → set the in-scope target and parameters → **Run**. Output streams live.
Intrusive tools (hydra, john, metasploit, tcpdump) require the scope to grant `active_testing` /
`exploitation` for that asset **and** a per-run confirmation dialog.

- **nmap** — `active_scan`. Params: `scan_type` (connect/syn/version/ping), `ports` (`80,443` /
  `1-1024` / `top1000`), `timing` 0–5.
- **gobuster** — `active_scan`. Params: `mode` (dir/dns), `wordlist` (install it first under
  Wordlists), `threads`.
- **hydra** — `active_testing`. Params: `service`, `userlist`, `passlist`.
- **john** — `active_testing`. Params: `hash_ref` (a file in the engagement evidence store,
  `backend/.azami_data/evidence/`), `wordlist`.
- **metasploit** — `exploitation`. Params: `module` (defaults to a scanner module).
- **tcpdump** — `active_testing`. Params: `interface` (must be listed under
  `constraints.tool_limits.tcpdump.interfaces` in the scope), `count`, optional BPF `filter`.

## 5. Playbooks

**Playbooks** tab → set a root target → run a builtin. Playbooks chain steps and **re-gate every
derived target** (a subdomain/IP discovered passively is only scanned if it independently matches
the scope and its grant allows the action).

## 6. Wordlists

**Wordlists** tab → **Install** a cataloged list. Lists are downloaded on demand, checksum-verified,
and mounted read-only into tool runners.

## 7. Report & audit

- **Audit** tab → live chain-integrity banner + the full tamper-evident trail (allow and deny).
- **Report** tab → the engagement report (attack surface, findings, activity, audit status) with
  Markdown download. `GET /api/audit/export` returns the full chain for the report appendix.
