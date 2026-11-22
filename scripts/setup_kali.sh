#!/usr/bin/env bash
# One-command setup for Kali / Debian: installs what is missing, creates the PostgreSQL database and
# backend/.env, builds the Python venv, runs migrations and tests, installs the frontend.
# Safe to re-run: it keeps an existing backend/.env (and therefore your database password).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
say() { printf '\n==> %s\n' "$*"; }

if [ -z "${SKIP_SYSTEM:-}" ]; then
  say "1/6 Installing system packages (asks for your sudo password)"
  sudo apt-get update
  sudo apt-get install -y python3-full python3-venv libpq-dev postgresql nodejs npm git unzip
  say "2/6 Starting PostgreSQL"
  sudo systemctl enable --now postgresql
else
  say "1-2/6 Skipping system packages and PostgreSQL (SKIP_SYSTEM is set)"
fi

ENV_FILE="$ROOT/backend/.env"
say "3/6 Database and backend/.env"
if [ -f "$ENV_FILE" ]; then
  echo "backend/.env already exists: keeping it."
else
  DB_PW="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
  JWT="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  if [ -z "${SKIP_SYSTEM:-}" ]; then
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='jobhunt'" | grep -q 1; then
      sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER USER jobhunt WITH PASSWORD '$DB_PW'"
    else
      sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE USER jobhunt WITH PASSWORD '$DB_PW'"
    fi
    if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='jobhunt'" | grep -q 1; then
      sudo -u postgres createdb -O jobhunt jobhunt
    fi
  fi
  cp "$ROOT/.env.example" "$ENV_FILE"
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg2://jobhunt:${DB_PW}@localhost:5432/jobhunt|; s|^JWT_SECRET=.*|JWT_SECRET=${JWT}|" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Created backend/.env with a new random database password and JWT secret."
fi

say "4/6 Python environment"
cd "$ROOT/backend"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

say "5/6 Migrations and tests"
./venv/bin/alembic upgrade head
./venv/bin/pytest -q

say "6/6 Frontend"
cd "$ROOT/frontend"
npm install

say "Done"
echo "Python: $("$ROOT/backend/venv/bin/python" --version)   Node: $(node --version)   npm: $(npm --version)"
echo "Start everything with:  $ROOT/scripts/dev.sh"
echo "Then open http://localhost:5173 (register a new account: the old database is gone)."
