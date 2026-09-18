#!/usr/bin/env bash
# Azami local dev bootstrap + run. Runs the backend (SQLite, in-process jobs) and the
# frontend dev server (which proxies /api to the backend).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Backend: venv + deps"
cd "$ROOT/backend"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e ".[dev]"

echo "==> Backend: starting on http://127.0.0.1:8099 (default creds admin/changeme)"
AZAMI_ALLOW_UNSIGNED_SCOPES=true \
AZAMI_JWT_SECRET="${AZAMI_JWT_SECRET:-dev-secret-change-me-32bytes-minimum}" \
  uvicorn azami.main:app --port 8099 --reload &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

echo "==> Frontend: deps + dev server on http://127.0.0.1:5173"
cd "$ROOT/frontend"
npm install --no-audit --no-fund
npm run dev
