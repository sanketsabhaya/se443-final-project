#!/usr/bin/env bash
# BASELINE: unchanged mini-SWE-agent (v2.4.6, 04d809ce) + DeepSeek-Flash, unit-test-mode prompt.
# Usage: scripts/run_baseline.sh <run_id> <instance_id>
# One instance per invocation (no parallel runs). Outputs: runs/baseline/<run_id>/<instance_id>/
# Never reuses an output dir: mini-swe-agent deletes an instance's old trajectory on re-run.
set -euo pipefail

RUN_ID="${1:?run_id required}"
IID="${2:?instance_id required}"

PROJECT="$HOME/se443/project"
MINI="$HOME/se443/mini-swe-agent"
CONFIG="$PROJECT/configs/unit_test_gen.yaml"
DATASET="$HOME/.cache/huggingface/hub/datasets--princeton-nlp--SWE-bench_Verified/snapshots/c104f840cc67f8b6eec6f759ebc8b2693d585d4a"
OUT="$PROJECT/runs/baseline/$RUN_ID/$IID"

if [ -e "$OUT" ]; then
  echo "ERROR: $OUT already exists; refusing to overwrite. Use a new run_id." >&2
  exit 1
fi
mkdir -p "$OUT"

# Same image name rule as mini-swe-agent's get_swebench_docker_image_name().
IMAGE="docker.io/swebench/sweb.eval.x86_64.$(echo "$IID" | sed 's/__/_1776_/' | tr 'A-Z' 'a-z'):latest"

META="$OUT/run_meta.txt"
{
  echo "arm: baseline"
  echo "run_id: $RUN_ID"
  echo "instance_id: $IID"
  echo "mini_swe_agent_commit: $(git -C "$MINI" rev-parse HEAD)"
  echo "config: $CONFIG sha256=$(sha256sum "$CONFIG" | cut -d' ' -f1)"
  echo "dataset: $DATASET"
  echo "image: $IMAGE"
  # Sampling settings actually sent: model_kwargs from the config (mini adds nothing else).
  uv run --frozen --project "$MINI" python - "$CONFIG" 2>/dev/null <<'PY'
import json, sys
from minisweagent.config import get_config_from_spec
m = get_config_from_spec(sys.argv[1])["model"]
kw = m.get("model_kwargs", {})
print("model_name:", m["model_name"])
print("model_kwargs_sent:", json.dumps(kw))
if "temperature" in kw:
    print("temperature:", kw["temperature"], "(set in config)")
else:
    print("temperature: not sent -> DeepSeek API default 1.0 (no effect in thinking mode, which is the default)")
print("seed:", kw["seed"] if "seed" in kw else "not sent (DeepSeek chat API has no seed parameter)")
PY
} > "$META"
cp "$CONFIG" "$OUT/config_used.yaml"

# Pre-pull outside the agent's clock (mini's pull_timeout is 120 s; big images can exceed it).
echo "pull_start: $(date -Iseconds)" >> "$META"
docker pull -q "$IMAGE" >> "$OUT/docker_pull.log" 2>&1
echo "pull_end: $(date -Iseconds)" >> "$META"
echo "image_digest: $(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGE")" >> "$META"

echo "start: $(date -Iseconds)" >> "$META"
set +e
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  uv run --frozen --project "$MINI" mini-extra swebench \
    --subset "$DATASET" --split test \
    --filter "^${IID}\$" \
    -c "$CONFIG" \
    -w 1 \
    -o "$OUT" \
  > "$OUT/mini_stdout.log" 2>&1
RC=$?
set -e
{
  echo "end: $(date -Iseconds)"
  echo "exit_code: $RC"
} >> "$META"
# Completion marker for the resumable driver (written for any outcome; failures are data).
printf '{"arm": "baseline", "run_id": "%s", "instance_id": "%s", "exit_code": %d, "finished": "%s"}\n' \
  "$RUN_ID" "$IID" "$RC" "$(date -Iseconds)" > "$OUT/done.json"
exit $RC
