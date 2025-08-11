#!/usr/bin/env bash
set -e
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 not found. Install Python 3.10+ and try again."
  exit 1
fi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export FLASK_ENV=development
export ADMIN_EMAIL=admin@betablockz.local
export ADMIN_PASSWORD=admin123
export SECRET_KEY=change-this-secret-key
echo "Launching BETA BLOCKZ on http://localhost:5000"
python app.py
