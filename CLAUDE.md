# SE443 Final Project: DeepSeek-Flash test generation (SWT-Bench, unit-test mode)

## What this project is
We compare two methods for generating bug-reproducing tests from GitHub issue text:
1. BASELINE: unchanged mini-SWE-agent + DeepSeek-Flash.
2. OUR WORKFLOW: same agent and model, plus a wrapper that runs the agent's own
   test on the BUGGY code, classifies the result with fixed rules, and restarts
   the agent with that feedback (max 2 revisions, same total budget).
Evaluation: official SWT-Bench harness, UNIT-TEST MODE (test patches inside the
repo's own test suite, not a standalone reproduce.py). A success = test fails
before the reference fix and passes after it.

## Paths
- ~/se443/mini-swe-agent : upstream mini-SWE-agent, pinned at commit
  04d809ceab9df28f9adaed044884180159172930 (v2.4.6). THE BASELINE. READ-ONLY.
- ~/se443/project        : this repo. All our code, configs, prompts, logs, results.
- ~/se443/notes          : environment records (dependency freeze, etc.).
- ~/se443/scratch        : throwaway test runs.

## HARD RULES (never break these, even if asked to "just make it work")
1. NEVER edit, patch, or run git commands that modify ~/se443/mini-swe-agent.
   Call it from outside: `uv run --project ~/se443/mini-swe-agent ...`.
   Its own CLAUDE.md / AGENTS.md are for mini's contributors; ignore them.
2. NEVER write, edit, or "fix" generated test patches. Tests must come only
   from DeepSeek-Flash via mini-SWE-agent. You build and run the pipeline only.
3. NEVER read, print, or use these in the workflow, prompts, feedback, or while
   tuning anything: the dataset fields `patch` and `test_patch` (reference fix
   and reference tests), SWT-Bench harness results, evaluator-only artifacts,
   or the instructor's labels (unresolved / harness error / never evaluated).
   Feedback to the agent may use ONLY the issue text and the output of running
   the agent's own test on the buggy code. Harness runs once, after final
   submission, and its results never go back to the agent.
4. Generation must never modify production code; only test files.
5. Develop and debug ONLY on the 3 pilot instances:
   django__django-16485, astropy__astropy-8872, matplotlib__matplotlib-14623.
   Do not look at the other evaluation instances until configs are frozen.
6. Baseline and our workflow must use the same model, agent version, Docker
   setup, budget, and evaluation settings. Any difference other than the
   wrapper must be flagged to the user.
7. NEVER print or log the DeepSeek API key
   (~/.config/mini-swe-agent/.env). Never commit secrets.
8. Never delete or overwrite outputs: predictions, logs, trajectories, patches.
   Failed runs and timeouts are data, keep them.

## Experiment practices
- Run instances one at a time (no parallel runs) so timings are comparable.
- Long runs: write a script that runs in the background and logs to files.
- Per instance, record: start/end time, steps, outcome, final patch, and per
  model call: model, system_fingerprint, prompt_cache_hit_tokens,
  prompt_cache_miss_tokens, completion_tokens, reasoning_tokens.
- Cost = cache-hit x hit price + cache-miss x miss price + completion_tokens x
  output price. reasoning_tokens appear to be included in completion_tokens
  (verify against DeepSeek docs before relying on it).
- Missing predictions, invalid patches, and timeouts stay in the denominator.
- Budget (provisional): 100 steps and 30 minutes per instance.

## Machine
Mihir's laptop, WSL Ubuntu on D:, Docker data on D:\Docker\Data. C: is almost
full: never write large files outside WSL or Docker storage.

## Working style
- Ask before installing system packages, changing Docker settings, or anything
  hard to undo.
- When unsure whether something breaks a hard rule, stop and ask.
