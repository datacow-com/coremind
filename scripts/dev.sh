#!/usr/bin/env bash
set -euo pipefail

BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-5173}
EMBEDDED_PORT=${EMBEDDED_PORT:-5174}

echo "Starting backend on http://localhost:${BACKEND_PORT}"
python3 -m uvicorn server.main:app --reload --port ${BACKEND_PORT} &
PID_BACKEND=$!

echo "Starting frontend on http://localhost:${FRONTEND_PORT}"
npm --prefix frontend run dev -- --port ${FRONTEND_PORT} &
PID_FRONTEND=$!

echo "Starting embedded-ui on http://localhost:${EMBEDDED_PORT}"
npm --prefix apps/embedded-ui run dev -- --port ${EMBEDDED_PORT} &
PID_EMBEDDED=$!

cleanup() {
  echo "Stopping services..."
  kill ${PID_BACKEND} ${PID_FRONTEND} ${PID_EMBEDDED} 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Backend:   http://localhost:${BACKEND_PORT}"
echo "Frontend:  http://localhost:${FRONTEND_PORT}"
echo "Embedded:  http://localhost:${EMBEDDED_PORT}"

wait

