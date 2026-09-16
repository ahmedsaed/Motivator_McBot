#!/bin/bash
# Wrapper for running the bot from cron on a machine with a local checkout.
# LOG_FILE can be overridden; it defaults to a log next to this script.
set -euo pipefail

cd "$(dirname "$0")"

log_file="${LOG_FILE:-$PWD/logs/motivator_bot.log}"
mkdir -p "$(dirname "$log_file")"

# Load credentials from .env if present.
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

{
    printf '+%s+\n' "$(printf '=%.0s' {1..50})"
    printf '| %-48s |\n' "$(date '+%Y-%m-%d %H:%M:%S')"
    printf '+%s+\n' "$(printf '=%.0s' {1..50})"
} >> "$log_file"

status=0
./.venv/bin/python bot.py >> "$log_file" 2>&1 || status=$?

if [ $status -eq 0 ] && command -v notify &> /dev/null; then
    notify "MotivatorMcBot tweeted successfully"
fi

exit $status
