#!/usr/bin/env bash
#
# Legal Dojo launcher: kills any stale servers, then starts the backend
# (FastAPI/uvicorn on :8000) and frontend (Next.js on :3000) cleanly.
# Press Ctrl+C to stop both. Logs stream to legal-dojo/logs/.
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
LOGS="$ROOT/logs"

echo "==> Stopping any existing Legal Dojo servers..."
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "next dev"        2>/dev/null || true
pkill -f "next-server"     2>/dev/null || true
sleep 1

# --- Preflight checks ---
if [ ! -x "$BACKEND/.venv/bin/uvicorn" ]; then
  echo "ERROR: backend venv not found."
  echo "  Run once:  cd '$BACKEND' && python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "ERROR: frontend dependencies not installed."
  echo "  Run once:  cd '$FRONTEND' && npm install"
  exit 1
fi
if [ ! -f "$BACKEND/.env" ]; then
  echo "WARNING: $BACKEND/.env not found — the AI needs GEMINI_API_KEY there."
fi

mkdir -p "$LOGS"

echo "==> Starting backend  on http://localhost:8000"
# --reload: backend picks up Python changes automatically, no manual restart.
( cd "$BACKEND" && exec .venv/bin/uvicorn main:app --port 8000 --reload ) >"$LOGS/backend.log" 2>&1 &
BPID=$!

echo "==> Starting frontend on http://localhost:3000"
( cd "$FRONTEND" && exec npm run dev -- --port 3000 ) >"$LOGS/frontend.log" 2>&1 &
FPID=$!

cleanup() {
  echo ""
  echo "==> Shutting down..."
  kill "$BPID" "$FPID" 2>/dev/null || true
  pkill -f "uvicorn main:app" 2>/dev/null || true
  pkill -f "next-server"     2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

printf "==> Waiting for backend "
for _ in $(seq 1 30); do curl -s http://localhost:8000/health >/dev/null 2>&1 && break; printf "."; sleep 1; done
printf " ready\n"
printf "==> Waiting for frontend "
for _ in $(seq 1 60); do curl -s http://localhost:3000 >/dev/null 2>&1 && break; printf "."; sleep 1; done
printf " ready\n"

echo ""
echo "  ┌──────────────────────────────────────────────┐"
echo "  │  Legal Dojo is running                        │"
echo "  │    App:  http://localhost:3000                │"
echo "  │    API:  http://localhost:8000                │"
echo "  │    Logs: legal-dojo/logs/{backend,frontend}.log│"
echo "  │    Stop: Ctrl+C                               │"
echo "  └──────────────────────────────────────────────┘"
echo ""

# Stream both logs until Ctrl+C; exit if either server dies.
# (Poll loop instead of `wait -n` so it works on macOS's bash 3.2.)
tail -n +1 -f "$LOGS/backend.log" "$LOGS/frontend.log" &
TPID=$!
while kill -0 "$BPID" 2>/dev/null && kill -0 "$FPID" 2>/dev/null; do
  sleep 1
done
echo "==> A server exited; shutting the other down."
kill "$TPID" 2>/dev/null || true
cleanup
