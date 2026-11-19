# SE443 final project: issue-to-test generation with DeepSeek-Flash on SWT-Bench Verified (unit-test mode)

Authors: Mihir Barvaliya & Sanket Sabhaya.

This project compares two arms on the same 25 SWT-Bench Verified instances (`configs/eval_instances.txt`):

1. **Baseline:** unchanged mini-SWE-agent with DeepSeek-Flash.
2. **Workflow:** the same agent and model, plus a wrapper. The wrapper runs the agent's own test on the buggy code, classifies the result (G1–G5), and restarts the agent with feedback, up to 2 revisions within the same budget. The procedure is in `docs/workflow-procedure.md`.

Both arms are evaluated with the official SWT-Bench harness in unit-test mode. A **success** is a test that fails before the reference fix and passes after it, and that changes test files only.

## Results at a glance

| | Baseline | Workflow |
|---|---|---|
| **Official final-1** (`results/final-1/latest/`) | 5/25 | 6/25 |
| **Post-hoc sensitivity, patched harness** (`results/final-1/posthoc/sensitivity_posthoc-c-1.md`) | 17/19 evaluable | 18/19 evaluable |

- The official result is primary. The post-hoc table is labelled as such and is explained further down.
- Cost: $0.44 for the baseline and $1.11 for the workflow, with 429 and 1022 model calls.
- Analysis and case studies are in `results/final-1/case_studies.md`.

## Repository layout

| Path | Contents |
|---|---|
| `configs/` | `unit_test_gen.yaml` (the agent config for both arms; frozen) and `eval_instances.txt` |
| `scripts/` | The baseline and workflow launchers, the full-run driver, the harness launcher, the results script, and `posthoc/` |
| `runs/` | Every generation output: `baseline/`, `workflow/`, and `experiment/final-1/` (driver log, status, harness markers, watchdog log), plus `posthoc/` |
| `evaluation/swt-runs/` | Copies of the harness run folders for final-1, posthoc-gold-1, posthoc-gold-fixed-1 and posthoc-c-1 (see the note below) |
| `results/final-1/` | The official summary, CSVs, leaderboard, case studies, and `posthoc/` |
| `notes/progress-log.md` | A dated log of every decision, check and intervention |
| `notes/environment/` | Environment records: SWT-Bench commit, venv freeze, dataset revision, mini-swe-agent freeze |
| `docs/` | The workflow design (rationale) and the procedure (as frozen) |

**Note on `evaluation/swt-runs/`:**
- The per-instance harness logs include the reference test patches and the gold runs, because the harness uses them internally. They are evaluator-only artifacts, and the generation pipeline never read them.
- Each run's `dataset` entry is a symlink to the local harness checkout, so the dataset itself is not copied. On another machine those links dangle.

## Environment (as used)

| Component | Version / location |
|---|---|
| OS | Windows + WSL2 3.0.5.0 (kernel 6.18.58.1), Ubuntu 26.04.1 LTS |
| Docker | Docker Desktop 29.9.3, WSL2 backend, data on `D:\Docker\Data`; 16 CPUs |
| WSL memory | 7.5 GB at the start, raised to 12 GB during final-1 (see Interventions) |
| uv | 0.13.8 |
| mini-swe-agent | `~/se443/mini-swe-agent`, commit `04d809ceab9df28f9adaed044884180159172930` (v2.4.6). Used unmodified and read-only. |
| SWT-Bench harness | `~/se443/SWT-Bench`, commit `be12d4c8e7a5315a6bd60b0cad72736e96a4af3e`; venv from `uv sync --frozen --python 3.11` (Python 3.11.18). Used unmodified. |
| Dataset | `princeton-nlp/SWE-bench_Verified` (test split), HF revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`, with `--filter_swt` (433 instances). Runs use `HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1`, so the cached snapshot is always used. |
| Model | `deepseek/deepseek-flash` (DeepSeek API, default thinking mode; no temperature or seed sent) |

The scripts assume the layout `~/se443/{project,mini-swe-agent,SWT-Bench,swt-runs}`.

### Setup
1. Install WSL2 and Ubuntu, and Docker Desktop with WSL integration turned on. Your user must be in the `docker` group.
   Give WSL at least 12 GB of memory (`%UserProfile%\.wslconfig`: `[wsl2]` and `memory=12GB`).
2. Install uv.
3. Clone and pin mini-swe-agent, then run `uv sync --frozen` in it:
   `git clone https://github.com/SWE-agent/mini-swe-agent ~/se443/mini-swe-agent && git -C ~/se443/mini-swe-agent checkout 04d809ce`
4. Clone and pin SWT-Bench:
   `git clone https://github.com/logic-star-ai/SWT-Bench ~/se443/SWT-Bench && git -C ~/se443/SWT-Bench checkout be12d4c8`.
   Then run `cd ~/se443/SWT-Bench && uv sync --frozen --python 3.11`.
5. Download the dataset snapshot once with network access, at revision `c104f840`.
6. **DeepSeek API key:** put it in `~/.config/mini-swe-agent/.env`. The file holds `DEEPSEEK_API_KEY=...`, `MSWEA_MODEL_NAME=deepseek/deepseek-flash` and `MSWEA_COST_TRACKING=ignore_errors`.
   The key lives only in that file. It is **never committed or logged**, and new outputs were scanned for it before each commit.

## How to run

All commands run from `~/se443/project`. Run one instance at a time; nothing runs in parallel.

| Step | Command | Output |
|---|---|---|
| Baseline, one instance | `scripts/run_baseline.sh <run_id> <instance_id>` | `runs/baseline/<run_id>/<iid>/` |
| Workflow, one instance | `scripts/run_workflow.sh <run_id> <instance_id>` | `runs/workflow/<run_id>/<iid>/` |
| Harness, one prediction file | `scripts/run_swt_harness.sh <harness_run_id> <preds.jsonl\|gold> [iid ...]` | `~/se443/swt-runs/<harness_run_id>/` |
| **Full experiment** | `scripts/start_experiment.sh final-1` (detached; resume by running the same command again) | `runs/experiment/final-1/` (`driver.log`, `status.tsv`, `harness_final/`) |
| Results | `python3 scripts/results.py final-1 --team "Mihir Barvaliya & Sanket Sabhaya" --confirm-read-harness` | `results/final-1/<timestamp>/` and `latest` |

**How the driver works:**
- Instances run in sorted order. For each instance: baseline generation, then workflow generation, then a harness run for each arm on its `harness_input.jsonl`.
- Resume rules: an arm with `done.json` is skipped. Incomplete folders are moved to `*.interrupted-<ts>`, never deleted.

**Retry rules:**
- **Generation:** retried only after an infrastructure crash, meaning no `done.json` was written. Agent limits, API errors and bad patches are never retried.
- **Harness:** reruns only the unchanged prediction (same sha256), and only if the run is incomplete, exits non-zero, or reports error instances.
- Each has at most 2 attempts.

**Scoring rules:**
- Missing predictions, invalid predictions and timeouts stay in the denominator.
- Harness errors count as failures for both arms. This is option A, decided by the user on 2026-11-14.

## Frozen files (tag `freeze-1`, commit `f8772f5`)
These files were not changed after the freeze. The sha256 values were rechecked after every step.

```
eb3e1ccd8a5a1d024c4f320c36a814baeaa9b74e7fbbb88d1033c80186040902  configs/unit_test_gen.yaml
77e4b3795bc8522b43fb75a06194d3b73f0181ab679987964609315845094de3  scripts/run_workflow.py
b6714e87713e1098707b6b8fec643b53ff2ac8fc3fcd56e79c6f4c69ba8378a1  scripts/run_baseline.sh
07d04557399848328f6a75f24cc3b01d7d619a54cc2abdaa63f41b01faea4a3f  scripts/check_test_only.py
0430fdbfba624090df319e5cc6c9d858386b05a1a1be587021ebe0e7bab0a0d2  scripts/run_experiment.py
7218cd7c12ff1c4b14ececffb85324865c7624c50dc6e57dc8c655ef6d254eb6  scripts/run_swt_harness.sh
```
Check with `sha256sum -c` against this list, or `git diff freeze-1 -- configs scripts/run_*.py scripts/run_*.sh scripts/check_test_only.py`.

## Infrastructure interventions during final-1
final-1 ran from 2026-11-13 19:05:48 to 2026-11-14 13:28:42 (times are local, UTC−6). Details are in `notes/progress-log.md`.
None of these interventions changed a frozen file or redid a generation.

1. **WSL memory, about 21:44–21:52, instance 6 (matplotlib-22719):**
   - A harness `conda-env create` build hung for 47 minutes or more, and its memory use kept rising. The user killed the container and paused the driver.
   - The user raised WSL memory from 7.5 GB to 12 GB, ran `wsl --shutdown` and restarted Docker Desktop. The driver resumed at 21:51:48.
   - Instances 1–5, and the generation for instance 6, ran under 7.5 GB. Every later step ran under 12 GB.
2. **Watchdog, 23:02 to about 13:35** (`scripts/watchdog_conda.sh`, not frozen and not part of the method):
   - It killed harness containers stuck in `conda-env create` for more than 30 minutes. It made 14 kills, all on matplotlib 3.5 environment builds (22719, 22865, 22871, 23299), the last at 06:45.
   - Those instances ended unevaluated for both arms.
3. **Network change, from just after 08:59:28 to 09:50:07:**
   - The laptop moved to a different network. The user paused the driver and the watchdog. No generation was running at the time.
   - One harness attempt (sphinx-11510, baseline) was moved aside and rerun on the same prediction.

Interventions 1 and 3 are the two interruptions counted in the results.
All 13 `HARNESS_RETRY_same_prediction` entries in `runs/experiment/final-1/status.tsv` fall on the six instances below, where the harness image build failed.

**Unevaluated in both arms:** astropy-8872, matplotlib 22719, 22865, 22871 and 23299, and pylint-7277. Their harness environment images failed to build.

## Post-hoc sensitivity analysis (option C), not the official result
**Why:**
- After final-1, gold-patch runs on the official harness (`posthoc-gold-1`) failed to resolve sphinx-8459, pylint-6903 and matplotlib-25311.
- The cause was the environment breaking, not the predictions:
  - docutils 0.23 removed the `roman` module that sphinx 3.x/4.0 needs;
  - setuptools 80.9's editable install hides pylint's own checker modules;
  - a stray vcs-versioning package raises a DeprecationWarning in matplotlib 3.7.
- So the 13 instances where both arms failed measured the environment, not the methods.

**Patch:**
- Applied to a **separate copy** of the harness, `~/se443/SWT-Bench-posthoc`. The official checkout is untouched.
- Diff: `results/final-1/posthoc/harness_posthoc_C1-C3.diff` (sha256 `cf493a18483236da…`), which adds 20 lines to `src/constants.py`:
  - **C1, sphinx 3.4/3.5/4.0:** caps `docutils` at `<0.20` in `setup.py`.
  - **C2, pylint 2.14/2.15:** installs with `python -m pip install -e . --config-settings editable_mode=compat`.
  - **C3, matplotlib 3.7:** runs `python -m pip uninstall -y vcs-versioning || true`.
- Launchers: `scripts/posthoc/run_swt_harness_posthoc.sh` (the frozen harness launcher with only the harness path changed) and `scripts/posthoc/run_reeval_C.sh`.

**Gating rule** (pre-registered: logged in commit `8213220` before any re-evaluation result was read):
- An instance counts in the sensitivity table only if **its own gold patch resolves** under the patched harness.
- Otherwise it is unevaluable for both arms.
- Both arms' **unchanged** final-1 predictions were re-evaluated, the same `harness_input.jsonl` files with their sha256 logged. Nothing was regenerated, and nothing went back to the agent.

**Outcome** (`posthoc-c-1`, 36 runs):
- Gold resolved on 13 of 13 instances, so none was excluded. No old environment signature appears in any log.
- Baseline 17/19 and workflow 18/19 evaluable (17/25 and 18/25).
- Paired: 17 both succeed, 0 baseline only, 1 workflow only (sympy-15017, the same as in the official run), 1 neither (sphinx-8595).
- No fix was tested for the six unevaluated instances, so they stay unevaluable.

**To reproduce:**
1. Copy the harness: `rsync -a --exclude .venv --exclude logs ~/se443/SWT-Bench/ ~/se443/SWT-Bench-posthoc/`.
2. Apply the diff: `git -C ~/se443/SWT-Bench-posthoc apply ~/se443/project/results/final-1/posthoc/harness_posthoc_C1-C3.diff`.
3. Re-evaluate: `scripts/posthoc/run_reeval_C.sh posthoc-c-1`.
4. Build the table: `python3 scripts/posthoc/sensitivity.py posthoc-c-1 --confirm-read-harness`.

## Limitations
- **Single run:** each arm was run once (final-1), and no second run will be done. There are no variance estimates, and the one-instance difference between arms (sympy-15017) is not statistically distinguishable (exact McNemar test: p = 1.0).
- **Official numbers depressed by the harness environment:** the official numbers are lowered by harness environment breakage, and the post-hoc table is a sensitivity analysis, not a replacement.
- **Wrapper classifier bugs (F1–F4):** these bugs mean the revision mechanism was barely exercised (`docs/workflow-procedure.md`).
- **Unevaluable instances:** six instances are unevaluable in both arms.

## Rules followed
These come from `CLAUDE.md`:
- mini-swe-agent is never modified.
- Generated tests are never edited.
- The pipeline never reads `patch`, `test_patch`, harness results or instructor labels.
- Generation changes test files only.
- The API key is never logged or committed.
- Outputs, including failed and interrupted runs, are never deleted.
