# Progress log

## 2026-11-13 — SWT-Bench harness install + smoke test

### Environment checks
- Docker Desktop 29.9.3 (client/server), WSL2 integration; 16 CPUs, ~7.5 GiB RAM visible (below README's 16 GB; no .wslconfig — left as is, watching for OOM).
- D: 191 GB free before any images; C: 17 GB free (nothing written there).
- Problem: first session had no Docker access (WSL integration off, then user not yet in `docker` group in the running shell). Fix: user enabled WSL integration and restarted the session; `docker` group now active.

### SWT-Bench clone
- Cloned https://github.com/logic-star-ai/SWT-Bench.git to ~/se443/SWT-Bench (README's eth-sri URL is outdated).
- Commit be12d4c8e7a5315a6bd60b0cad72736e96a4af3e (2026-11-04, "Merge pull request #53 ... bugstack-verified-results"), detached HEAD, read-only.
- Full env record: ~/se443/notes/swt-bench-env.md (commit, Python, uv, Docker, dataset rev, pip freeze).

### Verified README against source
- requires-python >=3.9, no upper bound -> Python 3.11.18 via `uv sync --frozen --python 3.11` (repo's uv.lock, 108 pkgs).
- Unit-test mode is the default `--exec_mode unit_test` (src/main.py). Reproduction-script mode only via flag; we don't use it.
- Defaults kept: --timeout 1800, --compute_coverage True, --cache_level env, --patch_types vanilla, --build_mode api. We set --max_workers 1.
- Verified subset: `--dataset_name princeton-nlp/SWE-bench_Verified --filter_swt`; filter = exclusion list dataset/filter_cases_verified.txt (67 IDs). Counted with the harness loader: 500 -> 433. Matches README table.
- Dataset revision c104f840cc67f8b6eec6f759ebc8b2693d585d4a. Harness has no revision flag, so runs use HF_HUB_OFFLINE=1 / HF_DATASETS_OFFLINE=1 to force the cached snapshot.
- Gotcha: filter file and all outputs are relative to cwd. Runner script runs from ~/se443/swt-runs/<run_id>/ with symlink `dataset -> ~/se443/SWT-Bench/dataset` (no harness edits).
- Gotcha: README's `src.report` imports figures.util (needs 'figures' extras). Not used; evaluation_results/*.json is enough.
- Pilots (django__django-16485, astropy__astropy-8872, matplotlib__matplotlib-14623) and psf__requests-2931 are all in the 433.

### Smoke test (psf__requests-2931, not in eval set — confirmed by user)
- Runner: scripts/run_swt_harness.sh (refuses existing run dirs; records timing, disk, exit code in run_meta.txt).
- Controls: run `smoke-gold` (gold predictions, expect resolved) and `smoke-empty` (smoke/empty_patch_psf__requests-2931.jsonl, expect not resolved).
- Only summary counts are read; per-instance harness logs contain reference test patches and are not inspected.

### Smoke test results (summary counts only)
| run | total | resolved | unresolved | error | wall time |
|---|---|---|---|---|---|
| smoke-gold (gold) | 1 | 1 | 0 | 0 | 9m46s (includes first image builds) |
| smoke-empty (empty patch) | 1 | 0 | 1 | 0 | 2m08s (images cached) |
- Both exit code 0. Harness reports `completed_instances: 0` in both runs even though they finished; appears to be a harness counting quirk, resolved/unresolved/error are the counts we use.
- Images: 4 images, 4.0 GB in Docker; D: used went 8.9G -> 15G, confirming Docker data lives on D:. No memory problems at max_workers 1.
- Results: ~/se443/swt-runs/smoke-{gold,empty}/evaluation_results/*.json. Driver log: ~/se443/swt-runs-smoke-driver.log.
- Status: CHECKPOINT 1 — waiting for user approval before moving on.

## To-do
- [x] (resolved 2026-11-13, see 'Results script' entry) BEFORE FINAL REPORTING: inspect harness source (~/se443/SWT-Bench, read-only) for "Mean coverage delta":
  (a) units — fraction vs percent;
  (b) exactly which instances are averaged;
  (c) whether instances with no coverage (empty/missing/failed patch) count as 0 or are excluded.
  Project rule: unavailable coverage must be reported as N/A, not 0.
- [x] (resolved 2026-11-13: INCLUDED, beta=0.979 on 65 pilot calls) reasoning_tokens vs completion_tokens: DeepSeek docs do NOT say whether reasoning is included (only safety_tokens are stated as included). Check empirically on pilot usage data; do not assume.
- [ ] Cost (user decision): headline cost for BOTH arms uses ONE fixed schedule, standard/peak prices for every call (deepseek-flash per 1M tokens: cache hit $0.006, cache miss $0.30, output $1.20; re-check before final report), so time of day cannot bias the comparison. Separately record per call the actual UTC timestamp and peak/off-peak status (peak = 01:00-04:00 and 06:00-10:00 UTC Mon-Fri, excl. Chinese holidays; off-peak = half price); informational only.
  Timestamp source: check after first pilot whether traj.json has a per-call time (e.g. response `created`); if not, find another reliable source without modifying mini.
- [ ] After first pilot run: confirm per-call fields (model, system_fingerprint, prompt_cache_hit_tokens, prompt_cache_miss_tokens, completion_tokens, reasoning_tokens) are present in traj.json `extra.response`; write extraction script.
- [x] Write preds.json (mini: dict keyed by instance_id) -> predictions.jsonl converter for the harness -> done as scripts/check_test_only.py (also does the rule-4 validity check).
- [x] (implemented in scripts/results.py) Applicability metric (user decision): a prediction that check_test_only.py marked invalid (missing / empty / no_diff_headers / non_test_files) and submitted as "" counts as NOT applicable, even if the harness reports the empty patch as applied. The results script must take applicability from our <prefix>.validity.json first, and use the harness's applied status only for valid predictions. Same rule for both arms.

## 2026-11-13 — Checkpoint 1 approved by user; files committed.

## 2026-11-13 — Checkpoint 2 preparation (baseline config + prompt)
- mini-swe-agent at 04d809ceab9df28f9adaed044884180159172930 (v2.4.6), untouched (git status clean). Called only via `uv run --frozen --project`.
- Model: `deepseek/deepseek-flash` (from ~/.config/mini-swe-agent/.env MSWEA_MODEL_NAME); DeepSeek /models lists deepseek-flash. MSWEA_COST_TRACKING=ignore_errors.
- Upstream swebench.yaml is a FIX prompt (edit non-test files). Wrote configs/unit_test_gen.yaml = upstream + test-generation instance_template, step_limit 100, wall_time_limit_seconds 1800, cost_limit 0, model deepseek/deepseek-flash. Diff vs upstream checked: only those changes.
- Config validated with mini's own loader (AgentConfig) and template rendered with a placeholder task; no agent run, no API call.
- Source facts: agent sees only `problem_statement` ({{task}}); full model response saved per call in traj.json; wall-time limit exists in AgentConfig (checked between steps; clock starts after container start).
- Gotcha (rule 8): mini's swebench runner deletes an instance's existing traj + preds entry on re-run into same dir -> runner refuses existing output dirs.
- Gotcha: mini's `--subset verified` loads an unpinned dataset; runner passes the cached snapshot dir (rev c104f840) instead, same data as harness. Verified 500 rows, pilots present.
- Gotcha: `git diff` omits new untracked test files -> submission step stages test files and uses `git diff --cached`.
- Gotcha: mini's docker pull_timeout is 120 s -> runner pre-pulls image outside the agent clock and records digest.
- Pilot images exist on Docker Hub (docker manifest inspect).
- scripts/run_baseline.sh written (not run). Outputs to runs/baseline/<run_id>/<instance_id>/.
- Status: CHECKPOINT 2 shown; user did NOT approve yet.

## 2026-11-13 — Checkpoint 2 revision (user feedback)
- Removed verification procedure from baseline prompt (old steps 2 "work out how tests run", 4 "run your test and confirm it fails", 5 "make sure the file still runs"). Workflow is now: analyze -> write focused test -> follow file conventions. Goal sentence softened to "should fail ... and pass once fixed". Rationale (user): baseline may run tests but is not instructed to; execution-based verification is what our workflow adds; instructor's baseline had none.
- Remaining "Step 2: Verify your patch / inspect patch.txt" is upstream verbatim (patch-format check, no test execution); kept.
- Rule 4 decision (user): option (b). scripts/check_test_only.py classifies patches by diff-header paths only; invalid (missing / empty / no_diff_headers / non_test_files) -> submitted to harness as "" so they count as failures in the denominator; reasons logged in <prefix>.validity.json; same script for both arms. Tested on synthetic inputs (6 cases incl. new-file and refusal to overwrite).
- DeepSeek docs (api-docs.deepseek.com): temperature default 1, no effect in thinking mode (default mode); no seed parameter; parallel_tool_calls not documented (drop_params kept as upstream). run_baseline.sh now records model_kwargs actually sent, temperature and seed status in run_meta.txt, and copies the config into the run dir.
- Status: CHECKPOINT 2 (revised) — waiting for user approval.

## 2026-11-13 — Checkpoint 2 approved by user
- configs/unit_test_gen.yaml frozen for the pilots: the workflow arm must use this exact file unchanged (sha256 recorded in each run_meta.txt).
- Next: baseline pilot on django__django-16485 (run_id pilot-baseline-1), then CHECKPOINT 3.
- NOTE (user, 2026-11-13): django__django-16485 is a pilot AND one of the 25 evaluation instances. The baseline config is already frozen. Harness results for pilot instances must NOT be used to change the wrapper's design or rules. Harness is run on the pilot prediction only because the course pilot requires it.

## 2026-11-13 — Pilot 1: baseline on django__django-16485 (run_id pilot-baseline-1)
- Agent: exit_status Submitted; 12 model calls (steps); agent wall time 47 s (18:20:09 -> 18:20:56 local); image pull 2m20s outside the clock. Config sha256 eb3e1ccd... (frozen).
- Rule-4 check: valid, touches only tests/template_tests/filter_tests/test_floatformat.py.
- Agent ran tests itself (not instructed): step 7 ran the existing test file before editing; step 9 ran its new test (rc=1, failing) and then submitted.
- Harness (swt-runs/pilot-baseline-1, ~8 min incl. image build): total 1, resolved 1, unresolved 0, error 0.
  REMINDER: this is also an evaluation instance; this result must not influence the wrapper's design or rules.
- Per-call data in traj.json `extra.response`: model (deepseek-flash), system_fingerprint (same for all 12 calls), created (server Unix time), usage.prompt_cache_hit_tokens / prompt_cache_miss_tokens / prompt_tokens / completion_tokens / completion_tokens_details.reasoning_tokens. All present.
  - hit + miss == prompt_tokens for all 12 calls.
  - reasoning_tokens <= completion_tokens for all 12 calls (consistent with reasoning being INCLUDED in completion_tokens, but not proof; docs silent). Keep the to-do open.
  - mini's own cost estimate: $0.0046 (litellm price table; not our cost method).
- Clock: WSL clock is ~94 s ahead of DeepSeek server time (curl Date header). Durations are fine; for per-call timestamps / peak status use the server `created` field. All 12 calls were at ~00:18-00:19 UTC Saturday -> off-peak.
- Status: CHECKPOINT 3 — waiting for user.

## 2026-11-13 — Workflow wrapper DESIGN (not built)
- User: final presentation Monday; design the wrapper + full-run driver, then stop for review.
- Design written to docs/workflow-design.md (draft). Grounded in harness source: get_test_directives(patch, repo) is a pure function of the patch passed (we pass only the agent's patch); generic test commands from MAP_REPO_TO_TEST_FRAMEWORK(_VERBOSE); per-test parsing via MAP_REPO_TO_PARSER. FAIL_TO_PASS/PASS_TO_PASS/test_patch never used.
- Open decisions for user: (1) rule-4-invalid/empty patch mid-workflow -> G1; (2) each wrapper test run = 1 step; (3) pre-apply previous patch via -c run.env_startup_command + per-round limit overrides (config file unchanged); (4) harness once per arm after all generation vs per instance; (5) need eval_instances.txt.
- Status: waiting for user review of design.

## 2026-11-13 — Wrapper + driver BUILT (design approved with user decisions)
- Decisions (user): G1 includes non-test/empty patches; each wrapper check = 1 step; previous patch pre-applied via -c run.env_startup_command (config file unchanged, documented as part of the workflow); harness PER INSTANCE after both arms are final (driver records exit codes only; results not read until user asks; never fed back).
- configs/eval_instances.txt: 25 IDs from user; plain sorted order == given order; recorded as fixed run order (driver also writes runs/experiment/<run_id>/run_order.txt and refuses a different order on resume). All 3 pilots are evaluation instances.
- Committed runs/ (baseline pilot generation outputs) after scanning for the API key (none found).
- scripts/run_workflow.py (+ run_workflow.sh launcher, SWT venv for read-only harness specs/parsers): rounds, wrapper test runs, fixed classification, feedback, budget ledger, final candidate, done.json. Dataset read with column projection (instance_id, problem_statement, repo, version only).
- scripts/run_experiment.py + start_experiment.sh: sequential, sorted order, baseline -> workflow -> harness per arm per instance; done.json resume; incomplete dirs moved to *.interrupted-<ts> (never deleted); 2 attempts per arm; flock; D: free-space guard (stop < 40 GB). run_baseline.sh now writes done.json.
- Tests: pure-function unit tests (all G1-G5 paths); container mechanics on the real django image (baseline pilot patch -> G5, ValueError named in issue); driver dry run with fake launchers (order, crash retry + move-aside, resume skip, interrupted-harness rerun, lock, order mismatch refusal).
- Workflow pilot (run_id pilot-workflow-1, django__django-16485): round 1 Submitted, 9 model calls, 33 s; wrapper check G5 (failure_matches_issue: ValueError), 2.4 s, 1 step; stopped, no revision. Total 10 steps, 35.4 s. Final = round 1 patch; rule-4 valid. Harness NOT run on it (not requested).
- Revision path not exercised by the real agent (round 1 was G5). Plumbing verified without model calls via mini's own get_sb_environment: per-round dataset loads (3 fields only), -c limit overrides parse as ints, startup command pre-applies previous patch in mini's container. A leftover test container from that check was removed.
- Known gap: sphinx / pylint / sympy test commands inside SWE-bench images untested (rule 5 limits dev to pilots).
- Status: STOP before full run (waiting for user).

## 2026-11-13 — Pre-freeze checks (user-approved items 1-3)
### Workflow pilots (run_id pilot-workflow-1)
| instance | round | agent steps / time | wrapper check | revision? |
|---|---|---|---|---|
| astropy__astropy-8872 | 1 | 13 / 38 s | G5 (AssertionError), 3.4 s | no -> stop |
| matplotlib__matplotlib-14623 | 1 | 15 / 54 s | G4 logged (failure type not extracted -> BUG) , 5.7 s | yes |
| matplotlib__matplotlib-14623 | 2 | 16 / 75 s (pre-applied patch, overrides 84 steps / 1740 s) | G5 (AssertionError), 5.5 s | no -> stop |
- astropy total 14 steps, 41.5 s; matplotlib total 33 steps, 140 s, final = round 2.
- BUG found (wrapper's own output, not harness): pytest's `E   assert ...` lines and the long-tb location line `path.py:950: AssertionError` were not recognised and the short-summary line was truncated (`- asser...`), so the failure type was None -> G4. Fixed exc_from_text (location-line regex; strip `E` prefix before `assert`). Offline re-classification of all 4 saved pilot checks with the fix: all G5 (matplotlib round 1 G4 -> G5; the others unchanged).
- Consequence: matplotlib's revision was triggered by the bug. Pilot data kept as is (data). The revision mechanics (feedback via per-round dataset, pre-applied patch via startup command, budget overrides, final = latest applying round) ran end to end for real.
### Test commands in SWE-bench images (non-evaluation instances, existing tests only)
- sphinx 7.2 (sphinx-doc__sphinx-10614): `tox -epy39 -v -- tests/test_util_typing.py::test_restify` -> PASSED, parser matched, 15 s.
- pylint 2.14 (pylint-dev__pylint-6528): pytest on test_numversion -> 11 parametrized cases matched, 1.6 s.
- sympy 1.2 (sympy__sympy-14976): `bin/test -C --verbose sympy/core/tests/test_basic.py` -> test_structure matched (16 parsed), 2.3 s.
- Gaps: sphinx 3.4 / 3.5 / 4.0 (9 of 10 sphinx eval instances) and pylint 2.15 (3 of 4) have no non-evaluation instance in Verified -> untested versions.
- Check images removed afterwards (digests in runs/command_checks/removed_images.txt).
### Driver image cleanup (user-approved)
- After both arms + both harness runs of an instance: remove the instance's mini image and the harness `exec.eval.*` images that appeared since a persisted pre-harness snapshot; base/env kept; digests logged in runs/experiment/<run_id>/images/<iid>.removed.json. Tested with a disposable tag (removed, ubuntu kept).
- D: 168 GB free, Docker images 18.3 GB.
- Status: CHECKPOINT 4 (freeze) — waiting for user.

## 2026-11-13 — Freeze adjustments (user) and FREEZE
### Infra-only check on evaluation images (user-approved; reveals no evaluation answers)
- Existing generic repo tests only; no agent, no patch, no test_patch, no harness; issue text not loaded (checker reads only instance_id/repo/version).
- sphinx 3.4 (sphinx-doc__sphinx-8459 image): `tox -epy39 -v -- tests/test_util_matching.py::test_compile_matchers` -> exit 0, PASSED, parser matched, 20.7 s.
- pylint 2.15 (pylint-dev__pylint-6903 image): `pytest -rA --tb=long -p no:cacheprovider tests/test_numversion.py::test_numversion` -> exit 0, 11/11 matched PASSED, 1.6 s.
- Output: runs/infra_checks_eval_images/. Images kept (the driver reuses and later removes them).
### Retry rules (confirmed + made explicit)
- Generation (both arms, same rule): retry ONLY if the launcher left no done.json (infrastructure crash: Docker/pull/driver/wrapper process died). Agent step/time limits, mini-caught errors (incl. API errors caught by mini -> recorded exit_status), wrapper-killed agent runs, and bad/empty patches all end with done.json -> never retried. Max 2 attempts; each retry logged as INFRA_RETRY_generation in status.tsv + driver.log; crashed attempt dirs moved to *.interrupted-<ts> (kept).
- Harness: retry ONLY the unchanged prediction (same harness_input.jsonl, sha256 logged) if the run is incomplete, exits non-zero, or reports error_instances > 0 (driver reads only that count). Max 2 attempts; logged as HARNESS_RETRY_same_prediction; final status in runs/experiment/<run_id>/harness_final/<hid>.json.
- Dry-run verified (fake launchers): agent-limit outcome not retried; crash retried once; harness error retried with identical input sha.
- Wrapper: if it ever hard-kills mini, it now also removes mini's orphaned container.
- Pilots re-run fresh in final-1 (pilot outputs not reused).
### Frozen file hashes (sha256 prefix) at tag freeze-1 (commit f8772f5)
eb3e1ccd8a5a1d02  configs/unit_test_gen.yaml
77e4b3795bc8522b  scripts/run_workflow.py
b6714e87713e1098  scripts/run_baseline.sh
07d0455739984832  scripts/check_test_only.py
0430fdbfba624090  scripts/run_experiment.py
7218cd7c12ff1c4b  scripts/run_swt_harness.sh
- final-1 started 2026-11-13T19:05:48-06:00 via scripts/start_experiment.sh final-1

## 2026-11-13 — Results script (scripts/results.py; not a frozen file; written while final-1 runs)
### Coverage delta, from harness source (src/grading.py get_pred_report, src/run_evaluation.py make_run_report)
- Per-instance field: `coverage_delta_pred` in run_instance_swt_logs/<hid>/<model>/<iid>/report.json.
- Units: FRACTION in [0, 1] = (# executable lines changed by the reference fix whose execution count is higher with the predicted tests than in the base run) / (# executable changed lines). We report it as a percentage.
- None when: patch not applied, no executable changed lines, or the instance errored (no report).
- Harness aggregate "Mean coverage delta": plain mean over instances with coverage_pred not None; error instances skipped; prints 0 when none -> we report N/A + n.
- Applicability source: `patch_successfully_applied` in report.json (after our validity.json gate).
- Script reads only resolved / patch_successfully_applied / coverage_pred / coverage_delta_pred (whitelist; verified that a planted gold field does not leak into outputs).
### reasoning_tokens
- DeepSeek returns reasoning_content. Least-squares fit completion_tokens = a*visible_chars + b*reasoning_tokens over 65 pilot calls: b = 0.979 -> reasoning tokens ARE included in completion_tokens (cost formula counts them once, via completion_tokens).
### Tests
- Pilot outputs (copied into scratchpad final-1 layout): ran; found and fixed: invalid count included missing predictions; harness time double counting in shared-dir test mode; reasoning verdict switched to regression test.
- Fake data (6 instances covering all paired cells, invalid-but-harness-applied, missing, unevaluated, coverage 0.0 vs None, revisions, retries/interruptions, peak/off-peak): all metrics match hand calculation.
- Guard: refuses non-pilot/fake run ids unless --confirm-read-harness (to be passed only when the user asks for final-1 results).
- final-1 harness results NOT read.

## 2026-11-13 — final-1: infrastructure intervention at instance 6 (user actions; no frozen file changed, no generation redone)
Times are local (-06:00). Facts checked against driver.log / status.tsv; harness results NOT read.
1. ~21:44 user ran `docker kill naughty_archimedes`: harness environment-build container for matplotlib__matplotlib-22719 (baseline arm), stuck in `conda-env create --file environment.yml` for 47+ min at 100% CPU, memory rising 5.65 -> 6.0 of 7.47 GiB. Driver (21:45:32) logged harness attempt 1 exit=0, complete, error_instances>0; moved folder to `final-1-baseline-matplotlib__matplotlib-22719.interrupted-20261113T214532`; started HARNESS RETRY 2/2 on the unchanged prediction (sha256 3bcbc524a857).
2. ~21:46 user stopped the driver (kill -TERM of its process group) and removed leftover containers. Retry 2 never finished.
3. ~21:48 user raised WSL memory 7.5 GB -> 12 GB (~/.wslconfig `memory=12GB`), `wsl --shutdown`, restarted Docker Desktop. Verified: `free` 11Gi, `docker info` MemTotal 12542935040.
4. 21:51:48 driver resumed (pid 860). Instances 1-5 and both 22719 generations skipped (done.json present); retry-2 folder moved to `...22719.interrupted-20261113T215148`; 22719 baseline harness restarted on the same harness_input.jsonl.
- Frozen hashes re-checked after resume: all 6 unchanged.
- Harness folders for 22719 baseline: the final one plus two *.interrupted-* (kept as data).

### Memory setting per stage (exact)
| Instances (run order) | Generation, both arms | Harness, both arms |
|---|---|---|
| 1-5 (astropy-8872 ... matplotlib-21568) | 7.5 GB | 7.5 GB |
| 6 matplotlib-22719 | 7.5 GB (20:44-20:53) | 12 GB (final runs; baseline's killed attempts were at 7.5 GB) |
| 7-25 | 12 GB | 12 GB |
Within each instance and stage, both arms ran under the same setting.

### Bookkeeping caveats
- The driver's attempt counter restarted on resume, so 22719 baseline has had 3 harness starts on the same prediction (attempt 1 killed, retry 2 interrupted by the stop, this session's attempt 1); the resumed driver may still do 1 more retry if this one errors. harness_final/<hid>.json "attempts" counts only this session's runs; the two *.interrupted-* folders + this entry are the full record. Report it as an infrastructure retry on an unchanged prediction, not as an extra evaluation.
- results.py takes harness time only from the final harness folder, so the ~52 min killed attempt and the ~6 min interrupted retry are excluded from "total harness time"; report them separately as infrastructure overhead.

### Effect on interpretation
- Paired comparison (success per arm, 2x2 table, per-instance differences) is not affected by design: at every stage both arms of an instance ran under the same memory setting, and no generation was redone or changed.
- Generation results for all 6 affected instances came from the 7.5 GB setting; the model, prompts, budgets and wrapper are identical, so a memory limit could change only infrastructure behaviour (a container being slow or killed by OOM inside a test run), not the agent's inputs. A per-instance OOM would show up in the trajectory/wrapper logs and should be checked when results are allowed to be read.
- Harness outcome: the test result itself should not depend on memory; what changes is whether the harness environment build finishes (hang / error) vs. runs. The raise lowers the chance of harness errors from instance 6 on; instances 1-5 had already completed their harness runs.
- Timing: absolute generation and harness times are not strictly comparable across the 1-5/6 and 7-25 groups (memory pressure can slow container work), so aggregate times mix two settings. Within-instance arm comparisons remain valid. Report mean times with a split (instances 1-6 vs 7-25 for generation; 1-5 vs 6-25 for harness) as a sensitivity check, and state the change in the report's threats-to-validity section.
- Cost: unaffected (token counts do not depend on machine memory).

## 2026-11-14 — final-1 overnight: stuck matplotlib harness env builds, watchdog, harness-error list, diagnosis
No frozen file changed (6 hashes re-checked); no generation redone; harness results (resolved/report.json/evaluation summaries beyond the error count) NOT read. Sources: driver.log, status.tsv, harness_final markers, watchdog.log, harness image_build_logs (build logs only).

### User interventions
- ~22:26-23:00 (user) manually killed stuck `conda-env create` containers for matplotlib__matplotlib-22719 (user reports three). Harness folders show baseline-arm BuildErrors at 21:45 (first kill, logged earlier), 22:27 and 23:00; folder `final-1-baseline-matplotlib__matplotlib-22719.interrupted-20261113T222748` added. Baseline 22719 final marker: ok=False, attempts=2 (attempts of the resumed driver session only; 4 harness starts in total on the same prediction sha256 3bcbc524a857).
- 23:02 (user) started `scripts/watchdog_conda.sh` (pid 3268). NOT part of the frozen experiment. Every 60 s it checks running containers; any whose `docker top` shows `conda-env create` and whose container age > 1800 s is `docker kill`ed; logged to runs/experiment/final-1/watchdog.log.
- watchdog.log: 14 kills from 23:30:51 to 06:45:14 (the 14th happened after the user's count of 13). Each matches one harness BuildError (exit 137) by time: 22719 workflow x2; 22865 baseline x2, workflow x2; 22871 baseline x2, workflow x2; 23299 baseline x2, workflow x2. Every kill was the same env image, exec.env.x86_64.1888cbc29e8911ba248a1e.
- At 06:45:40 the driver (pid 860) finished instance 9 (23299; its images removed) and started instance 10/25, matplotlib__matplotlib-25311 (baseline generation).

### Harness runs that ended as harness errors (harness_final markers: ok=False after 2 attempts; error_instances > 0)
| Instance | Baseline | Workflow | Build failure (from image build logs) |
|---|---|---|---|
| astropy__astropy-8872 | error | error | instance image: `pip install -e .` fails, ModuleNotFoundError: pkg_resources |
| matplotlib__matplotlib-22719 | error | error | env image 1888cbc: conda solve never finishes (killed) |
| matplotlib__matplotlib-22865 | error | error | same env image |
| matplotlib__matplotlib-22871 | error | error | same env image |
| matplotlib__matplotlib-23299 | error | error | same env image |
- 10 of 18 arm runs so far (5 of 9 instances, always both arms). ok=True: django-16485, matplotlib-14623, -20676, -21568 (both arms).
- No test ever ran in these runs: each failed while building the image, before any prediction was applied. So they say nothing about either arm's tests, and the pattern is identical across arms.

### Diagnosis (read-only; one `--network none` base-image container for `conda config`; no harness change)
matplotlib 3.5 (22719, 22865, 22871, 23299; all share environment_setup_commit de98877e, hence ONE env image key 1888cbc):
- Harness spec (src/constants.py MAP_VERSION_TO_INSTALL_MATPLOTLIB): versions 3.5/3.6/3.7 use `packages: environment.yml`, python 3.11; src/exec_spec.py writes the repo's environment.yml (fetched live from GitHub at the env-setup commit, only `name:` rewritten to testbed) and runs `conda env create --file environment.yml`, then `conda install python=3.11`.
- That environment.yml (from setup_env.sh in the build log): channel conda-forge; ~55 mostly UNPINNED packages including heavy GUI stacks (pyqt, wxpython, gtk3, pygobject, cairocffi), docs tooling (sphinx, pydata-sphinx-theme, sphinx-gallery, ...), testing/dev tools, and pip extras; no python pin.
- Base image (exec.base.x86_64, Miniconda3-py311_23.11.0-2): conda 23.11.0, solver libmamba (conda-libmamba-solver 23.12.0, libmamba 1.5.3), channel_priority flexible, channels [defaults, conda-forge] (the Dockerfile appends conda-forge).
- All 18 build logs for 1888cbc stop at "Solving environment: ...working..." (repodata download takes ~75 s and finishes); none got past the solve. The longest run (first, under 7.5 GB) solved for ~51 min with memory rising to ~6 GB before the kill; the 12 GB runs were killed at ~31 min. So it is a solver blow-up/non-termination, not a download or memory-limit failure.
- Likely cause: the solve runs against TODAY's conda-forge + defaults repodata (no date/version pins), with flexible priority across two large channels and many loosely constrained GUI/doc packages. The yml has not changed since 2022, but the package universe has, so the problem is now much bigger than when SWE-bench images were first built. Not verified further: a test solve is CPU-heavy (needs approval).
- Earlier matplotlib instances used a different path: 14623 (3.1) and 20676/21568 (3.4) use `packages: requirements.txt` -> `conda create -n testbed python=3.8` + `pip install -r requirements.txt` (no conda solve of a big env). 21568 reused 20676's env image (same env-setup commit f93c0a3d). That is why they built.
- Upcoming: matplotlib__matplotlib-25311 is version 3.7 -> also environment.yml / conda env create (env-setup commit 0849036f); expect the same hang -> ~2 h of watchdog kills, then harness error for both arms, unless something changes.
astropy-8872 (different cause): the env image builds; the INSTANCE image fails in setup_repo.sh at `pip install -e .`. pip's isolated build environment installs the latest setuptools allowed for python 3.9 (82.0.1); the old astropy setup imports `pkg_resources`, which that setuptools does not provide -> ModuleNotFoundError. Deterministic (failed identically 4 times in ~1 min); retries cannot help.
Risk for the rest: the sphinx/pylint infra checks used the SWE-bench Docker Hub images (mini's), not SWT-harness-built images, so the harness build of remaining repos is unverified and could hit the same unpinned-dependency drift.

### Threats to validity (additions)
- Harness errors from environment drift: the official SWT-Bench harness rebuilds environments from current package indexes. For 5 of the first 9 instances it could not build an image (conda solve non-termination for matplotlib 3.5; setuptools/pkg_resources for astropy). These are infrastructure failures, symmetric across arms (identical build, failed before any prediction was applied); they stay in the denominator as failures for both arms. Report success also over evaluable instances, plus the error list.
- Watchdog (scripts/watchdog_conda.sh, not frozen, started 23:02 after instance 6's baseline harness): it kills any container in `conda-env create` older than 30 min. (a) It could kill a build that was legitimately slow but would have finished; the 30-min threshold is arbitrary, and the first, unwatched 22719 build ran ~51 min without progress, which supports but does not prove non-termination. (b) It is not supervised: it stops if WSL/Docker restarts or the shell dies, so builds after such an event would run unbounded. (c) It applies to both arms equally, but only from 23:02 on (22719 baseline: manual kills at 21:44, ~22:27, ~23:00). (d) Container age, not solve time, is measured (includes ~75 s repodata download).
- Harness time for errored runs is wasted build time (~62 min per arm for matplotlib 3.5). results.py counts only the final folder; report the overhead separately.

## 2026-11-14T06:56:53-06:00 — DECISION (user): option A for final-1 harness errors
- Harness errors are accepted as unevaluated failures, kept in the denominator for BOTH arms: astropy-8872 and matplotlib 22719/22865/22871/23299 so far, plus any later ones.
- matplotlib-25311 runs as is. The watchdog (pid 3268) stays on. No harness or environment changes.
- Re-evaluations (B: unlimited-time rebuild with identical spec; C: environment fixes; D: test solve) are decided only after final-1 finishes, and applied identically to both arms on the unchanged final predictions; nothing goes back to the agent. Decided before any final-1 harness results were read.
- At decision time: driver pid 860 running (instance 10/25); frozen hashes unchanged.

## 2026-11-14 — final-1: infrastructure interruption (network change), 08:59-09:50
No frozen file changed (6 hashes re-checked); no generation redone; harness results NOT read.
- Cause: the user moved the laptop to a different network. The user paused the driver (kill -TERM of the driver's process group, old pid 860), stopped the watchdog (pkill; old pid 3268), and removed leftover containers. The user gives ~08:58 as the time. The logs show the stop came just after 08:59:28: both 11510 generations had already finished (baseline 08:49:13-08:52:19 rc=0; workflow 08:52:19-08:59:28 rc=0, done.json, stop_reason max_revisions, round-3 mini exit Submitted). Then the rule-4 check ran, and the baseline harness started at 08:59:28 and was killed.
- Resume ~09:50 on stable wifi: driver pid 60494 (driver start 09:50:07), watchdog restarted as pid 60586. User checks passed: ping api.deepseek.com; Docker networking.
- Driver on resume: instances 1-14 and both 11510 arms skipped (done.json / harness_final present). It moved the interrupted harness folder to `final-1-baseline-sphinx-doc__sphinx-11510.interrupted-20261114T095007` (kept) and restarted the 11510 baseline harness on the unchanged harness_input.jsonl.
- No generation was in progress during the network change, so no model call or agent run was affected. The only affected work is one harness attempt (11510 baseline, ~0 min of useful progress lost). The resumed driver's attempt counter restarted, so the harness_final "attempts" for this arm does not count the interrupted start; the .interrupted folder + this entry are the record.
- Watchdog gap 08:59-09:50: no harness ran during that time, so no build went unwatched.

## 2026-11-14 — final-1 complete
- Driver: "driver finished all instances" at 13:28:42 (pid 60494 exited).
- Watchdog (pid 60586) stopped with pkill at ~13:35 (confirmed gone at 13:35:51). watchdog.log total: 14 kills, last at 06:45:14 (none after the 23299 workflow arm; none for 25311 or later).
- No containers left running. Frozen files unchanged.
- Results script run at 13:35:57 (results/final-1/20261114T133557): `results.py final-1 --team "Mihir Barvaliya & Sanket Sabhaya" --confirm-read-harness` (user-requested). Unevaluated (harness image build failed, both arms): astropy-8872 (pkg_resources), matplotlib 22719/22865/22871/23299 (conda solve), pylint-7277 (editable install: build backend lacks the build_editable hook). matplotlib-25311 (3.7) built and was evaluated. No API/network generation errors (all mini exit_status Submitted; the only error-like match was repo test code); single system_fingerprint across 1451 calls. No re-evaluation started (user decides B/C/D).

## 2026-11-14 — POST-HOC analysis of final-1 (read-only; results unchanged; nothing re-run; wrapper NOT changed)
- Committed final-1 outputs (b754b3f) after a key scan (exact key value + `sk-` pattern: no hits).
- Harness results read with the user's approval: only resolved/applied/coverage_delta_pred, the predicted tests' tests_pred transitions, and pred_pre/pred_post test output. No patch/test_patch/tests_gold.
- Scripts: scripts/posthoc/reclassify.py (ANSI only) and reclassify2.py (F1-F4). Both import the frozen run_workflow.py and call its own classify() on the saved wrapper_test outputs; the fixes are applied to the INPUT only. Recomputed == saved for every round with the original input, so the replay is faithful.
### Wrapper classification bugs found (input-side; the fixed rules themselves unchanged)
- F1: ANSI colour codes in sphinx tox output defeat the `E ...` / `path:N: Type` / FAILED-summary patterns -> failure type None -> G4 "unknown error". Affects every sphinx round. Same class as the pilot pytest-extraction bug, not caught in pilots (no sphinx pilot).
- F2: sympy 1.2 failure header is two lines (a row of underscores, then " path:test ") -> not matched -> G4 (sympy-15017 x3).
- F3: pytest shortens headers to `_ name _` for long parametrized ids -> not matched (sphinx-8621 r2).
- F4: parametrized targets: classify() keeps only the FIRST matching parametrization -> matplotlib-14623 [linear-x] PASSED hid [log-x/y] FAILED -> false G3 "all tests pass" x3; also 22865 r1-2 and sphinx-8621 r3.
- With F1-F4: 13 of 14 revised instances would be G5 in round 1 (stop). The only genuine revisions: pylint-6386 (SystemExit / Failed from argparse; the issue names the message, not the exception class -> a limit of the rules, not a parsing bug). Of the 13 falsely revised instances, 9 ended with a different test from round 1; sympy-15017, sphinx-11510, -8548 and -8638 ended with exactly the round-1 test.
- sympy-15017 (the only paired difference): its final test == its round-1 test, so the win came from the first agent run, not from the feedback.
### Harness environment failures inside "evaluated" instances
- All 13 evaluated both-fail instances show an environment signature in both arms, pre and post: sphinx 3.x/4.0 x9 `No module named 'roman'` (test modules fail to import; mostly 0 parsed tests); pylint 6386/6903/7080 `UnknownMessageError 'c-extension-no-member'`; matplotlib-25311 setuptools_scm `release-branch-semver` DeprecationWarning turned into an error.
- Only 6/25 have a usable verdict (django-16485, mpl-14623/20676/21568, sphinx-11510, sympy-15017): baseline 5/6, workflow 6/6.
- The wrapper/agent environment (prebuilt SWE-bench images) differs from the harness's freshly built images; symmetric across arms, but absolute rates are heavily understated.
- Case studies: results/final-1/case_studies.md. Offline re-classifications: results/final-1/posthoc/.
- Nothing above was fed back to the agent or the wrapper. No re-evaluation started (B/C/D still the user's decision).

## 2026-11-14 — POST-HOC harness validation with GOLD predictions (run_id posthoc-gold-1)
- `scripts/run_swt_harness.sh posthoc-gold-1 gold sphinx-doc__sphinx-8459 pylint-dev__pylint-6903 matplotlib__matplotlib-25311`; same harness, commit and settings as final-1; 14:11:03-14:42:31, exit 0. No method re-run. Only resolved/applied and the error signature were read; no patch or test content was printed.
- Result: gold UNRESOLVED on all 3 (applied=True, error_instances=0):
  - sphinx-8459: 0 tests parsed (18 unmatched); `No module named 'roman'` before and after the fix.
  - pylint-6903: 5 tests fail both before and after the fix; `UnknownMessageError 'c-extension-no-member'`.
  - matplotlib-25311: 12 tests fail both before and after the fix; setuptools_scm/vcs-versioning `release-branch-semver` DeprecationWarning.
- Conclusion: in today's harness-built environments even the reference fix can't make the reference tests pass for these repo versions. The "both fail" outcomes for those 13 instances measure the environment, not the methods.
- Root causes (from final-1 build logs): sphinx 3.4-4.0 get docutils 0.23 (the SWE-bench image used by the agent/wrapper had docutils 0.19); pylint 2.14/2.15 editable install with setuptools 80.9 makes astroid unable to find pylint's own checker modules ("Problem importing module ...: Unable to find module for /testbed/pylint/checkers/..."), so 'c-extension-no-member' is never registered; matplotlib 3.7 has setuptools-scm 10.3.4 + vcs-versioning 2.6.0 from conda next to the pip-pinned 7.1.0.

## 2026-11-14 — POST-HOC SENSITIVITY ANALYSIS, option C step 1: gold with harness-side fixes (run_id posthoc-gold-fixed-1)
- Patched harness COPY ~/se443/SWT-Bench-posthoc (rsync of the official checkout at be12d4c8, without .venv/logs). The official ~/se443/SWT-Bench is untouched; the official venv is reused, and PYTHONPATH points at the copy (verified that src is imported from the copy). Diff: results/final-1/posthoc/harness_posthoc_C1-C3.diff (20 lines appended to src/constants.py):
  - C1 sphinx 3.4/3.5/4.0: pre_install `sed` caps `docutils>=0.1x` -> `,<0.20` in setup.py (same style as the harness's existing Jinja2/sphinxcontrib pins). Covers `pip install -e .[test]` and tox's test-time venv.
  - C2 pylint 2.14/2.15: install = `pip install -e . --config-settings editable_mode=compat` (setuptools' path-based editable mode). Not a version pin: pinning setuptools<64 would hit the 'missing build_editable hook' error seen for pylint-7277 under current pip. compat restores the legacy .pth-style discovery.
  - C3 matplotlib 3.7: pre_install `pip uninstall -y vcs-versioning || true` (left over from conda's setuptools-scm 10 next to pip's setuptools-scm 7.1.0).
- Launcher: scripts/posthoc/run_swt_harness_posthoc.sh (a copy of the frozen run_swt_harness.sh with only the harness path changed; same settings: --filter_swt, max_workers 1, offline dataset). Frozen files untouched.
- Gold run 15:09:32-15:40:29, exit 0: ALL 3 RESOLVED, no error instances, no environment signature before or after the fix:
  - sphinx-8459: 1 F2P, 17 P2P.
  - pylint-6903: 1 F2P, 8 P2P.
  - matplotlib-25311: 1 F2P, 181 P2P, 1 F2F.
- Re-evaluation script prepared, NOT started (waiting for the user): scripts/posthoc/run_reeval_C.sh posthoc-c-1 (13 instances x 2 arms, unchanged harness_input.jsonl, input sha256 logged, sequential).

## 2026-11-14T15:44:36-06:00 — POST-HOC option C: decisions recorded BEFORE any re-evaluation result is read (user)
- GATING RULE: an instance counts in the sensitivity table only if ITS OWN gold patch resolves under the patched harness (~/se443/SWT-Bench-posthoc, diff harness_posthoc_C1-C3.diff). Instances whose gold does not resolve are reported as unevaluable in the sensitivity table, for both arms.
- Gold already resolved (posthoc-gold-fixed-1): sphinx-8459, pylint-6903, matplotlib-25311. Gold added for the other 10: sphinx 8475, 8548, 8551, 8593, 8595, 8621, 8638, 8721; pylint 6386, 7080.
- Order per instance: gold (if not done) -> baseline -> workflow; sequential; unchanged harness_input.jsonl with sha256 logged; run ids posthoc-c-1-{gold,baseline,workflow}-<iid>.
- C2 DEFINITION (accepted): pylint 2.14/2.15 install = `python -m pip install -e . --config-settings editable_mode=compat`. C1 = cap docutils <0.20 in setup.py for sphinx 3.4/3.5/4.0; C3 = `python -m pip uninstall -y vcs-versioning || true` for matplotlib 3.7. (Line repaired at ~15:45: the original write lost the backticked commands to shell expansion; the content was decided before the start and matches harness_posthoc_C1-C3.diff, sha256 cf493a18483236da.)
- No image removal (148 GB free). Official final-1 results stay primary and unchanged; this is a labeled sensitivity analysis.
- Script: scripts/posthoc/run_reeval_C.sh posthoc-c-1 (started detached right after this entry).

## 2026-11-14 — POST-HOC SENSITIVITY ANALYSIS, option C: results (posthoc-c-1). NOT the official result.
- Re-evaluation 15:44:36–18:25:05, 36/36 runs exit 0. Results were read only after it finished, at the user's request. The gating rule was logged before (commit 8213220).
- Gate: gold RESOLVED on all 13 instances under the patched harness (10 in posthoc-c-1, 3 in posthoc-gold-fixed-1). No instance excluded.
- Log check: 0 of 36 runs contain an old environment signature (strict patterns: roman, UnknownMessageError, release-branch-semver, missing build_editable hook).
- Sensitivity table (19 evaluable = 13 re-evaluated + 6 official usable; 6 still unevaluable, no fix tested):
  - Baseline 17/19 (17/25); workflow 18/19 (18/25). Applicability 19/19 in both arms.
  - Coverage delta: all 66.5% vs 71.2% (n=19); successful 65.4% (n=17) vs 69.6% (n=18).
  - Paired: both 17, baseline only 0, workflow only 1 (sympy-15017, official), neither 1 (sphinx-8595). Re-evaluated instances: 12 both, 1 neither.
- Official final-1 results stay primary and unchanged (5/25 vs 6/25).
- Files: results/final-1/posthoc/sensitivity_posthoc-c-1.{md,json}, scripts/posthoc/sensitivity.py, runs/posthoc/posthoc-c-1/.

## 2026-11-14 — Packaging and slide export; LIMITATION: single run only
- LIMITATION (user decision): final-1 is the ONLY run. Each arm was run once, and no second run will be done.
  There are no variance estimates. The one-instance difference between arms (sympy-15017) is not statistically
  distinguishable (exact McNemar test, 1 discordant pair: p = 1.0). It is listed as a limitation in the export and the README.
- Export: ~/se443/export-for-slides/ (outside the repo), generated by scripts/export_for_slides.py from committed results only.
  It reads no harness data and runs nothing new. Contents:
  - results_summary.md (official + post-hoc, clearly labeled);
  - official_summary_final-1.md, per_instance.csv, leaderboard.csv;
  - case_studies.md, sensitivity_posthoc-c-1.md;
  - final_tests_side_by_side.md: added lines only of both arms' final predictions for sympy-15017 and matplotlib-14623.
- Backups: ~/backups/ (repo zip without .git; export zip).
