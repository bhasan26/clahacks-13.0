#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend"
export COVERAGEGUARD_STATE_PATH="${COVERAGEGUARD_STATE_PATH:-$PWD/backend/data/demo-workspace.sqlite3}"
export COVERAGEGUARD_DISABLE_AI=true
export COVERAGEGUARD_SCHEDULER_ENABLED="${COVERAGEGUARD_SCHEDULER_ENABLED:-true}"
export COVERAGEGUARD_SCHEDULER_SOURCES="${COVERAGEGUARD_SCHEDULER_SOURCES:-demo-insurer-api}"
export COVERAGEGUARD_CHECK_INTERVAL="${COVERAGEGUARD_CHECK_INTERVAL:-86400}"
backend/.venv/bin/python -m uvicorn simulators.hospital:app --host 127.0.0.1 --port 8101 &
hospital_pid=$!
backend/.venv/bin/python -m uvicorn simulators.insurer:app --host 127.0.0.1 --port 8102 &
insurer_pid=$!
backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
coverage_pid=$!
(cd frontend && npm run dev -- --host 127.0.0.1 --strictPort) &
frontend_pid=$!
trap 'kill "$hospital_pid" "$insurer_pid" "$coverage_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM
printf 'Open http://127.0.0.1:5173 → Policy Monitoring. Import 40 claims, sync DEMO, review five baseline representations.\n'
wait
