#!/usr/bin/env bash
# Start the full-run driver detached from this terminal / Claude Code (setsid + nohup).
# Usage: scripts/start_experiment.sh <run_id> [extra driver args, e.g. --only IID]
# Resumable: just run the same command again after an interruption.
# Watch:  tail -f ~/se443/project/runs/experiment/<run_id>/driver.log
# Stop:   kill "$(cat ~/se443/project/runs/experiment/<run_id>/driver.pid)"   (then resume later)
set -euo pipefail
RUN_ID="${1:?run_id required}"; shift
EXP="$HOME/se443/project/runs/experiment/$RUN_ID"
mkdir -p "$EXP"
cd "$HOME/se443/project"
setsid nohup python3 scripts/run_experiment.py "$RUN_ID" "$@" >> "$EXP/driver.stdout" 2>&1 < /dev/null &
echo $! > "$EXP/driver.pid"
echo "driver started: pid $(cat "$EXP/driver.pid"), log $EXP/driver.log"
