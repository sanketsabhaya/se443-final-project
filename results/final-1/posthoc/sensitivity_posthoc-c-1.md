# POST-HOC SENSITIVITY ANALYSIS: final-1 re-evaluated with harness environment fixes C1-C3

**This is not the official result.** The official final-1 numbers (results/final-1/20261114T133557) stay primary and unchanged.
This table re-evaluates both arms' *unchanged* final-1 predictions after fixing harness-side environment breakage.
Nothing was regenerated, and nothing went back to the agent or the wrapper.

- Patched harness: ~/se443/SWT-Bench-posthoc, diff `harness_posthoc_C1-C3.diff` (sha256 cf493a18483236da). C1 caps sphinx 3.4–4.0 docutils at <0.20; C2 uses compat editable installs for pylint 2.14/2.15; C3 removes the stray vcs-versioning package for matplotlib 3.7.
- Runs: `posthoc-c-1-{gold,baseline,workflow}-<iid>` (36 runs, 15:44–18:25, all exit 0) plus gold from `posthoc-gold-fixed-1`.
- Gating rule (logged before any result was read, commit 8213220): an instance counts only if its own gold patch resolves under the patched harness.
- Per instance, the evaluation source is one of:
  - **Patched re-evaluation:** the 13 instances with broken environments, if they pass the gate.
  - **Official final-1 verdicts:** the 6 instances that already had usable verdicts.
  - **Unevaluable for both arms:** the 6 instances that were unevaluated in final-1, for which no fix was tested (astropy-8872, matplotlib 22719/22865/22871/23299, pylint-7277).
- Check: none of the 36 runs' logs contains any old environment signature (`No module named 'roman'`, `UnknownMessageError`, `release-branch-semver`, `missing the 'build_editable' hook`).

## Gold under the patched harness (gate)
All 13 resolved: pylint 6386, 6903, 7080; matplotlib 25311; sphinx 8459, 8475, 8548, 8551, 8593, 8595, 8621, 8638, 8721.
**The gate excludes no instance.** No gold patch failed to resolve.

## Results

| Metric | Official final-1: Baseline | Official final-1: Workflow | POST-HOC: Baseline | POST-HOC: Workflow |
|---|---|---|---|---|
| Evaluable instances | 6 usable verdicts (19 had a report) | 6 usable verdicts (19 had a report) | 19 | 19 |
| Success / 25 | 5/25 (20.0%) | 6/25 (24.0%) | 17/25 (68.0%) | 18/25 (72.0%) |
| Success / evaluable | — | — | 17/19 (89.5%) | 18/19 (94.7%) |
| Applicability | 19/25 | 19/25 | 19/19 | 19/19 |
| Coverage delta, all with coverage | 39.0% (n=16) | 41.0% (n=16) | 66.5% (n=19) | 71.2% (n=19) |
| Coverage delta, successful | 64.8% (n=5) | 77.4% (n=6) | 65.4% (n=17) | 69.6% (n=18) |

## Paired outcomes

| | Official (n=25) | POST-HOC (evaluable, n=19) |
|---|---|---|
| Both succeed | 5 | 17 |
| Baseline only | 0 | 0 |
| Workflow only | 1 (sympy-15017) | 1 (sympy-15017) |
| Neither | 19 | 1 (sphinx-8595) |

## Reading
- Of the 13 re-evaluated instances, 12 succeed in **both** arms and 1 fails in both (sphinx-8595). The re-evaluation adds no discordant pair.
- The one difference between arms is still sympy-15017, from the official run. Exact McNemar test on 1 discordant pair: p = 1.0.
- Without the environment fixes, the official harness made both arms look much weaker (5–6 out of 25). The gold-patch gate shows the low official numbers came from the environment, not the methods.
- The workflow's extra cost buys no measurable gain on this sample: $1.11 against $0.44, and 1022 model calls against 429.
- sphinx-8548 and 8638 have byte-identical predictions in both arms (same input sha256), and both arms agree on them.
- Machine-readable output: `sensitivity_posthoc-c-1.json`, produced by `scripts/posthoc/sensitivity.py posthoc-c-1 --confirm-read-harness`.
