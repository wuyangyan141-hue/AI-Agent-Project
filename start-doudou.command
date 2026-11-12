#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x services/api/.venv/bin/python ]; then
  python3 -m venv services/api/.venv
fi
services/api/.venv/bin/python -m pip install -r services/api/requirements.txt
if [ ! -f node_modules/electron/path.txt ]; then
  npm ci --no-audit --no-fund
fi
if [ ! -f .env ]; then
  cp .env.example .env
fi
npm run build
exec services/api/.venv/bin/python scripts/run_desktop.py
