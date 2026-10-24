#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " Starting CoverageGuard (Backend & Frontend)"
echo "=========================================================="

# Start backend
cd "$(dirname "$0")/backend"
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend
cd "../frontend"
npm run dev &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

echo ""
echo "✅ CoverageGuard API running at: http://127.0.0.1:8000"
echo "✅ CoverageGuard Web UI running at: http://localhost:5173"
echo "Press Ctrl+C to stop both servers."
echo ""

wait
