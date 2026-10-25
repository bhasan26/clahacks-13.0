#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend"
export COVERAGEGUARD_STATE_PATH="${COVERAGEGUARD_STATE_PATH:-$PWD/backend/data/demo-workspace.sqlite3}"
export COVERAGEGUARD_DISABLE_AI=true
export COVERAGEGUARD_SCHEDULER_ENABLED="${COVERAGEGUARD_SCHEDULER_ENABLED:-true}"
export COVERAGEGUARD_SCHEDULER_SOURCES="${COVERAGEGUARD_SCHEDULER_SOURCES:-demo-insurer-api}"
export COVERAGEGUARD_CHECK_INTERVAL="${COVERAGEGUARD_CHECK_INTERVAL:-86400}"

# Preflight: fail fast with a fix instead of leaving a half-started demo.
if [ ! -x backend/.venv/bin/python ]; then
  echo "Missing backend/.venv. Run: python3 -m venv backend/.venv && backend/.venv/bin/python -m pip install -r backend/requirements.txt" >&2
  exit 1
fi
if [ ! -d frontend/node_modules ]; then
  echo "Missing frontend/node_modules. Run: (cd frontend && npm ci)" >&2
  exit 1
fi
for port in 8101 8102 8000 5173; do
  if lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Port $port is already in use (is another demo running?). Stop it first:" >&2
    lsof -iTCP:"$port" -sTCP:LISTEN -P >&2 || true
    exit 1
  fi
done

backend/.venv/bin/python -m uvicorn simulators.hospital:app --host 127.0.0.1 --port 8101 &
hospital_pid=$!
backend/.venv/bin/python -m uvicorn simulators.insurer:app --host 127.0.0.1 --port 8102 &
insurer_pid=$!
backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
coverage_pid=$!
(cd frontend && npm run dev -- --host 127.0.0.1 --strictPort) &
frontend_pid=$!
trap 'kill "$hospital_pid" "$insurer_pid" "$coverage_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM

for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1 \
    && curl -sf http://127.0.0.1:8101/health >/dev/null 2>&1 \
    && curl -sf http://127.0.0.1:8102/health >/dev/null 2>&1 && break
  if ! kill -0 "$coverage_pid" 2>/dev/null; then
    echo "CoverageGuard API failed to start; see the log above." >&2
    exit 1
  fi
  sleep 0.5
done
# Load the demo so the app opens ready (set SEED_DEMO=0 to start empty).
if [ "${SEED_DEMO:-1}" != "0" ]; then
  backend/.venv/bin/python scripts/seed_demo.py
fi
printf 'Open http://127.0.0.1:5173\n'
wait
