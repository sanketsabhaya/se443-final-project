"""Post-hoc counterfactual: wrapper's own classify() on saved outputs with input-side fixes only:
 F1 strip ANSI; F2 sympy 1.2 two-line block header; F3 pytest single-underscore headers (long ids);
 F4 parametrized targets: a target counts as FAILED if any of its parametrizations failed."""
import importlib.util, json, re, sys
from pathlib import Path
P = Path.home() / "se443/project"
spec = importlib.util.spec_from_file_location("wf", P / "scripts/run_workflow.py"); wf = importlib.util.module_from_spec(spec); spec.loader.exec_module(wf)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
def fix_output(out):
    out = ANSI.sub("", out)
    out = re.sub(r"(?m)^_{20,}\n (\S+:\S+) *$", r"_____ \1 _____", out)          # F2
    out = re.sub(r"(?m)^_{1,2} (.+) _{1,2}$", r"___ \1 ___", out)                 # F3
    return out
def fix_statuses(st, targets):
    if not targets: return st
    fail = {k: v for k, v in st.items() if v in ("FAILED", "ERROR") and any(wf.key_matches(k, t) for t in targets)}
    return {**fail, **{k: v for k, v in st.items() if k not in fail}}             # F4: failing params first
summary = {}
for d in sorted((P / "runs/workflow/final-1").iterdir()):
    if not d.is_dir() or not (d / "done.json").exists(): continue
    inst = wf.load_instance(d.name); seq_saved, seq_fix = [], []
    for rd in sorted(d.glob("round_*")):
        r = rd / "wrapper_test/result.json"
        if not r.exists(): continue
        res = json.loads(r.read_text()); out = (rd / "wrapper_test/test_output.txt").read_text()
        rule4 = (res["rule4"]["valid"], res["rule4"]["reason"], res["rule4"]["files"])
        a = (inst["problem_statement"], res["apply_ok"], "", rule4, res.get("targets"), res.get("selection_mode"), res.get("timed_out"))
        g, ev = wf.classify(*a, fix_output(out), fix_statuses(res.get("statuses") or {}, res.get("targets")))
        seq_saved.append(res["group"]); seq_fix.append(g)
    stop = next((i + 1 for i, g in enumerate(seq_fix) if g == "G5"), None)
    summary[d.name] = {"saved": seq_saved, "fixed": seq_fix, "fixed_would_stop_after_round": stop}
    if seq_saved != seq_fix:
        print(f"{d.name:30} saved={'|'.join(seq_saved):12} fixed={'|'.join(seq_fix):12} -> with fixes, final candidate = round {stop or len(seq_fix)}")
json.dump(summary, open(sys.argv[1], "w"), indent=1)
