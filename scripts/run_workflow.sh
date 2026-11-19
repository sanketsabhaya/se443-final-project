#!/usr/bin/env bash
# WORKFLOW arm launcher. Usage: scripts/run_workflow.sh <run_id> <instance_id>
# Runs scripts/run_workflow.py with the SWT-Bench venv so it can import the harness's GENERIC
# per-repo specs (test commands, log parsers, get_test_directives) read-only.
set -euo pipefail
SWT="$HOME/se443/SWT-Bench"
exec env PYTHONPATH="$SWT" HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  "$SWT/.venv/bin/python" "$HOME/se443/project/scripts/run_workflow.py" "$@"
