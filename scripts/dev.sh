#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sudo systemctl start postgresql
cd "$ROOT/backend" && source venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
BACK=$!
cd "$ROOT/frontend"
npm run dev &
FRONT=$!
trap 'kill $BACK $FRONT 2>/dev/null' EXIT INT TERM
wait
