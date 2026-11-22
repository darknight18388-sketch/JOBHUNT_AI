#!/usr/bin/env bash
# Starts PostgreSQL, the backend (port 8000) and the frontend (port 5173). Ctrl+C stops both.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -x "$ROOT/backend/venv/bin/uvicorn" ] || { echo "Backend is not set up. Run: $ROOT/scripts/setup_kali.sh"; exit 1; }
[ -d "$ROOT/frontend/node_modules" ] || { echo "Frontend is not set up. Run: $ROOT/scripts/setup_kali.sh"; exit 1; }
sudo systemctl start postgresql
trap 'trap - TERM INT EXIT; kill 0' TERM INT EXIT
( cd "$ROOT/backend" && exec ./venv/bin/uvicorn app.main:app --reload --port 8000 ) &
( cd "$ROOT/frontend" && exec npm run dev ) &
wait
