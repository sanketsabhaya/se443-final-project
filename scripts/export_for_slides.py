#!/usr/bin/env python3
"""Build ~/se443/export-for-slides/ from committed results (no harness access, no new runs).

Reads: results/final-1/latest/{summary.json,summary.md,per_instance.csv,leaderboard.csv},
results/final-1/case_studies.md, results/final-1/posthoc/sensitivity_posthoc-c-1.{json,md},
and both arms' final predictions runs/<arm>/final-1/<iid>/harness_input.jsonl (agent output only).
Usage: scripts/export_for_slides.py [OUT_DIR]   (refuses to overwrite an existing OUT_DIR)
"""
import csv
import json
import shutil
import sys
from pathlib import Path

HOME = Path.home()
P = HOME / "se443/project"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HOME / "se443/export-for-slides"
LATEST = P / "results/final-1/latest"
POST = P / "results/final-1/posthoc"
ARMS = ("baseline", "workflow")
CASES = ["sympy__sympy-15017", "matplotlib__matplotlib-14623"]


def pct(n, d):
    return f"{n}/{d} ({100 * n / d:.1f}%)"


def cov(v, n):
    return "N/A" if v is None else f"{100 * v:.1f}% (n={n})"


def added_lines(patch):
    out, cur = [], None
    for ln in (patch or "").splitlines():
        if ln.startswith("+++ "):
            cur = ln[6:] if ln.startswith("+++ b/") else ln[4:]
            out.append(f"# file: {cur}")
        elif ln.startswith("+"):
            out.append(ln[1:])
    while out and not out[-1].strip():
        out.pop()
    return out


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} exists; refusing to overwrite")
    OUT.mkdir(parents=True)
    S = json.load(open(LATEST / "summary.json"))
    X = json.load(open(POST / "sensitivity_posthoc-c-1.json"))
    B, W = S["arms"]["baseline"], S["arms"]["workflow"]
    PB, PW = X["posthoc_evaluable"]["baseline"], X["posthoc_evaluable"]["workflow"]
    N, NE = S["n_instances"], len(X["evaluable"])
    op, pp = S["paired"], X["paired_posthoc_evaluable"]
    dis_o = [i for i, r in X["per_instance"].items() if r["official_baseline_success"] != r["official_workflow_success"]]
    dis_p = [i for i in X["evaluable"]
             if X["per_instance"][i]["baseline_success"] != X["per_instance"][i]["workflow_success"]]
    neither_p = [i for i in X["evaluable"]
                 if not X["per_instance"][i]["baseline_success"] and not X["per_instance"][i]["workflow_success"]]
    unevaluable = [i for i, s in X["source"].items() if s.startswith("unevaluable")]
    gold_bad = [i for i, g in X["gold"].items() if not g["gold_resolved"]]

    md = f"""# Results summary: final-1 (SWT-Bench Verified, unit-test mode, 25 instances)

Single run per arm (no repeated runs), so there are no variance estimates. See Limitations.

## 1. OFFICIAL RESULT (primary): official SWT-Bench harness at be12d4c8

| Metric | Baseline | Workflow |
|---|---|---|
| Success | {pct(B['success'], N)} | {pct(W['success'], N)} |
| Applicability | {pct(B['applicable'], N)} | {pct(W['applicable'], N)} |
| Coverage delta, all | {cov(B['coverage_delta_mean'], B['coverage_delta_n'])} | {cov(W['coverage_delta_mean'], W['coverage_delta_n'])} |
| Coverage delta, successful | {cov(B['coverage_delta_mean_successful'], B['coverage_delta_n_successful'])} | {cov(W['coverage_delta_mean_successful'], W['coverage_delta_n_successful'])} |
| Cost | ${B['cost_usd_fixed_peak']:.4f} | ${W['cost_usd_fixed_peak']:.4f} |
| Model calls | {B['n_calls']} | {W['n_calls']} |
| Avg generation time | {B['avg_generation_seconds']:.1f} s | {W['avg_generation_seconds']:.1f} s |
| Unevaluated (harness image build failed; counted as failure) | {len(B['unevaluated'])} | {len(W['unevaluated'])} |

Paired outcomes (n={N}):
- both succeed: {op['both']};
- baseline only: {op['only_baseline']};
- workflow only: {op['only_workflow']} ({', '.join(dis_o)});
- neither: {op['neither']}.

## 2. POST-HOC SENSITIVITY ANALYSIS (not the official result): patched harness copy, fixes C1-C3

The patch fixes the harness environment, not the predictions. Both arms' predictions were re-evaluated unchanged.
Pre-registered gate: an instance counts only if its own gold patch resolves under the patched harness.
Gold not resolved: {', '.join(gold_bad) if gold_bad else 'none (13/13 resolved)'}.
Still unevaluable (no fix tested): {', '.join(unevaluable)}.

| Metric | Baseline | Workflow |
|---|---|---|
| Success / evaluable | {pct(PB['success'], NE)} | {pct(PW['success'], NE)} |
| Success / 25 | {pct(PB['success'], N)} | {pct(PW['success'], N)} |
| Applicability / evaluable | {pct(PB['applicable'], NE)} | {pct(PW['applicable'], NE)} |
| Coverage delta, all | {cov(PB['cov'], PB['cov_n'])} | {cov(PW['cov'], PW['cov_n'])} |
| Coverage delta, successful | {cov(PB['cov_succ'], PB['cov_succ_n'])} | {cov(PW['cov_succ'], PW['cov_succ_n'])} |

Paired outcomes (n={NE} evaluable):
- both succeed: {pp['both']};
- baseline only: {pp['only_baseline']};
- workflow only: {pp['only_workflow']} ({', '.join(dis_p)});
- neither: {pp['neither']} ({', '.join(neither_p)}).

## 3. Side by side

| | Official: Baseline | Official: Workflow | POST-HOC: Baseline | POST-HOC: Workflow |
|---|---|---|---|---|
| Success | {B['success']}/{N} | {W['success']}/{N} | {PB['success']}/{NE} ({PB['success']}/{N}) | {PW['success']}/{NE} ({PW['success']}/{N}) |
| Coverage delta, all | {cov(B['coverage_delta_mean'], B['coverage_delta_n'])} | {cov(W['coverage_delta_mean'], W['coverage_delta_n'])} | {cov(PB['cov'], PB['cov_n'])} | {cov(PW['cov'], PW['cov_n'])} |
| Workflow-only wins | | {op['only_workflow']} | | {pp['only_workflow']} |

## Limitations
- **Single run:** each arm was run once (final-1), and no second run will be done. The difference between arms is one instance (sympy-15017), which is not statistically distinguishable (exact McNemar test, 1 discordant pair: p = 1.0). LLM sampling is nondeterministic: no seed is sent, and thinking mode uses the API's default temperature.
- **Official numbers depressed by the harness environment:** the post-hoc table is a sensitivity analysis on a patched harness copy, not a replacement for the official result.
- **Wrapper classifier bugs (F1-F4, found post-hoc, not fixed: frozen):** with F1-F4 fixed, 13 of the 14 revised instances would have been classified G5 at round 1, so the revision mechanism was barely tested (see case_studies.md).
- **Six instances could not be evaluated in either arm.**
"""
    (OUT / "results_summary.md").write_text(md)
    shutil.copy2(LATEST / "summary.md", OUT / "official_summary_final-1.md")
    for f in ("per_instance.csv", "leaderboard.csv"):
        shutil.copy2(LATEST / f, OUT / f)
    shutil.copy2(P / "results/final-1/case_studies.md", OUT / "case_studies.md")
    shutil.copy2(POST / "sensitivity_posthoc-c-1.md", OUT / "sensitivity_posthoc-c-1.md")

    rows = {r["instance_id"]: r for r in csv.DictReader(open(LATEST / "per_instance.csv"))}
    parts = ["# Final tests: baseline vs workflow (added lines only)\n",
             "Each block shows the lines the arm's final prediction adds; this is the patch the harness evaluated, unchanged.",
             "The lines are taken from runs/<arm>/final-1/<iid>/harness_input.jsonl.\n"]
    for iid in CASES:
        r = rows[iid]
        parts.append(f"## {iid}\n")
        parts.append("| | Baseline | Workflow |\n|---|---|---|")
        parts.append(f"| Official success | {r['baseline_success']} | {r['workflow_success']} |")
        parts.append(f"| Post-hoc success | {X['per_instance'][iid]['baseline_success']} | {X['per_instance'][iid]['workflow_success']} |")
        parts.append(f"| Coverage delta | {r['baseline_coverage_delta'] or 'N/A'} | {r['workflow_coverage_delta'] or 'N/A'} |")
        parts.append(f"| Model calls | {r['baseline_model_calls']} | {r['workflow_model_calls']} |")
        parts.append(f"| Wrapper groups per round | (none) | {r['workflow_groups'].replace('|', ' → ')} (final round {r['workflow_final_round']}, stop: {r['workflow_stop_reason']}) |\n")
        for arm in ARMS:
            p = json.loads((P / "runs" / arm / "final-1" / iid / "harness_input.jsonl").read_text().splitlines()[0])["model_patch"]
            lines = added_lines(p)
            parts.append(f"### {arm.capitalize()} ({len([l for l in lines if not l.startswith('# file:')])} added lines)\n")
            parts.append("```python\n" + "\n".join(lines) + "\n```\n")
    (OUT / "final_tests_side_by_side.md").write_text("\n".join(parts))
    print("\n".join(sorted(str(p.relative_to(OUT)) for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
