#!/usr/bin/env python3
"""EXPERIMENTAL WORKFLOW arm: mini-SWE-agent + DeepSeek-Flash + execution-feedback wrapper.

Design: docs/workflow-design.md. One instance per invocation.
Usage (via scripts/run_workflow.sh):
    run_workflow.py <run_id> <instance_id>
Outputs: runs/workflow/<run_id>/<instance_id>/

Information boundary (CLAUDE.md rule 3): this script reads ONLY instance_id, problem_statement,
repo, version from the dataset (column projection: other columns are never loaded), the agent's
own patches, and the output of running those patches' tests on the buggy code. It never reads
patch / test_patch / FAIL_TO_PASS / PASS_TO_PASS or any harness result.
"""
import base64
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq

# Harness code, used read-only for GENERIC per-repo specs (no instance data, no results).
from src.constants import MAP_REPO_TO_TEST_FRAMEWORK_VERBOSE, MAP_VERSION_TO_INSTALL, TestStatus  # noqa: E402
from src.log_parsers import MAP_REPO_TO_PARSER  # noqa: E402
from src.utils import get_test_directives  # noqa: E402

HOME = Path.home()
PROJECT = HOME / "se443/project"
MINI = HOME / "se443/mini-swe-agent"
CONFIG = PROJECT / "configs/unit_test_gen.yaml"
DATASET = HOME / ".cache/huggingface/hub/datasets--princeton-nlp--SWE-bench_Verified/snapshots/c104f840cc67f8b6eec6f759ebc8b2693d585d4a"
sys.path.insert(0, str(PROJECT / "scripts"))
from check_test_only import classify as rule4_classify, is_test_file  # noqa: E402

STEP_BUDGET = 100
TIME_BUDGET = 1800
MAX_REVISIONS = 2
MIN_SECS_FOR_ROUND = 60
WRAPPER_TEST_TIMEOUT_CAP = 900
OUTPUT_TAIL_LINES, OUTPUT_TAIL_CHARS = 150, 8000
STARTUP_CMD = "cd /testbed && echo {{prev_patch_b64}} | base64 -d | git apply"
MAX_B64_FOR_STARTUP = 100_000  # stay well under the kernel's per-argument limit

ISSUE_EXC_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning))\b")
SETUP_MARKERS = [
    r"SyntaxError", r"IndentationError", r"ImportError", r"ModuleNotFoundError",
    r"ERROR collecting", r"errors during collection", r"fixture '[^']+' not found",
    r"Failed to import test module", r"INTERNALERROR", r"no tests ran", r"Ran 0 tests",
]
EXC_LINE_RE = re.compile(r"^(?:E\s+)?([A-Za-z_][\w\.]*?(?:Error|Exception|Warning|Exit|Interrupt))(?::|\s|$)")

GROUPS = {
    "G1": "The patch could not be applied.",
    "G2": "The tests could not run (setup error).",
    "G3": "All of your tests PASS on the current, unfixed code.",
    "G4": "Your tests fail, but not in a way related to the issue.",
    "G5": "Your tests fail in a way that matches the issue.",
}


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def log(msg, fh):
    line = f"[{now_iso()}] {msg}"
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


def write_json(path, obj):
    path = Path(path)
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    path.write_text(json.dumps(obj, indent=2))


# ---------------------------------------------------------------- dataset (column projection)
def load_instance(iid):
    files = sorted((DATASET / "data").glob("test-*.parquet"))
    table = pq.read_table(files[0], columns=["instance_id", "problem_statement", "repo", "version"])
    for row in table.to_pylist():
        if row["instance_id"] == iid:
            return row
    raise SystemExit(f"instance {iid} not in dataset")


def image_name(iid):
    return f"docker.io/swebench/sweb.eval.x86_64.{iid.replace('__', '_1776_')}:latest".lower()


# ---------------------------------------------------------------- docker helpers
def sh(cmd, timeout=None, input_=None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input_)
    return p.returncode, p.stdout + p.stderr


def docker_exec(cid, script, timeout):
    """Run a bash script in the container. Returns (rc, output, timed_out)."""
    try:
        rc, out = sh(["docker", "exec", "-i", cid, "bash", "-s"], timeout=timeout, input_=script)
        return rc, out, False
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode(errors="replace")
        return -9, out, True


ENV_PREFIX = "source /opt/miniconda3/bin/activate\nconda activate testbed\ncd /testbed\n"


# ---------------------------------------------------------------- test selection
def added_lines_by_file(patch):
    """{path: set(new-file line numbers added by the patch)} from unified diff hunks."""
    result, cur, new_ln = {}, None, 0
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            cur = None
        elif line.startswith("+++ "):
            path = line[4:].strip()
            cur = None if path == "/dev/null" else path[2:] if path.startswith("b/") else path
            if cur:
                result.setdefault(cur, set())
        elif line.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            new_ln = int(m.group(1)) if m else 0
        elif cur is not None and new_ln:
            if line.startswith("+"):
                result[cur].add(new_ln)
                new_ln += 1
            elif line.startswith("-"):
                pass
            elif line.startswith("\\"):
                pass
            else:
                new_ln += 1
    return result


def changed_test_functions(source, added):
    """[(class_path or None, func)] for test functions whose span overlaps added lines."""
    import ast
    out = []

    def visit(node, classes):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, classes + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name.startswith("test"):
                    start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                    end = getattr(child, "end_lineno", child.lineno)
                    if any(start <= ln <= end for ln in added):
                        out.append((".".join(classes) or None, child.name))
    visit(ast.parse(source), [])
    return out


def build_targets(repo, patch, cid):
    """Returns (targets, args, mode). targets: list of dicts {file, cls, func, label}."""
    added = added_lines_by_file(patch)
    py_test_files = [f for f in added if f.endswith(".py") and is_test_file(f)]
    targets = []
    for f in py_test_files:
        rc, src, _ = docker_exec(cid, f"cat /testbed/{f}\n", timeout=60)
        if rc != 0:
            continue
        try:
            funcs = changed_test_functions(src, added[f])
        except SyntaxError:
            funcs = []  # let the test run surface the SyntaxError (-> G2)
        for cls, func in funcs:
            if repo == "django/django":
                mod = f[:-3]
                mod = mod[len("tests/"):] if mod.startswith("tests/") else mod
                label = ".".join([mod.replace("/", ".")] + ([cls] if cls else []) + [func])
            else:
                label = "::".join([f] + (cls.split(".") if cls else []) + [func])
            targets.append({"file": f, "cls": cls, "func": func, "label": label})
    if targets and repo != "sympy/sympy":
        return targets, [t["label"] for t in targets], "functions"
    # Fallback (no changed test functions found, or sympy whose runner takes files): whole changed files.
    files_args = get_test_directives(patch, repo)  # pure function of the AGENT's patch
    if targets:  # sympy: run files, but still match results by function name
        return targets, files_args, "files(sympy)"
    return [], files_args, "files(fallback)"


def key_matches(key, t):
    if "::" in key:
        parts = key.split("::")
        base = parts[-1].split("[")[0]
        path = parts[0]
        file_ok = path == t["file"] or path.endswith(t["file"]) or t["file"].endswith(path)
        cls_ok = t["cls"] is None or all(c in parts[1:-1] for c in t["cls"].split("."))
        return base == t["func"] and file_ok and cls_ok
    m = re.match(r"^(\S+) \((.*)\)$", key)
    if m:
        name, ctx = m.groups()
        cls_ok = t["cls"] is None or (f".{t['cls'].split('.')[-1]}." in f".{ctx}.")
        return name == t["func"] and cls_ok
    return key == t["func"] or key == t["func"][len("test_"):] or key.endswith(t["func"])


# ---------------------------------------------------------------- failure types
PYTEST_LOCATION_RE = re.compile(r"^\S+:\d+: ([A-Za-z_][\w\.]*)$")  # pytest long-tb last line: "path.py:950: AssertionError"


def exc_from_text(text):
    text = text.strip()
    if not text:
        return None
    m = PYTEST_LOCATION_RE.match(text)
    if m:
        return m.group(1).split(".")[-1]
    body = re.sub(r"^E\s+", "", text)  # pytest prefixes exception/assert lines with "E   "
    if "DID NOT RAISE" in body or body.startswith("assert ") or body.startswith("AssertionError"):
        return "AssertionError"
    m = EXC_LINE_RE.match(text)
    return m.group(1).split(".")[-1] if m else None


def failure_types(output):
    """{test key or block header: exception type} from pytest summaries, unittest blocks, '____' blocks."""
    types = {}
    lines = output.splitlines()
    for ln in lines:  # pytest -rA short summary
        m = re.match(r"^(FAILED|ERROR) (\S+)(?: - (.+))?$", ln)
        if m and m.group(3):
            t = exc_from_text(m.group(3))
            if t:
                types[m.group(2)] = t
    i = 0
    while i < len(lines):  # unittest/django FAIL:/ERROR: blocks and pytest/sympy '____ name ____' blocks
        ln = lines[i]
        m = re.match(r"^(FAIL|ERROR): (\S+ \([^)]*\))", ln)
        h = re.match(r"^_{3,} (.+?) _{3,}$", ln)
        if m or h:
            key = m.group(2) if m else h.group(1)
            last = None
            j = i + 1
            while j < len(lines) and not re.match(r"^(={20,}|_{3,} .+ _{3,}$|Ran \d+ tests?)", lines[j]):
                t = exc_from_text(lines[j])
                if t:
                    last = t
                j += 1
            if m and m.group(1) == "FAIL":
                last = "AssertionError"
            if last and key not in types:
                types[key] = last
            i = j
            continue
        i += 1
    return types


def type_for_target(t, types):
    for key, typ in types.items():
        if key_matches(key, t) or (t["func"] and re.search(rf"\b{re.escape(t['func'])}\b", key)):
            return typ
    return None


# ---------------------------------------------------------------- classification (fixed rules)
def classify(issue_text, apply_ok, apply_out, rule4, targets, mode, timed_out, output, statuses):
    issue_exc = set(ISSUE_EXC_RE.findall(issue_text))
    ev = {"issue_exc": sorted(issue_exc), "mode": mode}
    valid, reason, files = rule4
    if not valid:
        ev["reason"] = reason
        ev["non_test_files"] = [f for f in files if not is_test_file(f)]
        return "G1", ev
    if not apply_ok:
        ev["reason"] = "git_apply_failed"
        return "G1", ev
    if timed_out:
        ev["reason"] = "timeout"
        return "G2", ev
    if targets:
        collected = {}
        for t in targets:
            for k, s in statuses.items():
                if key_matches(k, t):
                    collected[t["label"]] = (s, t)
                    break
    else:  # file-level fallback: every parsed test came from the agent's changed files
        collected = {k: (s, {"file": None, "cls": None, "func": k, "label": k}) for k, s in statuses.items()}
    ev["collected"] = {k: v[0] for k, v in collected.items()}
    if mode == "files(fallback)" and not statuses:
        ev["reason"] = "no_targets_or_not_collected"
        return "G2", ev
    if targets is not None and not collected:
        ev["reason"] = "targets_not_collected"
        return "G2", ev
    markers = []
    for pat in SETUP_MARKERS:
        mm = re.search(pat, output)
        if mm and mm.group(0) not in issue_exc:
            markers.append(mm.group(0))
    ev["setup_markers"] = markers
    failing = {k: v for k, v in collected.items() if v[0] in (TestStatus.FAILED.value, TestStatus.ERROR.value)}
    if markers and not any(v[0] == TestStatus.FAILED.value for v in collected.values()):
        ev["reason"] = "setup_marker_and_no_FAILED_target"
        return "G2", ev
    if not failing:
        ev["reason"] = "no_target_failed"
        return "G3", ev
    types = failure_types(output)
    ftypes = {k: type_for_target(v[1], types) for k, v in failing.items()}
    ev["failure_types"] = ftypes
    if any(ty == "AssertionError" or (ty and ty in issue_exc) for ty in ftypes.values()):
        ev["reason"] = "failure_matches_issue"
        return "G5", ev
    ev["reason"] = "failure_unrelated"
    return "G4", ev


def informational_flags(patch):
    added = "\n".join(l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++"))
    return {
        "no_assertion_in_added_lines": not re.search(r"\bassert|\braises\b|assert[A-Z]\w*\(", added),
        "skip_or_xfail_added": bool(re.search(r"skip|xfail|expectedFailure", added)),
    }


# ---------------------------------------------------------------- wrapper test run
def wrapper_test(inst, patch, timeout_s, out_dir):
    out_dir.mkdir(parents=True)
    repo, version = inst["repo"], inst["version"]
    res = {"start": now_iso(), "timeout_s": timeout_s}
    rule4 = rule4_classify(patch)
    res["rule4"] = {"valid": rule4[0], "reason": rule4[1], "files": rule4[2]}
    t0 = time.time()
    apply_ok, apply_out, targets, args, mode, cmd, rc, output, timed_out, statuses = (
        False, "", None, [], None, None, None, "", False, {})
    if rule4[0]:
        rc_run, cid_out = sh(["docker", "run", "-d", "--rm", image_name(inst["instance_id"]), "sleep", "infinity"])
        cid = cid_out.strip().splitlines()[-1] if rc_run == 0 else None
        if cid is None:
            raise RuntimeError(f"could not start container: {cid_out}")
        try:
            (out_dir / "agent.patch").write_text(patch)
            sh(["docker", "cp", str(out_dir / "agent.patch"), f"{cid}:/tmp/agent.patch"])
            arc, apply_out, _ = docker_exec(cid, ENV_PREFIX + "git apply -v /tmp/agent.patch\n", timeout=120)
            apply_ok = arc == 0
            if apply_ok:
                targets, args, mode = build_targets(repo, patch, cid)
                spec = MAP_VERSION_TO_INSTALL[repo][version]
                eval_cmds = "\n".join(spec.get("eval_commands", []))
                cmd = " ".join([MAP_REPO_TO_TEST_FRAMEWORK_VERBOSE[repo][version], *args])
                left = max(1, int(timeout_s - (time.time() - t0)))
                rc, output, timed_out = docker_exec(cid, ENV_PREFIX + eval_cmds + "\n" + cmd + "\n", timeout=left)
                statuses = MAP_REPO_TO_PARSER[repo](output)
        finally:
            sh(["docker", "rm", "-f", cid])
    group, ev = classify(inst["problem_statement"], apply_ok, apply_out, rule4, targets, mode, timed_out, output, statuses)
    res.update({
        "end": now_iso(), "duration_s": round(time.time() - t0, 1), "apply_ok": apply_ok,
        "selection_mode": mode, "targets": targets, "command": cmd, "exit_code": rc, "timed_out": timed_out,
        "statuses": statuses, "group": group, "evidence": ev, "flags": informational_flags(patch or ""),
    })
    (out_dir / "apply_output.txt").write_text(apply_out)
    (out_dir / "test_output.txt").write_text(output)
    write_json(out_dir / "result.json", res)
    return res


# ---------------------------------------------------------------- feedback
def feedback_text(k, res, patch):
    g = res["group"]
    ev = res["evidence"]
    if g == "G1":
        if ev.get("reason") in ("missing", "empty"):
            expl = "No test patch was submitted."
        elif ev.get("reason") == "non_test_files":
            expl = f"The patch modifies non-test files: {', '.join(ev['non_test_files'])}. Only test files may be changed."
        elif ev.get("reason") == "no_diff_headers":
            expl = "The submitted text is not a valid git patch (no 'diff --git' headers)."
        else:
            expl = f"`git apply` reported:\n{res_tail(res.get('_apply_out', ''), 40)}"
    elif g == "G2":
        expl = ("The test run stopped before your tests could execute, e.g. because of a syntax error, a failed import, "
                "a test that could not be collected, or a missing fixture (see output). Fix the test code so it runs.")
    elif g == "G3":
        expl = ("A test that passes on the unfixed code does not reproduce the issue. Change it so that it fails because "
                "of the problem described in the issue and would pass once the issue is fixed.")
    else:  # G4
        types = sorted({t for t in ev.get("failure_types", {}).values() if t}) or ["unknown error"]
        expl = (f"The failure ({', '.join(types)}) does not look like the problem described in the issue. Fix the test so "
                "that it fails because of the behavior the issue describes, not because of a mistake in the test.")
    per_test = []
    for label, status in (ev.get("collected") or {}).items():
        ty = (ev.get("failure_types") or {}).get(label)
        per_test.append(f"{label}: {status}" + (f" ({ty})" if ty else ""))
    for t in res.get("targets") or []:
        if t["label"] not in (ev.get("collected") or {}):
            per_test.append(f"{t['label']}: NOT RUN / NOT FOUND")
    pre_applied = res.get("_pre_applied", False)
    patch_state = ("This patch is already applied in /testbed. Edit the test files in place, then submit as instructed."
                   if pre_applied else
                   "This patch is NOT applied in /testbed. Recreate your test changes in the test files, then submit as instructed.")
    output = res.get("_output", "")
    tail_lines = output.splitlines()[-OUTPUT_TAIL_LINES:]
    tail = "\n".join(tail_lines)[-OUTPUT_TAIL_CHARS:]
    return f"""

---
FEEDBACK FROM AN AUTOMATED TEST RUN (revision {k} of at most {MAX_REVISIONS})

A previous attempt at this task produced the test patch shown below. We applied it to the current,
unfixed code in a fresh copy of the repository and ran only the tests it adds or changes.

Command: {res.get('command') or '(tests were not run)'}
Result: {GROUPS[g]}
{expl}

Per-test results:
{chr(10).join(per_test) if per_test else '(none)'}

Test output (last {len(tail_lines)} lines):
<test_output>
{tail}
</test_output>

Previous test patch:
<previous_patch>
{patch or '(empty)'}
</previous_patch>
{patch_state}

Please revise the test. It must still check the behavior described in the issue with meaningful
assertions: do not delete or weaken assertions, and do not skip, xfail or otherwise disable the test
just to change its outcome. As before, change test files only and do not fix the issue.
"""


def res_tail(text, n):
    return "\n".join(text.splitlines()[-n:])


# ---------------------------------------------------------------- mini rounds
def run_mini(round_dir, subset, overrides, hard_timeout, logfh):
    out = round_dir / "mini"
    cmd = ["uv", "run", "--frozen", "--project", str(MINI), "mini-extra", "swebench",
           "--subset", str(subset), "--split", "test", "--filter", f"^{IID}$", "-c", str(CONFIG)]
    for o in overrides:
        cmd += ["-c", o]
    cmd += ["-w", "1", "-o", str(out)]
    env = dict(os.environ, HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1")
    (round_dir / "mini_command.json").write_text(json.dumps(cmd, indent=1))
    t0 = time.time()
    killed = False
    with open(round_dir / "mini_stdout.log", "w") as so:
        p = subprocess.Popen(cmd, stdout=so, stderr=subprocess.STDOUT, env=env)
        try:
            rc = p.wait(timeout=hard_timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            rc = p.wait()
            killed = True
            log(f"mini killed by wrapper hard timeout ({hard_timeout}s)", logfh)
            # mini's container (sleep 2h) would outlive the killed process; remove it.
            ids = sh(["docker", "ps", "-q", "--filter", "name=minisweagent-",
                      "--filter", f"ancestor={image_name(IID)}"])[1].split()
            for c in ids:
                sh(["docker", "rm", "-f", c])
            log(f"removed orphaned mini containers: {ids}", logfh)
    dur = time.time() - t0
    traj = out / IID / f"{IID}.traj.json"
    steps, exit_status = 0, None
    if traj.exists():
        t = json.loads(traj.read_text())
        steps = t["info"].get("model_stats", {}).get("api_calls", 0)
        exit_status = t["info"].get("exit_status")
    patch = None
    if (out / "preds.json").exists():
        patch = json.loads((out / "preds.json").read_text()).get(IID, {}).get("model_patch")
    return {"rc": rc, "killed_by_wrapper": killed, "duration_s": round(dur, 1), "steps": steps,
            "exit_status": exit_status, "patch_chars": len(patch or ""), "_patch": patch}


def main():
    global IID
    run_id, IID = sys.argv[1], sys.argv[2]
    root = PROJECT / "runs/workflow" / run_id / IID
    if root.exists():
        raise SystemExit(f"{root} exists; refusing to overwrite")
    root.mkdir(parents=True)
    logfh = open(root / "workflow.log", "a")
    inst = load_instance(IID)
    img = image_name(IID)
    cfg_sha = sh(["sha256sum", str(CONFIG)])[1].split()[0]
    meta = [f"arm: workflow", f"run_id: {run_id}", f"instance_id: {IID}",
            f"mini_swe_agent_commit: {sh(['git', '-C', str(MINI), 'rev-parse', 'HEAD'])[1].strip()}",
            f"config: {CONFIG} sha256={cfg_sha}", f"dataset: {DATASET}", f"image: {img}",
            "model_name: deepseek/deepseek-flash (from config, unchanged)",
            "temperature: not sent -> DeepSeek API default 1.0 (no effect in thinking mode, which is the default)",
            "seed: not sent (DeepSeek chat API has no seed parameter)",
            f"budget: {STEP_BUDGET} steps (model calls + 1 per wrapper check), {TIME_BUDGET} s wall from round-1 start",
            f"max_revisions: {MAX_REVISIONS}"]
    (root / "config_used.yaml").write_text(CONFIG.read_text())
    log(f"pulling {img}", logfh)
    meta.append(f"pull_start: {now_iso()}")
    prc, pout = sh(["docker", "pull", "-q", img])
    (root / "docker_pull.log").write_text(pout)
    if prc != 0:
        raise SystemExit(f"docker pull failed: {pout}")
    meta.append(f"pull_end: {now_iso()}")
    meta.append("image_digest: " + sh(["docker", "image", "inspect", "--format", "{{index .RepoDigests 0}}", img])[1].strip())

    T0 = time.time()
    meta.append(f"start: {now_iso()}")
    steps_used = 0
    rounds = []
    budget = {"ledger": []}
    k = 1
    subset, overrides, pre_applied = DATASET, [], False
    while True:
        rdir = root / f"round_{k}"
        rdir.mkdir(exist_ok=(k > 1))  # rounds >1 were created early to hold their dataset file
        secs_left = TIME_BUDGET - (time.time() - T0)
        log(f"round {k}: start mini (steps_left={STEP_BUDGET - steps_used}, secs_left={int(secs_left)}, overrides={[o[:60] for o in overrides]})", logfh)
        m = run_mini(rdir, subset, overrides, hard_timeout=max(60, int(secs_left)) + 300, logfh=logfh)
        patch = m.pop("_patch")
        steps_used += m["steps"]
        budget["ledger"].append({"round": k, "kind": "agent", "steps": m["steps"], "seconds": m["duration_s"]})
        log(f"round {k}: mini done exit_status={m['exit_status']} steps={m['steps']} dur={m['duration_s']}s patch_chars={m['patch_chars']}", logfh)

        steps_left = STEP_BUDGET - steps_used
        secs_left = TIME_BUDGET - (time.time() - T0)
        can_revise_after = k - 1 < MAX_REVISIONS
        # Wrapper check: full test run if budget allows (1 step); otherwise apply-check only, no step charged.
        if steps_left >= 1 and secs_left > 0:
            res = wrapper_test(inst, patch, min(secs_left, WRAPPER_TEST_TIMEOUT_CAP), rdir / "wrapper_test")
            steps_used += 1
            budget["ledger"].append({"round": k, "kind": "wrapper_test", "steps": 1, "seconds": res["duration_s"]})
            charged = True
        else:
            res = apply_check_only(inst, patch, rdir / "wrapper_test")
            budget["ledger"].append({"round": k, "kind": "apply_check_only", "steps": 0, "seconds": res["duration_s"]})
            charged = False
        log(f"round {k}: wrapper check group={res['group']} reason={res['evidence'].get('reason')} apply_ok={res['apply_ok']} charged_step={charged} dur={res['duration_s']}s", logfh)
        rounds.append({"round": k, "agent": m, "check": {kk: res[kk] for kk in ("group", "apply_ok", "duration_s", "selection_mode", "command", "timed_out")},
                       "pre_applied_previous_patch": pre_applied, "overrides": overrides, "patch": patch})

        steps_left = STEP_BUDGET - steps_used
        secs_left = TIME_BUDGET - (time.time() - T0)
        if res["group"] == "G5":
            stop = "G5"
        elif not can_revise_after:
            stop = "max_revisions"
        elif steps_left < 1 or secs_left < MIN_SECS_FOR_ROUND:
            stop = "budget_exhausted"
        else:
            stop = None
        if stop:
            log(f"stop after round {k}: {stop}", logfh)
            break

        # Next round: feedback through a per-round dataset file (only these 3 fields exist in it).
        res["_output"] = (rdir / "wrapper_test/test_output.txt").read_text()
        res["_apply_out"] = (rdir / "wrapper_test/apply_output.txt").read_text()
        b64 = base64.b64encode((patch or "").encode()).decode()
        pre_applied = res["group"] in ("G2", "G3", "G4") and res["apply_ok"] and len(b64) <= MAX_B64_FOR_STARTUP
        res["_pre_applied"] = pre_applied
        fb = feedback_text(k, res, patch)
        nxt = root / f"round_{k + 1}"
        (nxt / "dataset/data").mkdir(parents=True)
        (rdir / "feedback_to_next_round.txt").write_text(fb)
        with open(nxt / "dataset/data/test.jsonl", "w") as fh:
            fh.write(json.dumps({"instance_id": IID, "problem_statement": inst["problem_statement"] + fb,
                                 "prev_patch_b64": b64 if pre_applied else ""}) + "\n")
        subset = nxt / "dataset"
        overrides = [f"agent.step_limit={steps_left}", f"agent.wall_time_limit_seconds={int(secs_left)}"]
        if pre_applied:
            overrides.append(f"run.env_startup_command={STARTUP_CMD}")
        k += 1

    end = time.time()
    applying = [r for r in rounds if r["check"]["apply_ok"]]
    final = applying[-1] if applying else None
    final_info = {
        "final_round": final["round"] if final else None,
        "reason": "latest round whose patch applied in the wrapper check" if final else "no round produced an applying patch",
        "stop_reason": stop, "rounds": len(rounds), "revisions": len(rounds) - 1,
        "groups": [r["check"]["group"] for r in rounds],
        "steps_used": steps_used, "wall_s": round(end - T0, 1),
    }
    write_json(root / "final.json", final_info)
    write_json(root / "budget.json", {**budget, "steps_used": steps_used, "wall_s": round(end - T0, 1),
                                      "step_budget": STEP_BUDGET, "time_budget_s": TIME_BUDGET})
    write_json(root / "rounds.json", [{kk: v for kk, v in r.items() if kk != "patch"} for r in rounds])
    write_json(root / "final_preds.json", {IID: {"instance_id": IID, "model_name_or_path": "deepseek/deepseek-flash",
                                                  "model_patch": final["patch"] if final else None}})
    meta += [f"end: {now_iso()}", f"wall_s: {round(end - T0, 1)}", f"steps_used: {steps_used}",
             f"rounds: {len(rounds)}", f"groups: {final_info['groups']}", f"final_round: {final_info['final_round']}"]
    (root / "run_meta.txt").write_text("\n".join(meta) + "\n")
    write_json(root / "done.json", {"arm": "workflow", "run_id": run_id, "instance_id": IID, "finished": now_iso(),
                                    "final_round": final_info["final_round"], "stop_reason": stop})
    log("done", logfh)


def apply_check_only(inst, patch, out_dir):
    """Applicability only (no test run, no step charged): used when no budget is left."""
    out_dir.mkdir(parents=True)
    t0 = time.time()
    rule4 = rule4_classify(patch)
    apply_ok, apply_out = False, ""
    if rule4[0]:
        rc_run, cid_out = sh(["docker", "run", "-d", "--rm", image_name(inst["instance_id"]), "sleep", "infinity"])
        cid = cid_out.strip().splitlines()[-1]
        try:
            (out_dir / "agent.patch").write_text(patch)
            sh(["docker", "cp", str(out_dir / "agent.patch"), f"{cid}:/tmp/agent.patch"])
            arc, apply_out, _ = docker_exec(cid, ENV_PREFIX + "git apply --check -v /tmp/agent.patch\n", timeout=120)
            apply_ok = arc == 0
        finally:
            sh(["docker", "rm", "-f", cid])
    group = "G1" if not apply_ok else "UNTESTED"
    res = {"start": None, "end": now_iso(), "duration_s": round(time.time() - t0, 1), "apply_ok": apply_ok,
           "rule4": {"valid": rule4[0], "reason": rule4[1], "files": rule4[2]}, "group": group,
           "evidence": {"reason": "apply_check_only (no budget left)"}, "selection_mode": None, "command": None,
           "timed_out": False}
    (out_dir / "apply_output.txt").write_text(apply_out)
    (out_dir / "test_output.txt").write_text("")
    write_json(out_dir / "result.json", res)
    return res


if __name__ == "__main__":
    main()
