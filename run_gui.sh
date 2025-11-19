#!/usr/bin/env bash

set -e

# Always operate from the project root (the directory of this script)
cd "$(dirname "$0")"

echo "Using project directory: $(pwd)"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv)…"
  python3 -m venv .venv
fi

echo "Activating virtual environment…"
source .venv/bin/activate

echo "Upgrading pip and installing requirements (including PyQt6)…"
pip install --upgrade pip
pip install -r requirements.txt

echo "Starting GUI…"
python gui.py


