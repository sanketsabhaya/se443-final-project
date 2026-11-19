#!/usr/bin/env bash
# Run the official SWT-Bench harness (unit-test mode) on SWT-Bench Verified.
# Usage: scripts/run_swt_harness.sh <run_id> <predictions.jsonl|gold> [instance_id ...]
# Outputs go to ~/se443/swt-runs/<run_id>/ (never reused, never overwritten).
# NOTE: harness logs contain reference test patches (evaluator-only). Do not feed
# anything from swt-runs back into generation, prompts, or feedback.
set -euo pipefail

RUN_ID="${1:?run_id required}"
PREDS="${2:?predictions path or 'gold' required}"
shift 2
INSTANCE_ARGS=()
if [ "$#" -gt 0 ]; then INSTANCE_ARGS=(--instance_ids "$@"); fi

SWT="$HOME/se443/SWT-Bench"
RUN_DIR="$HOME/se443/swt-runs/$RUN_ID"
DATASET_NAME="princeton-nlp/SWE-bench_Verified"

if [ -e "$RUN_DIR" ]; then
  echo "ERROR: $RUN_DIR already exists; refusing to overwrite. Use a new run_id." >&2
  exit 1
fi
if [ "$PREDS" != "gold" ]; then
  PREDS="$(realpath "$PREDS")"
  [ -f "$PREDS" ] || { echo "ERROR: predictions file not found: $PREDS" >&2; exit 1; }
fi

mkdir -p "$RUN_DIR"
ln -s "$SWT/dataset" "$RUN_DIR/dataset"   # harness reads dataset/filter_cases_*.txt relative to cwd
[ "$PREDS" != "gold" ] && cp "$PREDS" "$RUN_DIR/predictions_input.jsonl"
cd "$RUN_DIR"

META="$RUN_DIR/run_meta.txt"
{
  echo "run_id: $RUN_ID"
  echo "predictions: $PREDS"
  echo "instances: ${*:-<all in predictions>}"
  echo "dataset: $DATASET_NAME --filter_swt (HF offline, cached rev c104f840cc67f8b6eec6f759ebc8b2693d585d4a)"
  echo "swt_bench_commit: $(git -C "$SWT" rev-parse HEAD)"
  echo "start: $(date -Iseconds)"
  echo "--- disk before"; df -h /mnt/d | tail -1; docker system df
} > "$META"

set +e
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONPATH="$SWT" \
  "$SWT/.venv/bin/python" -m src.main \
    --dataset_name "$DATASET_NAME" \
    --filter_swt \
    --predictions_path "$PREDS" \
    --max_workers 1 \
    --run_id "$RUN_ID" \
    "${INSTANCE_ARGS[@]}" \
  > "$RUN_DIR/harness_stdout.log" 2>&1
RC=$?
set -e

{
  echo "end: $(date -Iseconds)"
  echo "exit_code: $RC"
  echo "--- disk after"; df -h /mnt/d | tail -1; docker system df
} >> "$META"
exit $RC
