#!/usr/bin/env bash
# Infra watchdog, NOT part of the frozen experiment: kills a harness container stuck >30 min in "conda-env create".
LOG=~/se443/project/runs/experiment/final-1/watchdog.log
while true; do
  for c in $(docker ps -q); do
    if docker top "$c" 2>/dev/null | grep -q 'conda-env create'; then
      secs=$(( $(date +%s) - $(date -d "$(docker inspect -f '{{.State.StartedAt}}' "$c")" +%s) ))
      if [ "$secs" -gt 1800 ]; then
        echo "$(date -Iseconds) killing $c (conda-env create running ${secs}s)" >> "$LOG"
        docker kill "$c" >> "$LOG" 2>&1
      fi
    fi
  done
  sleep 60
done
