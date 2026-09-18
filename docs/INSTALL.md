# Azami — Install & Run

Three ways to run Azami. **Option A** is the fastest way to see it working. Once it's up, jump to
[Using it](#3-use-it).

## 0. Prerequisites

- **Python 3.11+**, **Node 18+**, and **git**.
- **Docker** — required for Option C, and for actually executing the security tools (nmap, hydra, …)
  via pinned runner images.
- Verify: `python3 --version`, `node --version`, `git --version`.

## 1. Get the code

```bash
git clone https://github.com/voidless026-design/Azami.git
cd Azami
# If this branch has not been merged yet:
git checkout claude/azami-osint-gui-app-yor7j5
```

---

## Option A — One command (macOS / Linux, easiest)

```bash
./scripts/dev.sh
```

Creates the Python venv, installs backend + frontend deps, starts the backend on **:8099** and the
frontend dev server on **:5173**. Open **http://127.0.0.1:5173**.

## Option B — Run each tier manually (all platforms, incl. Windows)

**Terminal 1 — backend:**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
AZAMI_ALLOW_UNSIGNED_SCOPES=true uvicorn azami.main:app --port 8099 --reload
```

On Windows PowerShell, set the env var first, then run uvicorn:

```powershell
$env:AZAMI_ALLOW_UNSIGNED_SCOPES="true"
uvicorn azami.main:app --port 8099 --reload
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm install
npm run dev                          # http://127.0.0.1:5173
```

## Option C — Docker (backend stack, closest to production)

```bash
docker compose -f deploy/docker-compose.yml up -d --build

# To actually run the security tools, build the runner images the Docker runner uses:
for t in nmap gobuster hydra john metasploit tcpdump; do docker build -t azami/$t:latest runners/$t; done
```

Backend comes up on **:8099** with Postgres + Redis. Run the frontend from Option B against it, or
build the desktop app (below). Production keeps `AZAMI_ALLOW_UNSIGNED_SCOPES=false` — scopes must be
signed (see [`../scripts/sign_scope.py`](../scripts/sign_scope.py)).

---

## 3. Use it

1. Open **http://127.0.0.1:5173** and sign in: **`admin` / `changeme`**
   (change via `AZAMI_BOOTSTRAP_ADMIN_PASSWORD`).
2. The console boots **locked**. Paste [`examples/scope.example.yaml`](../examples/scope.example.yaml)
   into the scope box and click **Verify & load scope**.
   - ⚠️ That example has a **Mon–Fri 13:00–21:00 UTC blackout**, so *active* scans pause during those
     hours (passive still works). To test active tools any time, remove the `blackout_windows:` block
     or use your own scope.
3. Explore: **OSINT** (passive collection), **Tools** (run nmap etc. with live output),
   **Playbooks**, **Wordlists**, **Audit**, **Report**. Full walkthrough in
   [`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md).

## 4. Run the tests (optional)

```bash
cd backend && source .venv/bin/activate && pytest -q      # 46 passing
```

## 5. Build the desktop executable (Tauri)

Requires the Rust toolchain (<https://rustup.rs>) plus your OS's Tauri prerequisites.

```bash
cd frontend
npm run tauri icon path/to/any-square-icon.png            # generates the required app icons
VITE_API_BASE=http://127.0.0.1:8099 npm run tauri build
```

The installer lands in `frontend/src-tauri/target/release/bundle/` (`.dmg` / `.msi` /
`.AppImage`). The desktop app talks to the local backend on :8099, so keep that running (Option B/C).

---

## Notes & gotchas

- **Security binaries must exist where jobs run.** In dev (Option A/B), install them locally
  (`brew install nmap`, `apt install nmap`, …) or a job reports "tool unavailable" — the wrappers,
  scope-gating, and live streaming still work and are unit-tested. Option C's runner images bundle
  them.
- **Everything is scope-gated.** You cannot run against a target unless it is in the loaded scope;
  every attempt (allow or deny) is written to the tamper-evident audit log.
- **Ports:** backend `8099`, frontend dev `5173`. Change the backend port with
  `uvicorn ... --port N` (and update `frontend/vite.config.ts`'s proxy target).
