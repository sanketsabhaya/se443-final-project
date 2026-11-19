# Experimental workflow wrapper — design (DRAFT, not built)

Status: APPROVED 2026-11-13 with user decisions (G1 includes non-test/empty patches; each wrapper check = 1 step;
previous patch pre-applied via -c overrides; harness per instance). Implemented in scripts/run_workflow.py,
scripts/run_experiment.py. Section 10 lists implementation details that refine the design.

## 1. What the wrapper does

```
round 1: agent (frozen config, issue only) ──► patch P1
           │
           ▼
   wrapper test run of P1 on BUGGY code (fresh container) ──► classify G1..G5
           │ G5 → stop                    │ G1-G4 and budget left
           ▼                              ▼
   final = latest applying patch    round 2: agent (same frozen config,
                                     task = issue + feedback) ──► P2 ──► test ──► classify
                                                                       │ G1-G4 and budget left
                                                                       ▼
                                                              round 3 (revision 2) ──► P3 ──► test ──► classify
                                                                       ▼
                                                              stop (max 2 revisions)
```

- Agent: the same `uv run --project ~/se443/mini-swe-agent mini-extra swebench` command and the same
  `configs/unit_test_gen.yaml` (sha256 eb3e1ccd…) as the baseline. The config file is never changed.
- Inputs the wrapper may use: issue text (`problem_statement`), the generic `repo`/`version` fields
  (to select the generic test command and log parser), the agent's own patch, and the output of
  running that patch's tests on the buggy code. **Never used:** `patch`, `test_patch`, `FAIL_TO_PASS`,
  `PASS_TO_PASS`, harness results or logs, instructor labels.

## 2. Wrapper test run (agent patch on buggy code)

1. Fresh container from the same image the agent used
   (`docker.io/swebench/sweb.eval.x86_64.<id>:latest`; repo at `base_commit` = buggy code, conda env `testbed`).
   It is not the agent's container, so anything the agent installed or changed there is gone.
2. `source /opt/miniconda3/bin/activate && conda activate testbed && cd /testbed`, then the repo/version's
   generic `eval_commands` from the harness specs (`MAP_VERSION_TO_INSTALL[repo][version]`, e.g. locale
   settings for django), if any. The harness's `install` step is skipped: the image already has the repo
   installed and only test files change.
3. `git apply -v` the agent's patch → failure = G1.
4. **Select tests from the agent's patch only:**
   - Files: `get_test_directives(agent_patch, repo)` from the harness, which is a pure function of the
     patch string it is given. It is never given `test_patch`.
   - Narrow to the agent's new or changed test functions: a small script in the container parses each
     changed file with `ast` and keeps the test functions/methods whose line range overlaps the
     patch's added lines (from the `@@ +start,len @@` hunk headers). It emits
     `module.Class.method` for django and `path::Class::func` for pytest.
     If none can be found, it falls back to the whole changed files.
5. Test command: `MAP_REPO_TO_TEST_FRAMEWORK_VERBOSE[repo][version]` (pytest `--tb=long`, django
   runtests `--verbosity 2`) + selected tests. No coverage tracing.
   Timeout = min(remaining wall budget, 900 s).
6. Parse with the harness's `MAP_REPO_TO_PARSER[repo]` → per-test status (PASSED/FAILED/ERROR/SKIPPED/XFAIL).
7. Save the command, exit code, duration, raw output, parsed statuses, target test IDs and classification
   evidence in `round_k/wrapper_test/`.

## 3. Classification rules (fixed, applied in this order; first match wins)

Definitions
- `targets` = test IDs selected in step 4. `collected` = targets that appear in the parser output.
- `issue_exc` = set of names matched by `\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning))\b` in the issue text.
- `SETUP_MARKERS` (regex, on raw output): `SyntaxError`, `IndentationError`, `ImportError`,
  `ModuleNotFoundError`, `ERROR collecting`, `errors during collection`, `fixture '[^']+' not found`,
  `Failed to import test module`, `INTERNALERROR`, `no tests ran`, `Ran 0 tests`.
  (NameError was dropped during implementation: a NameError in a test body is a test bug, so it falls under G4.)
  A marker whose exception name is in `issue_exc` does not count (the bug itself may be an ImportError).
- Failure type of a FAILED/ERROR target: the last exception line in that test's failure section
  (pytest `____ name ____` block; unittest `FAIL:`/`ERROR:` block), e.g. `E   ValueError: …` → `ValueError`.
  unittest `FAIL:` → `AssertionError`; pytest `Failed: DID NOT RAISE` → `AssertionError`.

| # | Group | Rule |
|---|---|---|
| G1 | patch does not apply | patch missing/empty, OR `git apply` fails, OR patch touches non-test files (rule-4 check, same function as `check_test_only.py`) *(last condition: needs user decision)* |
| G2 | setup error | no targets identified; OR test run timed out/killed; OR `collected` is empty; OR a SETUP_MARKER matched and no target has status FAILED |
| G3 | all tests pass on buggy code | no collected target is FAILED or ERROR (SKIPPED/XFAIL count as not failing, noted in feedback) |
| G5 | fails matching the issue | at least one collected target is FAILED/ERROR with failure type `AssertionError` or a type in `issue_exc` |
| G4 | fails, unrelated to issue | otherwise (at least one target fails, none with a matching type) |

Notes
- G5 is checked before G4, so if any target fails in a way that matches, the instance stops.
- The rules use only the test output and the issue text, and they are deterministic, with no LLM judge.
- Known limitation: an AssertionError caused by a wrong expectation still counts as G5. That is accepted
  and documented: the rule can't know the right value without the reference fix.
- Informational flags (logged only; they change nothing): changed tests contain no `assert`/`assert*`/`raises`;
  skip/xfail markers added.

## 4. Revision rounds

- Trigger: G1–G4 and revisions used < 2 and budget left (section 5). G5 → stop.
- New mini run, same command, same config file. The task text is the issue plus the feedback block
  (section 6), passed through a per-round dataset file
  `round_k/dataset/data/test.jsonl` = `{instance_id, problem_statement: <issue + feedback>, prev_patch_b64}`.
  This file has no `patch`/`test_patch` fields at all, so they cannot leak.
- Starting state (G2–G4): the previous patch is pre-applied to the fresh container via
  `-c run.env_startup_command="cd /testbed && echo {{prev_patch_b64}} | base64 -d | git apply"`,
  so the agent edits it instead of retyping it. For G1 nothing is pre-applied; the patch text is
  shown in the feedback.
  *(This is a command-line config override, not a change to the file; needs user OK.)*
- Budget for round k: `-c agent.step_limit=<steps_left> -c agent.wall_time_limit_seconds=<secs_left>`.
  This is also an override; the config file is unchanged.

## 5. Budget (same as baseline: 100 steps, 1800 s per instance, all rounds + wrapper test runs)

- Steps used = sum of model calls over all rounds + 1 per wrapper test run *(proposal; needs user OK)*.
- Wall clock: starts when round 1's agent process starts and runs continuously to the end, covering all agent
  rounds, container starts for later rounds and wrapper test runs. The image is pulled once beforehand,
  outside the clock, as for the baseline.
  This is slightly stricter than the baseline, whose clock starts after its container is up.
- A new round starts only if `steps_left ≥ 1` and `secs_left ≥ 60`. **Gotcha:** mini treats
  `step_limit: 0` / `wall_time_limit_seconds: 0` as *unlimited*, so the wrapper must never pass 0.
- mini checks limits only between steps, so a step can overrun; the overrun counts. If time runs out
  during a wrapper test run, it is killed (classified G2/timeout) and no further round starts.
- After the last allowed revision (or when the budget is exhausted), the latest patch is still tested
  once if time allows, so its applicability and group are known. This doesn't affect the budget,
  because no round follows.

## 6. Feedback message (appended to the issue text as `{{task}}`; the agent also sees the frozen instance_template around it)

```
{issue text, unchanged}

---
FEEDBACK FROM AN AUTOMATED TEST RUN (revision {k} of at most 2)

A previous attempt at this task produced the test patch shown below. We applied it to the current,
unfixed code in a fresh copy of the repository and ran only the tests it adds or changes.

Command: {test_command}
Result: {GROUP_TITLE}
{GROUP_EXPLANATION}

Per-test results:
{test_id}: {status}{" (" + failure_type + ")" if any}
...

Test output (last {n} lines):
<test_output>
{tail of raw output, at most 150 lines / 8000 characters}
</test_output>

Previous test patch:
<previous_patch>
{patch text}
</previous_patch>
{PATCH_STATE}

Please revise the test. It must still check the behavior described in the issue with meaningful
assertions: do not delete or weaken assertions, and do not skip, xfail or otherwise disable the test
just to change its outcome. As before, change test files only and do not fix the issue.
```

`PATCH_STATE`
- G2–G4: "This patch is already applied in /testbed. Edit the test files in place, then submit as instructed."
- G1: "This patch is NOT applied in /testbed. Recreate your test changes in the test files, then submit as instructed."

| Group | GROUP_TITLE | GROUP_EXPLANATION |
|---|---|---|
| G1 | The patch could not be applied. | `git apply` reported: {error}. (Or: "No test patch was submitted." / "The patch modifies non-test files: {files}. Only test files may be changed.") |
| G2 | The tests could not run (setup error). | The test run stopped before your tests could execute, e.g. because of a syntax error, a failed import, a test that could not be collected, or a missing fixture (see output). Fix the test code so it runs. |
| G3 | All of your tests PASS on the current, unfixed code. | A test that passes on the unfixed code does not reproduce the issue. Change it so that it fails because of the problem described in the issue and would pass once the issue is fixed. |
| G4 | Your tests fail, but not in a way related to the issue. | The failure ({failure_types}) does not look like the problem described in the issue. Fix the test so that it fails because of the behavior the issue describes, not because of a mistake in the test. |

## 7. Final candidate and records

- Final candidate = the patch from the latest round whose `git apply` succeeded in the wrapper test run.
  If no round produced an applying patch: the final candidate is "none", recorded as a failure (missing prediction → invalid,
  in the denominator).
- The final candidate then goes through the same `check_test_only.py` → harness input as the baseline.
- Per instance: `runs/workflow/<run_id>/<iid>/round_{1,2,3}/` (mini output dir: traj.json, preds.json, logs;
  `wrapper_test/` with command, raw output, parsed statuses, classification.json; `feedback.txt` sent to the
  next round), `budget.json` (steps and seconds per round and per wrapper test run), `run_meta.txt`
  (same fields as baseline + config sha256 + overrides used), `final.json` (chosen round, reason).
- Per call: model, system_fingerprint, created (server time), cache hit/miss, completion, reasoning tokens.
  These come from every round's traj.json, with the same extractor as the baseline.

## 8. Full-run driver (proposal)

- Input: `configs/eval_instances.txt` (the 25 IDs, provided by the user), sorted alphabetically. Fixed order.
- One experiment run_id (e.g. `final-1`). For each instance, in order and one at a time:
  1. baseline (`run_baseline.sh`), then 2. workflow; both share the pre-pulled image.
  Each arm writes `done.json` when finished (including timeouts, errors and no submission; those are data).
- Resumable: an arm with `done.json` is skipped. An arm directory without `done.json` (interrupted run) is
  never deleted: it is moved to `<iid>.interrupted-<timestamp>/`, logged, and the arm is rerun.
  Interruptions are reported in the final write-up.
- DECIDED (user): harness PER INSTANCE, right after both arms of that instance have their final predictions
  (rule-4 check → `run_swt_harness.sh <run_id>-<arm>-<iid>`), so partial paired results exist if the run
  is cut short. Each prediction is still evaluated exactly once, after it is final. The driver records only
  harness exit codes and paths. Harness results are never passed to the agent or wrapper, and are not
  read or summarized until the user asks.
- Then the results script: resolved (harness), applicability (from our validity.json first, then the harness),
  coverage delta (N/A when unavailable), steps, wall time, rounds and groups (workflow), cost at the fixed
  peak price schedule, per-call timestamps with peak/off-peak flag, fingerprints.
- `driver.log` (timestamped events) + `status.tsv` (one row per instance × arm). Runs in the background with nohup.
- Time: worst case 25 × (30 + 30) min = 25 h of generation + harness (~5–10 min per instance per arm ≈ 4–8 h).
  The django baseline took 47 s, so typical is far lower. The laptop must not sleep during the run
  (that's a Windows setting for the user to change).

## 9. Before the full run

Build the wrapper, test it on the 3 pilot instances (checkpoint 3 for each pilot run), then checkpoint 4
(freeze configs) before starting the driver.

## 10. Implementation details (as built)

- Dataset access: `pyarrow.parquet.read_table(columns=[instance_id, problem_statement, repo, version])`.
  The other columns are never loaded.
- Round 1 is byte-for-byte the baseline command (same dataset snapshot, same config, no overrides).
  Rounds 2-3 use `--subset round_k/dataset` and `-c agent.step_limit=<left> -c agent.wall_time_limit_seconds=<left>`,
  plus `-c run.env_startup_command=cd /testbed && echo {{prev_patch_b64}} | base64 -d | git apply` for G2-G4.
  Pre-applying is skipped (patch shown as text instead) if the base64 patch is over 100 kB.
- Every wrapper check after a round costs 1 step, including a trivial G1 (empty/non-test patch).
  If no step or time is left, only `git apply --check` is run (no step charged), so the final candidate's
  applicability is still known.
- Test selection: AST over the post-patch file (parsed on the host with Python 3.11), changed lines from the
  diff hunks. sympy's runner takes files, so sympy runs the whole changed files but results are still
  matched to the changed functions by name. Fallback for every repo: the whole changed files
  (`get_test_directives(agent_patch, repo)`); in that mode every parsed test counts as a target.
- Test command: `MAP_REPO_TO_TEST_FRAMEWORK_VERBOSE[repo][version]` + labels; preceded by
  `MAP_VERSION_TO_INSTALL[repo][version]["eval_commands"]` if present. Timeout min(budget left, 900 s).
- mini is hard-killed by the wrapper at (time left + 300 s) as a safety net; mini's own wall limit
  normally stops it first.
- Not testable on the pilots (CLAUDE.md rule 5): the sphinx (`tox -epy39 -v --`), pylint and sympy test
  commands inside the SWE-bench images. A failure there would show up as G2 in the logs.
