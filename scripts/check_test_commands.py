#!/usr/bin/env python3
"""Verify the wrapper's generic test command + harness parser inside SWE-bench images, on NON-evaluation
instances, using only tests that already exist in the repo (no gold patch, no test_patch, no agent patch).

Uses the wrapper's own functions (image name, docker exec, env prefix, label format, key matching)
so it checks exactly the code path the wrapper uses.
Usage (SWT venv, PYTHONPATH=~/se443/SWT-Bench):
    check_test_commands.py <out_dir> [--infra-check-eval-images] <iid>:<test_file>[::<Class>]::<func> ...
--infra-check-eval-images (user-approved, 2026-11-13): allow evaluation-instance IMAGES for an infrastructure-only
check: one existing, generic repo test; no agent, no patch, no test_patch, no harness, no issue text is read.
"""
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location("wf", Path(__file__).with_name("run_workflow.py"))
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)

out_dir = Path(sys.argv[1])
out_dir.mkdir(parents=True, exist_ok=False)
eval_ids = set((wf.PROJECT / "configs/eval_instances.txt").read_text().split())
infra_eval = "--infra-check-eval-images" in sys.argv
summary = []
for arg in [a for a in sys.argv[2:] if a != "--infra-check-eval-images"]:
    iid, test = arg.split(":", 1)
    assert iid not in eval_ids or infra_eval, f"{iid} is an evaluation instance; refusing"
    tbl = wf.pq.read_table(sorted((wf.DATASET / "data").glob("test-*.parquet"))[0],
                           columns=["instance_id", "repo", "version"])  # issue text never loaded
    inst = next(r for r in tbl.to_pylist() if r["instance_id"] == iid)
    repo, version = inst["repo"], inst["version"]
    parts = test.split("::")
    t = {"file": parts[0], "cls": ".".join(parts[1:-1]) or None, "func": parts[-1], "label": test}
    args = [t["file"]] if repo == "sympy/sympy" else [test]  # same rule as build_targets
    img = wf.image_name(iid)
    subprocess.run(["docker", "pull", "-q", img], check=True, capture_output=True)
    cid = subprocess.run(["docker", "run", "-d", "--rm", img, "sleep", "infinity"], check=True,
                         capture_output=True, text=True).stdout.strip()
    try:
        spec_i = wf.MAP_VERSION_TO_INSTALL[repo][version]
        cmd = " ".join([wf.MAP_REPO_TO_TEST_FRAMEWORK_VERBOSE[repo][version], *args])
        t0 = time.time()
        rc, output, timed_out = wf.docker_exec(
            cid, wf.ENV_PREFIX + "\n".join(spec_i.get("eval_commands", [])) + "\n" + cmd + "\n", timeout=900)
        dur = round(time.time() - t0, 1)
    finally:
        subprocess.run(["docker", "rm", "-f", cid], capture_output=True)
    statuses = wf.MAP_REPO_TO_PARSER[repo](output)
    matched = {k: s for k, s in statuses.items() if wf.key_matches(k, t)}
    (out_dir / f"{iid}.output.txt").write_text(output)
    row = {"infra_check_on_eval_image": iid in eval_ids, "instance_id": iid, "repo": repo, "version": version, "command": cmd, "exit_code": rc,
           "timed_out": timed_out, "duration_s": dur, "n_parsed": len(statuses), "target_matched": matched,
           "ok": bool(matched) and not timed_out}
    summary.append(row)
    print(json.dumps(row))
(out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
