#!/usr/bin/env python3
"""POST-HOC SENSITIVITY ANALYSIS (option C) for final-1. Not the official result.

Reuses scripts/results.py (same whitelisted report fields, same success/applicability/coverage rules).
Per instance, the evaluation source is:
  - the 13 env-broken instances: patched-harness re-evaluation runs <tag>-{baseline,workflow}-<iid>,
    counted ONLY if that instance's own gold resolved under the patched harness (pre-registered gate,
    notes/progress-log.md commit 8213220); gold read from <tag>-gold-<iid> or posthoc-gold-fixed-1;
  - the 6 instances with usable official verdicts: official final-1 harness runs (unchanged);
  - the 6 officially unevaluated instances (no fix tested): unevaluable for both arms.
Predictions are the unchanged final-1 harness_input.jsonl files. For gold, only `resolved` is read.
Usage: scripts/posthoc/sensitivity.py posthoc-c-1 --confirm-read-harness
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import results as R  # noqa: E402

REEVAL = ["pylint-dev__pylint-6386", "pylint-dev__pylint-6903", "pylint-dev__pylint-7080",
          "matplotlib__matplotlib-25311",
          "sphinx-doc__sphinx-8459", "sphinx-doc__sphinx-8475", "sphinx-doc__sphinx-8548",
          "sphinx-doc__sphinx-8551", "sphinx-doc__sphinx-8593", "sphinx-doc__sphinx-8595",
          "sphinx-doc__sphinx-8621", "sphinx-doc__sphinx-8638", "sphinx-doc__sphinx-8721"]
GOLD_FIXED_1 = {"sphinx-doc__sphinx-8459", "pylint-dev__pylint-6903", "matplotlib__matplotlib-25311"}
NO_FIX = ["astropy__astropy-8872", "matplotlib__matplotlib-22719", "matplotlib__matplotlib-22865",
          "matplotlib__matplotlib-22871", "matplotlib__matplotlib-23299", "pylint-dev__pylint-7277"]


def gold_resolved(swt_runs, hid, iid):
    rep = R.load_json(swt_runs / hid / "run_instance_swt_logs" / hid / "gold" / iid / "report.json")
    if not rep or iid not in rep:
        return None
    return bool(rep[iid].get("resolved"))  # only field read from the gold report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--confirm-read-harness", action="store_true")
    a = ap.parse_args()
    if not a.confirm_read_harness:
        raise SystemExit("refusing: reads harness results; pass --confirm-read-harness only when the user asks")
    root, swt = R.HOME / "se443/project", R.HOME / "se443/swt-runs"
    exp = root / "runs/experiment/final-1"
    instances = sorted(l.strip() for l in (exp / "run_order.txt").read_text().splitlines() if l.strip())
    assert len(instances) == 25 and set(REEVAL) | set(NO_FIX) <= set(instances)

    gold = {}
    for iid in REEVAL:
        hid = "posthoc-gold-fixed-1" if iid in GOLD_FIXED_1 else f"{a.tag}-gold-{iid}"
        gold[iid] = {"gold_run": hid, "gold_resolved": gold_resolved(swt, hid, iid)}

    off, post, source = {}, {}, {}
    for iid in instances:
        for arm in R.ARMS:
            off.setdefault(arm, {})[iid] = R.arm_record(root, swt, exp, "final-1", arm, iid,
                                                        lambda rid, ar, i: f"{rid}-{ar}-{i}")[0]
        if iid in NO_FIX:
            source[iid] = "unevaluable (no fix tested)"
        elif iid in gold:
            source[iid] = "patched re-eval" if gold[iid]["gold_resolved"] else "unevaluable (gold not resolved)"
        else:
            source[iid] = "official final-1"
        for arm in R.ARMS:
            if source[iid] == "patched re-eval":
                rec = R.arm_record(root, swt, None, "final-1", arm, iid, lambda rid, ar, i: f"{a.tag}-{ar}-{i}")[0]
            else:
                rec = off[arm][iid]
            post.setdefault(arm, {})[iid] = rec

    evaluable = [i for i in instances if not source[i].startswith("unevaluable")]
    # sanity: every counted record must actually have been evaluated by the harness
    bad = [(arm, i) for i in evaluable for arm in R.ARMS if post[arm][i]["evaluation"] != "evaluated"]

    def arm_summary(recs, ids):
        rs = [recs[i] for i in ids]
        cov, n = R.mean_or_na([r["coverage_delta"] for r in rs])
        covs, ns = R.mean_or_na([r["coverage_delta"] for r in rs if r["success"]])
        return {"success": sum(r["success"] for r in rs), "applicable": sum(r["applicable"] for r in rs),
                "n": len(ids), "cov": cov, "cov_n": n, "cov_succ": covs, "cov_succ_n": ns}

    def paired(recs, ids):
        b, w = recs["baseline"], recs["workflow"]
        return {"both": sum(b[i]["success"] and w[i]["success"] for i in ids),
                "only_baseline": sum(b[i]["success"] and not w[i]["success"] for i in ids),
                "only_workflow": sum(w[i]["success"] and not b[i]["success"] for i in ids),
                "neither": sum(not b[i]["success"] and not w[i]["success"] for i in ids)}

    out = {
        "label": "POST-HOC SENSITIVITY ANALYSIS (option C, patched harness C1-C3). NOT the official result.",
        "tag": a.tag,
        "harness_diff_sha256_16": __import__("hashlib").sha256(
            (root / "results/final-1/posthoc/harness_posthoc_C1-C3.diff").read_bytes()).hexdigest()[:16],
        "gold": gold, "source": source, "evaluable": evaluable, "not_evaluated_records": bad,
        "official_all25": {arm: arm_summary(off[arm], instances) for arm in R.ARMS},
        "posthoc_evaluable": {arm: arm_summary(post[arm], evaluable) for arm in R.ARMS},
        "posthoc_all25": {arm: arm_summary(post[arm], instances) for arm in R.ARMS},
        "paired_official": paired(off, instances),
        "paired_posthoc_evaluable": paired(post, evaluable),
        "per_instance": {i: {"source": source[i], **({"gold_resolved": gold[i]["gold_resolved"]} if i in gold else {}),
                             **{f"{arm}_{k}": post[arm][i][k] for arm in R.ARMS
                                for k in ("success", "resolved", "applicable", "valid", "coverage_delta")},
                             **{f"official_{arm}_success": off[arm][i]["success"] for arm in R.ARMS}}
                         for i in instances},
    }
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
