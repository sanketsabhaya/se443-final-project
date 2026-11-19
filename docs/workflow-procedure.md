# Workflow procedure (as frozen at tag `freeze-1`)

This is a short procedure for the experimental arm, matching `scripts/run_workflow.py` (sha256 `77e4b379…`).
The rationale is in `docs/workflow-design.md`. Where that draft and the code disagree, the code is authoritative.

## Inputs and information boundary
1. Per instance, the wrapper reads only `instance_id`, `problem_statement`, `repo` and `version` from the
   SWE-bench Verified snapshot `c104f840`. It never loads `patch`, `test_patch`, `FAIL_TO_PASS`,
   `PASS_TO_PASS` or any harness result.
2. Feedback uses only the issue text and the output of running the agent's own test on the buggy code.

## Budget (same as the baseline)
3. Each instance gets **100 steps and 1800 s of wall time**, counted from the start of round 1 across all rounds.
   Every agent model call costs 1 step, and every wrapper test run costs 1 step.
4. Revisions are capped at **2**, so there are at most 3 agent rounds.
   Each later round runs mini with `agent.step_limit` and `agent.wall_time_limit_seconds` overridden to the
   remaining budget. The config file itself is never changed.

## One round
5. **Agent:** run the unchanged mini-SWE-agent (`mini-extra swebench`, `configs/unit_test_gen.yaml`, DeepSeek-Flash).
   The agent submits a test patch.
6. **Wrapper check:** start a fresh container from the instance's SWE-bench image (the buggy code) and run these steps:
   1. Check the patch is test-files-only (`check_test_only.py`, rule 4).
   2. Apply it with `git apply -v`.
   3. Select the targets: the test functions the patch adds or changes, found by parsing the AST.
      If none are found, or the repo is sympy, run the whole changed test files instead.
   4. Run the harness's per-repo verbose test command on those targets. It is capped at 900 s and at the remaining time.
   5. Parse the output with the harness's per-repo log parser.

   If no step or no time is left, the wrapper only checks that the patch applies, with no step charged and no classification.
7. **Classification:** apply these fixed rules in order. The first match wins.
   - **G1, patch unusable:** the patch is missing or empty, touches non-test files, has no `diff --git` headers, or fails `git apply`.
   - **G2, tests could not run:** at least one of these happened:
     - the test run timed out;
     - no target was collected (or, in file mode, nothing was parsed);
     - a setup marker appears (SyntaxError, ImportError, collection error, missing fixture, "no tests ran", and so on) and no target has the status FAILED. A marker is ignored if the issue itself names it.
   - **G3, tests pass on the buggy code:** no target FAILED or ERRORed.
   - **G5, failure matches the issue:** at least one failing target's exception type is `AssertionError`, or is an exception class named in the issue text.
   - **G4, failure unrelated:** any other failure.

## Stopping rules (checked after each round)
8. Stop on **G5**.
9. Stop if **2 revisions were already used** (`max_revisions`).
10. Stop if **fewer than 1 step or fewer than 60 s** remain (`budget_exhausted`).
11. Otherwise, for G1–G4, go to round k+1 with feedback.

## Feedback to the next round
12. The wrapper appends a feedback block to the issue text, which becomes the agent's `{{task}}`. The block contains:
    - the revision number and the command that was run;
    - the group's one-line result and a fixed explanation;
    - per-test statuses, with exception types;
    - the last 150 lines (at most 8000 characters) of the test output;
    - the previous patch;
    - a fixed instruction: keep meaningful assertions, do not skip or xfail tests, change test files only, and do not fix the issue.
13. For G2, G3 and G4, a previous patch that applied is pre-applied in the new container through
    `run.env_startup_command`, and the feedback says so. For G1, or for a patch whose base64 encoding is
    over 100 kB, the patch is not applied, and the agent is told to recreate its changes.

## Final candidate
14. The submitted prediction is the patch from the **latest round whose patch applied in the wrapper check**,
    whatever its group. If no round produced an applying patch, the prediction is empty or missing, and the
    instance counts as a failure.
15. Records per instance (`runs/workflow/<run_id>/<iid>/`):
    - `final.json`: rounds, groups, final round, stop reason;
    - `budget.json`: the step and time ledger;
    - `rounds.json`;
    - `round_k/`: the mini trajectory, the wrapper test output, and the feedback;
    - `final_preds.json`, `run_meta.txt`, `done.json`.
16. The harness runs once per arm after generation. Its results are never fed back.

## Known limitations (found post-hoc, not changed: the wrapper is frozen)
These are failure-type extraction bugs (F1–F4) that pushed real G5 cases into G4 or G3:
- **F1:** ANSI colour codes in tox output.
- **F2:** sympy 1.2's two-line failure header.
- **F3:** pytest's shortened `_ name _` header for long test names.
- **F4:** only the first matching parametrization is checked.

With them fixed, 13 of the 14 revised final-1 instances would have stopped at round 1 (`results/final-1/case_studies.md`).
