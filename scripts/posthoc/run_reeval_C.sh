#!/usr/bin/env bash
# POST-HOC SENSITIVITY ANALYSIS (option C): re-evaluate both arms' UNCHANGED final-1 predictions on the
# env-broken instances with the patched harness copy (~/se443/SWT-Bench-posthoc, fixes C1-C3).
# Never regenerates anything; never edits predictions; nothing is passed back to the agent/wrapper.
# Usage: scripts/posthoc/run_reeval_C.sh <tag>   (e.g. posthoc-c-1); sequential, one harness run at a time.
set -uo pipefail
TAG="${1:?tag required, e.g. posthoc-c-1}"
P="$HOME/se443/project"
OUT="$P/runs/posthoc/$TAG"
mkdir -p "$OUT"
INSTANCES=(
  pylint-dev__pylint-6386 pylint-dev__pylint-6903 pylint-dev__pylint-7080
  matplotlib__matplotlib-25311
  sphinx-doc__sphinx-8459 sphinx-doc__sphinx-8475 sphinx-doc__sphinx-8548 sphinx-doc__sphinx-8551
  sphinx-doc__sphinx-8593 sphinx-doc__sphinx-8595 sphinx-doc__sphinx-8621 sphinx-doc__sphinx-8638
  sphinx-doc__sphinx-8721
)
log() { echo "[$(date -Iseconds)] $*" | tee -a "$OUT/reeval.log"; }
log "start tag=$TAG harness_diff_sha256=$(sha256sum "$P/results/final-1/posthoc/harness_posthoc_C1-C3.diff" | cut -c1-16)"
# Gold already run under the patched harness in posthoc-gold-fixed-1 (all resolved): skip gold for these.
GOLD_DONE=" sphinx-doc__sphinx-8459 pylint-dev__pylint-6903 matplotlib__matplotlib-25311 "
for iid in "${INSTANCES[@]}"; do
  # Order per instance: gold (if not done) -> baseline -> workflow. Gating: the instance counts in the
  # sensitivity table only if ITS OWN gold resolves (decided by the analysis afterwards, not here).
  for arm in gold baseline workflow; do
    if [ "$arm" = gold ] && [[ "$GOLD_DONE" == *" $iid "* ]]; then
      log "$iid gold already done in posthoc-gold-fixed-1, skipping"; continue
    fi
    in="$P/runs/$arm/final-1/$iid/harness_input.jsonl"
    [ "$arm" = gold ] && in=gold
    hid="$TAG-$arm-$iid"
    if [ -e "$HOME/se443/swt-runs/$hid/run_meta.txt" ] && grep -q "exit_code:" "$HOME/se443/swt-runs/$hid/run_meta.txt"; then
      log "$hid already complete, skipping"; continue
    fi
    [ -e "$HOME/se443/swt-runs/$hid" ] && mv "$HOME/se443/swt-runs/$hid" "$HOME/se443/swt-runs/$hid.interrupted-$(date +%Y%m%dT%H%M%S)"
    if [ "$in" = gold ]; then log "$hid gold"; else log "$hid input_sha256=$(sha256sum "$in" | cut -c1-16)"; fi
    "$P/scripts/posthoc/run_swt_harness_posthoc.sh" "$hid" "$in" "$iid" >> "$OUT/harness_launcher.log" 2>&1
    log "$hid exit=$?"
  done
done
log "done"
