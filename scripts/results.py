#!/usr/bin/env python3
"""Results for one experiment run (baseline vs workflow), per README sections 6-7.

Usage: results.py <run_id> [--team NAME] [--confirm-read-harness]
                  [--project-root DIR] [--swt-runs DIR] [--instances FILE]
Writes results/<run_id>/<timestamp>/ (+ results/<run_id>/latest symlink): summary.md, summary.json,
per_instance.csv, calls.csv, workflow_rounds.csv, leaderboard.csv, case_studies.json.

Reads harness outputs, so it is run only AFTER all predictions are final, and on non-pilot runs only with
--confirm-read-harness (given when the user asks for results). From each harness report.json it reads ONLY
resolved, patch_successfully_applied, coverage_pred, coverage_delta_pred (never gold/base fields or test lists).
Nothing produced here is ever fed back to the agent or the wrapper.

Metric definitions (denominator is always the full instance list, e.g. 25):
- success: harness resolved AND our rule-4 validity ok. Missing / invalid / timed-out predictions are failures.
  Harness infra failures that never produced a report are labelled "unevaluated" and count as failures.
- applicability: our validity.json first (invalid -> not applicable, even if the harness "applied" the empty
  replacement patch), then the harness's patch_successfully_applied. No report -> not applicable.
- coverage delta (SWT-Bench, src/grading.py get_pred_report + src/run_evaluation.py make_run_report):
  per instance coverage_delta_pred = (# executable lines changed by the reference fix whose hit count is
  higher with the predicted tests than without them) / (# executable changed lines); a FRACTION in [0, 1].
  It is None when the patch did not apply, when there are no executable changed lines, or when the
  instance errored. The harness's "Mean coverage delta" averages over instances with coverage_pred not None
  and prints 0 when none exist; we report N/A instead of 0, and the number of instances averaged.
- cost: every model call priced at ONE fixed schedule (DeepSeek deepseek-flash standard/peak prices) for both
  arms; per-call UTC timestamp (server `created`) and peak/off-peak flag are informational only.
"""
import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path

HOME = Path.home()
# USD per 1M tokens, deepseek-flash, standard (peak) schedule, from api-docs.deepseek.com/quick_start/pricing
# (read 2026-11-13). Re-check before the final report.
PRICE = {"cache_hit": 0.006, "cache_miss": 0.30, "output": 1.20}
ARMS = ("baseline", "workflow")
REPORT_FIELDS = ("resolved", "patch_successfully_applied", "coverage_pred", "coverage_delta_pred")


def is_peak(ts_utc):
    """Peak = 01:00-04:00 and 06:00-10:00 UTC, Mon-Fri (Chinese public holidays not modelled)."""
    if ts_utc.weekday() >= 5:
        return False
    h = ts_utc.hour
    return 1 <= h < 4 or 6 <= h < 10


def parse_meta(path):
    d = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if ": " in line:
                k, v = line.split(": ", 1)
                d.setdefault(k.strip(), v.strip())
    return d


def iso_seconds(a, b):
    try:
        return (dt.datetime.fromisoformat(b) - dt.datetime.fromisoformat(a)).total_seconds()
    except (TypeError, ValueError):
        return None


def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


# ------------------------------------------------------------------ per-call records
def calls_from_traj(traj_path, arm, iid, round_no):
    t = load_json(traj_path)
    rows = []
    if not t:
        return rows
    for m in t.get("messages", []):
        r = (m.get("extra") or {}).get("response")
        if not isinstance(r, dict):
            continue
        u = r.get("usage") or {}
        det = u.get("completion_tokens_details") or {}
        msg = (r.get("choices") or [{}])[0].get("message") or {}
        vis = len(msg.get("content") or "") + sum(
            len((tc.get("function") or {}).get("arguments") or "") + len((tc.get("function") or {}).get("name") or "")
            for tc in (msg.get("tool_calls") or []))
        rc = msg.get("reasoning_content") or (msg.get("provider_specific_fields") or {}).get("reasoning_content") or ""
        created = r.get("created")
        ts = dt.datetime.fromtimestamp(created, dt.timezone.utc) if created else None
        hit = u.get("prompt_cache_hit_tokens") or 0
        miss = u.get("prompt_cache_miss_tokens") or 0
        comp = u.get("completion_tokens") or 0
        rows.append({
            "arm": arm, "instance_id": iid, "round": round_no, "model": r.get("model"),
            "system_fingerprint": r.get("system_fingerprint"),
            "created_utc": ts.isoformat() if ts else "", "peak": (is_peak(ts) if ts else ""),
            "prompt_cache_hit_tokens": hit, "prompt_cache_miss_tokens": miss, "completion_tokens": comp,
            "reasoning_tokens": det.get("reasoning_tokens"),
            "cost_usd_fixed_peak": (hit * PRICE["cache_hit"] + miss * PRICE["cache_miss"] + comp * PRICE["output"]) / 1e6,
            "_visible_chars": vis, "_reasoning_chars": len(rc),
        })
    return rows


def reasoning_inclusion(calls):
    """Is reasoning_tokens included in completion_tokens? Least-squares fit (no intercept) of
    completion_tokens = alpha * visible_chars + beta * reasoning_tokens over all calls.
    Included -> beta ~ 1 (alpha ~ 1/chars-per-token); not included -> beta ~ 0."""
    pts = [(c["_visible_chars"], c["reasoning_tokens"], c["completion_tokens"]) for c in calls
           if c["reasoning_tokens"] is not None and c["completion_tokens"]]
    if len(pts) < 10:
        return {"verdict": "inconclusive (too few calls)", "n_calls": len(pts)}
    sxx = sum(x * x for x, _, _ in pts); syy = sum(r * r for _, r, _ in pts); sxy = sum(x * r for x, r, _ in pts)
    sxc = sum(x * c for x, _, c in pts); syc = sum(r * c for _, r, c in pts)
    det = sxx * syy - sxy * sxy
    if det == 0 or syy == 0:
        return {"verdict": "inconclusive (degenerate data)", "n_calls": len(pts)}
    alpha = (sxc * syy - syc * sxy) / det
    beta = (syc * sxx - sxc * sxy) / det
    always_le = all(r <= c for _, r, c in pts)
    if always_le and abs(beta - 1) < 0.2:
        verdict = "included (completion_tokens = visible + reasoning)"
    elif abs(beta) < 0.2:
        verdict = "not included"
    else:
        verdict = "inconclusive"
    return {"verdict": verdict, "n_calls": len(pts), "beta_reasoning": round(beta, 3),
            "alpha_per_visible_char": round(alpha, 3),
            "implied_visible_chars_per_token": round(1 / alpha, 2) if alpha > 0 else None,
            "reasoning_le_completion_all": always_le}


# ------------------------------------------------------------------ per instance x arm
def harness_info(swt_runs, exp_dir, hid, iid):
    hdir = swt_runs / hid
    meta = parse_meta(hdir / "run_meta.txt")
    final = load_json(exp_dir / "harness_final" / f"{hid}.json", {}) if exp_dir else {}
    info = {"harness_dir": str(hdir), "harness_ran": bool(meta.get("exit_code")),
            "harness_exit_code": meta.get("exit_code"), "harness_attempts": final.get("attempts"),
            "harness_seconds": iso_seconds(meta.get("start"), meta.get("end")), "report": None, "error": None}
    agg = None
    for f in (hdir / "evaluation_results").glob("*.json") if hdir.exists() else []:
        agg = load_json(f)
    if agg is not None:
        info["error"] = iid in (agg.get("error_ids") or [])
    logs = hdir / "run_instance_swt_logs" / hid
    if logs.exists():
        for model_dir in logs.iterdir():
            if model_dir.name.startswith(("pred_pre__", "pred_post__")):
                continue
            rep = load_json(model_dir / iid / "report.json")
            if rep and iid in rep:
                info["report"] = {k: rep[iid].get(k) for k in REPORT_FIELDS}  # whitelist only
    return info


def arm_record(root, swt_runs, exp_dir, run_id, arm, iid, harness_id_fn):
    d = root / "runs" / arm / run_id / iid
    rec = {"instance_id": iid, "arm": arm, "generated": (d / "done.json").exists()}
    calls = []
    if arm == "baseline":
        meta = parse_meta(d / "run_meta.txt")
        rec["gen_seconds"] = iso_seconds(meta.get("start"), meta.get("end"))
        traj = d / iid / f"{iid}.traj.json"
        t = load_json(traj, {})
        rec["exit_status"] = (t.get("info") or {}).get("exit_status")
        rec["model_calls"] = ((t.get("info") or {}).get("model_stats") or {}).get("api_calls")
        rec["steps_used"] = rec["model_calls"]
        calls += calls_from_traj(traj, arm, iid, 1)
        rec["rounds"], rec["groups"] = None, None
    else:
        budget = load_json(d / "budget.json", {})
        final = load_json(d / "final.json", {})
        rec["gen_seconds"] = budget.get("wall_s")
        rec["steps_used"] = budget.get("steps_used")
        rec["model_calls"] = sum(e["steps"] for e in budget.get("ledger", []) if e.get("kind") == "agent") if budget else None
        rec["rounds"] = final.get("rounds")
        rec["groups"] = final.get("groups")
        rec["final_round"] = final.get("final_round")
        rec["stop_reason"] = final.get("stop_reason")
        rounds = load_json(d / "rounds.json", [])
        rec["exit_status"] = "/".join(str(r["agent"].get("exit_status")) for r in rounds) if rounds else None
        for r in rounds:
            calls += calls_from_traj(d / f"round_{r['round']}" / "mini" / iid / f"{iid}.traj.json", arm, iid, r["round"])
    v = (load_json(d / "harness_input.validity.json", {}) or {}).get(iid)
    rec["valid"] = v["valid"] if v else False
    rec["validity_reason"] = v["reason"] if v else "no_validity_record"
    h = harness_info(swt_runs, exp_dir, harness_id_fn(run_id, arm, iid), iid)
    rep = h["report"]
    rec["harness_seconds"] = h["harness_seconds"]
    rec["harness_dir"] = h["harness_dir"]
    rec["harness_attempts"] = h["harness_attempts"]
    if rep is None or h["error"]:
        rec["evaluation"] = "unevaluated" if rec["generated"] else "missing_prediction"
        rec["resolved"] = False
        rec["harness_applied"] = None
        rec["coverage_delta"] = None
        rec["coverage"] = None
    else:
        rec["evaluation"] = "evaluated"
        rec["resolved"] = bool(rep["resolved"])
        rec["harness_applied"] = rep["patch_successfully_applied"]
        rec["coverage_delta"] = rep["coverage_delta_pred"] if rec["valid"] else None
        rec["coverage"] = rep["coverage_pred"] if rec["valid"] else None
    rec["success"] = bool(rec["valid"] and rec["resolved"])
    rec["applicable"] = bool(rec["valid"] and rec["harness_applied"])
    rec["cost_usd"] = sum(c["cost_usd_fixed_peak"] for c in calls) if calls else 0.0
    rec["n_calls"] = len(calls)
    return rec, calls


# ------------------------------------------------------------------ aggregation and output
def pct(n, d):
    return f"{n}/{d} ({100 * n / d:.1f}%)" if d else "N/A"


def mean_or_na(xs):
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs), len(xs)) if xs else (None, 0)


def fmt_cov(v):
    return "N/A" if v is None else f"{100 * v:.1f}%"


def counts_from_logs(exp_dir):
    out = {"INFRA_RETRY_generation": 0, "HARNESS_RETRY_same_prediction": 0, "interruptions_moved_aside": 0}
    st = exp_dir / "status.tsv" if exp_dir else None
    if st and st.exists():
        for row in csv.DictReader(st.open(), delimiter="\t"):
            if row["stage"] in out:
                out[row["stage"]] += 1
    dl = exp_dir / "driver.log" if exp_dir else None
    if dl and dl.exists():
        out["interruptions_moved_aside"] = sum("moved incomplete" in l for l in dl.read_text().splitlines())
        # moves that were caused by an infra retry are not user/driver interruptions
        out["interruptions_moved_aside"] -= out["INFRA_RETRY_generation"] + out["HARNESS_RETRY_same_prediction"]
        out["interruptions_moved_aside"] = max(0, out["interruptions_moved_aside"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--team", default="TEAM")
    ap.add_argument("--confirm-read-harness", action="store_true")
    ap.add_argument("--project-root", default=str(HOME / "se443/project"))
    ap.add_argument("--swt-runs", default=str(HOME / "se443/swt-runs"))
    ap.add_argument("--instances", default=None)
    ap.add_argument("--harness-id-map", default=None,
                    help="JSON {arm: harness_run_id} for runs not named <run_id>-<arm>-<iid> (pilot tests only)")
    a = ap.parse_args()
    if not a.run_id.startswith(("pilot", "fake")) and not a.confirm_read_harness:
        raise SystemExit("refusing: this reads harness results; pass --confirm-read-harness only when the user asks")
    root, swt_runs = Path(a.project_root), Path(a.swt_runs)
    exp_dir = root / "runs/experiment" / a.run_id
    inst_file = Path(a.instances) if a.instances else (exp_dir / "run_order.txt" if (exp_dir / "run_order.txt").exists()
                                                          else root / "configs/eval_instances.txt")
    instances = sorted(l.strip() for l in inst_file.read_text().splitlines() if l.strip())
    N = len(instances)
    hmap = json.loads(a.harness_id_map) if a.harness_id_map else None
    hid_fn = (lambda rid, arm, iid: hmap[arm]) if hmap else (lambda rid, arm, iid: f"{rid}-{arm}-{iid}")

    recs, calls = {arm: {} for arm in ARMS}, []
    for iid in instances:
        for arm in ARMS:
            r, c = arm_record(root, swt_runs, exp_dir if exp_dir.exists() else None, a.run_id, arm, iid, hid_fn)
            recs[arm][iid] = r
            calls += c

    summary = {"run_id": a.run_id, "n_instances": N, "price_schedule_usd_per_1M": PRICE, "arms": {}}
    for arm in ARMS:
        R = list(recs[arm].values())
        cov_all, n_cov = mean_or_na([r["coverage_delta"] for r in R])
        cov_succ, n_cov_succ = mean_or_na([r["coverage_delta"] for r in R if r["success"]])
        gen, n_gen = mean_or_na([r["gen_seconds"] for r in R])
        arm_calls = [c for c in calls if c["arm"] == arm]
        summary["arms"][arm] = {
            "success": sum(r["success"] for r in R), "applicable": sum(r["applicable"] for r in R),
            "unevaluated": sorted(r["instance_id"] for r in R if r["evaluation"] == "unevaluated"),
            "missing_prediction": sorted(r["instance_id"] for r in R if r["evaluation"] == "missing_prediction"),
            "invalid": {r["instance_id"]: r["validity_reason"] for r in R if r["generated"] and not r["valid"]},
            "coverage_delta_mean": cov_all, "coverage_delta_n": n_cov,
            "coverage_delta_mean_successful": cov_succ, "coverage_delta_n_successful": n_cov_succ,
            "cost_usd_fixed_peak": sum(c["cost_usd_fixed_peak"] for c in arm_calls),
            "n_calls": len(arm_calls), "calls_in_peak_hours": sum(1 for c in arm_calls if c["peak"] is True),
            "avg_generation_seconds": gen, "n_generation_times": n_gen,
            "total_harness_seconds": sum({r["harness_dir"]: (r["harness_seconds"] or 0) for r in R}.values()),
            "fingerprints": sorted({c["system_fingerprint"] for c in arm_calls if c["system_fingerprint"]}),
            "models": sorted({c["model"] for c in arm_calls if c["model"]}),
        }
    both = sum(recs["baseline"][i]["success"] and recs["workflow"][i]["success"] for i in instances)
    only_b = sum(recs["baseline"][i]["success"] and not recs["workflow"][i]["success"] for i in instances)
    only_w = sum(not recs["baseline"][i]["success"] and recs["workflow"][i]["success"] for i in instances)
    neither = N - both - only_b - only_w
    summary["paired"] = {"both": both, "only_baseline": only_b, "only_workflow": only_w, "neither": neither}

    # workflow-only stats
    W = recs["workflow"]
    group_counts = {}
    for r in W.values():
        for k, g in enumerate(r["groups"] or [], start=1):
            group_counts.setdefault(f"round_{k}", {g_: 0 for g_ in ("G1", "G2", "G3", "G4", "G5", "UNTESTED")})
            group_counts[f"round_{k}"][g] = group_counts[f"round_{k}"].get(g, 0) + 1
    revised = [i for i, r in W.items() if (r["rounds"] or 0) > 1]
    not_revised = [i for i, r in W.items() if r["rounds"] == 1]
    summary["workflow"] = {
        "group_counts_per_round": group_counts, "instances_revised": len(revised),
        "success_revised": pct(sum(W[i]["success"] for i in revised), len(revised)),
        "success_not_revised": pct(sum(W[i]["success"] for i in not_revised), len(not_revised)),
        "no_workflow_record": sorted(i for i, r in W.items() if r["rounds"] is None),
    }
    summary["retries"] = counts_from_logs(exp_dir if exp_dir.exists() else None)
    summary["reasoning_tokens_in_completion"] = reasoning_inclusion(calls)
    cases = {
        "successful_both": [i for i in instances if recs["baseline"][i]["success"] and recs["workflow"][i]["success"]],
        "unsuccessful_both": [i for i in instances if not recs["baseline"][i]["success"] and not recs["workflow"][i]["success"]],
        "methods_disagree": [i for i in instances if recs["baseline"][i]["success"] != recs["workflow"][i]["success"]],
    }
    summary["case_study_candidates"] = cases

    # ------------------------------------------------------------ write outputs
    out_root = root / "results" / a.run_id
    out = out_root / dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True, exist_ok=False)
    latest = out_root / "latest"
    if latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out.name)

    cols = ["instance_id"]
    for arm in ARMS:
        cols += [f"{arm}_{k}" for k in ("success", "evaluation", "valid", "validity_reason", "applicable",
                                        "coverage_delta", "steps_used", "model_calls", "gen_seconds", "cost_usd",
                                        "exit_status", "harness_attempts")]
    cols += ["workflow_rounds", "workflow_groups", "workflow_final_round", "workflow_stop_reason"]
    with open(out / "per_instance.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i in instances:
            row = [i]
            for arm in ARMS:
                r = recs[arm][i]
                row += [r["success"], r["evaluation"], r["valid"], r["validity_reason"], r["applicable"],
                        "" if r["coverage_delta"] is None else round(r["coverage_delta"], 4),
                        r["steps_used"], r["model_calls"],
                        "" if r["gen_seconds"] is None else round(r["gen_seconds"], 1), round(r["cost_usd"], 6),
                        r["exit_status"], r["harness_attempts"]]
            wr = recs["workflow"][i]
            row += [wr["rounds"], "|".join(wr["groups"] or []), wr.get("final_round"), wr.get("stop_reason")]
            w.writerow(row)
    with open(out / "calls.csv", "w", newline="") as fh:
        keys = [k for k in (calls[0].keys() if calls else []) if not k.startswith("_")]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(calls)
    with open(out / "workflow_rounds.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["round", "G1", "G2", "G3", "G4", "G5", "UNTESTED"])
        for k, c in sorted(group_counts.items()):
            w.writerow([k] + [c.get(g, 0) for g in ("G1", "G2", "G3", "G4", "G5", "UNTESTED")])
    lb = []
    for arm, name in (("baseline", "mini-SWE-agent + DeepSeek-Flash (baseline)"),
                      ("workflow", "mini-SWE-agent + DeepSeek-Flash + execution-feedback wrapper")):
        s = summary["arms"][arm]
        lb.append([a.team, name, f"{100 * s['success'] / N:.1f}%", fmt_cov(s["coverage_delta_mean"]),
                   f"{100 * s['applicable'] / N:.1f}%", f"${s['cost_usd_fixed_peak']:.4f}",
                   "N/A" if s["avg_generation_seconds"] is None else f"{s['avg_generation_seconds']:.1f} s"])
    with open(out / "leaderboard.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Team", "Method", "Success Rate", "Coverage", "Applicability", "Cost", "Avg Generation Time"])
        w.writerows(lb)
    (out / "case_studies.json").write_text(json.dumps(cases, indent=2))
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    B, Wa = summary["arms"]["baseline"], summary["arms"]["workflow"]
    fmt_s = lambda v: "N/A" if v is None else f"{v:.1f} s"
    gen_b, gen_w = fmt_s(B["avg_generation_seconds"]), fmt_s(Wa["avg_generation_seconds"])
    md = [f"# Results: {a.run_id}", "",
          f"N = {N} instances (denominator for every rate). Generated {dt.datetime.now().isoformat(timespec='seconds')}.", "",
          "## Main metrics", "",
          "| Metric | Baseline | Workflow |", "|---|---|---|",
          f"| Success (resolved) | {pct(B['success'], N)} | {pct(Wa['success'], N)} |",
          f"| Applicability | {pct(B['applicable'], N)} | {pct(Wa['applicable'], N)} |",
          f"| Coverage delta, all (instances with coverage) | {fmt_cov(B['coverage_delta_mean'])} (n={B['coverage_delta_n']}) | {fmt_cov(Wa['coverage_delta_mean'])} (n={Wa['coverage_delta_n']}) |",
          f"| Coverage delta, successful reproductions | {fmt_cov(B['coverage_delta_mean_successful'])} (n={B['coverage_delta_n_successful']}) | {fmt_cov(Wa['coverage_delta_mean_successful'])} (n={Wa['coverage_delta_n_successful']}) |",
          f"| Cost (fixed peak prices) | ${B['cost_usd_fixed_peak']:.4f} | ${Wa['cost_usd_fixed_peak']:.4f} |",
          f"| Model calls (of which in peak hours, info) | {B['n_calls']} ({B['calls_in_peak_hours']}) | {Wa['n_calls']} ({Wa['calls_in_peak_hours']}) |",
          f"| Avg generation time | {gen_b} | {gen_w} |",
          f"| Total evaluation (harness) time | {B['total_harness_seconds'] / 60:.1f} min | {Wa['total_harness_seconds'] / 60:.1f} min |",
          f"| Unevaluated (harness infra failure; counted as failure) | {len(B['unevaluated'])} | {len(Wa['unevaluated'])} |",
          f"| Missing prediction | {len(B['missing_prediction'])} | {len(Wa['missing_prediction'])} |",
          f"| Invalid prediction (rule 4 / empty) | {len(B['invalid'])} | {len(Wa['invalid'])} |",
          "", "Coverage delta: SWT-Bench per-instance fraction of the reference fix's executable changed lines whose "
          "execution count rises with the predicted tests; averaged over instances where it is available (N/A, not 0, when none).",
          "", "## Paired outcomes", "", "| | Workflow succeeds | Workflow fails |", "|---|---|---|",
          f"| **Baseline succeeds** | {both} (both) | {only_b} (only baseline) |",
          f"| **Baseline fails** | {only_w} (only workflow) | {neither} (neither) |",
          "", "## Workflow wrapper", "", "| Round | G1 | G2 | G3 | G4 | G5 | apply-check only |", "|---|---|---|---|---|---|---|"]
    for k, c in sorted(group_counts.items()):
        md.append(f"| {k} | " + " | ".join(str(c.get(g, 0)) for g in ("G1", "G2", "G3", "G4", "G5", "UNTESTED")) + " |")
    md += ["", f"Instances revised: {len(revised)}. Success among revised: {summary['workflow']['success_revised']}; "
               f"among not revised: {summary['workflow']['success_not_revised']}.",
           "", "## Retries and interruptions", "", "| Event | Count |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in summary["retries"].items()]
    ri = summary["reasoning_tokens_in_completion"]
    md += ["", f"Reasoning tokens vs completion tokens: **{ri['verdict']}** ({json.dumps({k: v for k, v in ri.items() if k != 'verdict'})}).",
           "", "## Case-study candidates (sorted by instance ID)", ""]
    for k, v in cases.items():
        md.append(f"- **{k}** ({len(v)}): {', '.join(v) if v else '(none)'}")
    md += ["", "## Leaderboard rows", "", "| Team | Method | Success Rate | Coverage | Applicability | Cost | Avg Generation Time |",
           "|---|---|---|---|---|---|---|"] + ["| " + " | ".join(r) + " |" for r in lb]
    (out / "summary.md").write_text("\n".join(md) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
