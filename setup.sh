#!/bin/bash
# Local development setup. For deployment, prefer the container (see README).
set -euo pipefail

cd "$(dirname "$0")"

python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

mkdir -p images

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env — fill in your API credentials before running the bot."
fi

echo
echo "Done. Try a render that does not post anything:"
echo "  ./.venv/bin/python bot.py --dry-run"
