"""Post-hoc, offline: re-run the wrapper's own classify() on saved wrapper outputs, original vs ANSI-stripped output.
Reads only saved wrapper_test/result.json + test_output.txt and the issue text (wrapper's own loader). No harness data."""
import importlib.util, json, re, sys
from pathlib import Path
P = Path.home() / "se443/project"
spec = importlib.util.spec_from_file_location("wf", P / "scripts/run_workflow.py"); wf = importlib.util.module_from_spec(spec); spec.loader.exec_module(wf)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
rows = []
for d in sorted((P / "runs/workflow/final-1").iterdir()):
    if not d.is_dir() or not (d / "done.json").exists(): continue
    inst = wf.load_instance(d.name)
    for rd in sorted(d.glob("round_*")):
        r = rd / "wrapper_test/result.json"
        if not r.exists(): continue
        res = json.loads(r.read_text()); out = (rd / "wrapper_test/test_output.txt").read_text()
        rule4 = (res["rule4"]["valid"], res["rule4"]["reason"], res["rule4"]["files"])
        args = (inst["problem_statement"], res["apply_ok"], "", rule4, res.get("targets"), res.get("selection_mode"), res.get("timed_out"))
        g0, e0 = wf.classify(*args, out, res.get("statuses") or {})
        g1, e1 = wf.classify(*args, ANSI.sub("", out), res.get("statuses") or {})
        rows.append({"iid": d.name, "round": rd.name, "saved": res["group"], "recomputed": g0, "ansi_stripped": g1,
                     "types_saved": e0.get("failure_types"), "types_stripped": e1.get("failure_types"),
                     "statuses": res.get("statuses"), "reason_stripped": e1.get("reason"), "has_ansi": bool(ANSI.search(out))})
json.dump(rows, open(sys.argv[1], "w"), indent=1)
for x in rows:
    flag = "" if x["saved"] == x["ansi_stripped"] else "  <-- CHANGES"
    print(f'{x["iid"]:30} {x["round"]} saved={x["saved"]} recomputed={x["recomputed"]} ansi_stripped={x["ansi_stripped"]} ansi={x["has_ansi"]}{flag}')
