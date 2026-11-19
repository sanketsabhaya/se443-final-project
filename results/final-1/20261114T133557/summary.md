# Results: final-1

N = 25 instances (denominator for every rate). Generated 2026-11-14T13:35:57.

## Main metrics

| Metric | Baseline | Workflow |
|---|---|---|
| Success (resolved) | 5/25 (20.0%) | 6/25 (24.0%) |
| Applicability | 19/25 (76.0%) | 19/25 (76.0%) |
| Coverage delta, all (instances with coverage) | 39.0% (n=16) | 41.0% (n=16) |
| Coverage delta, successful reproductions | 64.8% (n=5) | 77.4% (n=6) |
| Cost (fixed peak prices) | $0.4427 | $1.1149 |
| Model calls (of which in peak hours, info) | 429 (0) | 1022 (0) |
| Avg generation time | 77.8 s | 215.4 s |
| Total evaluation (harness) time | 326.4 min | 210.8 min |
| Unevaluated (harness infra failure; counted as failure) | 6 | 6 |
| Missing prediction | 0 | 0 |
| Invalid prediction (rule 4 / empty) | 0 | 0 |

Coverage delta: SWT-Bench per-instance fraction of the reference fix's executable changed lines whose execution count rises with the predicted tests; averaged over instances where it is available (N/A, not 0, when none).

## Paired outcomes

| | Workflow succeeds | Workflow fails |
|---|---|---|
| **Baseline succeeds** | 5 (both) | 0 (only baseline) |
| **Baseline fails** | 1 (only workflow) | 19 (neither) |

## Workflow wrapper

| Round | G1 | G2 | G3 | G4 | G5 | apply-check only |
|---|---|---|---|---|---|---|
| round_1 | 0 | 0 | 2 | 12 | 11 | 0 |
| round_2 | 0 | 0 | 2 | 12 | 0 | 0 |
| round_3 | 0 | 0 | 2 | 10 | 2 | 0 |

Instances revised: 14. Success among revised: 3/14 (21.4%); among not revised: 3/11 (27.3%).

## Retries and interruptions

| Event | Count |
|---|---|
| INFRA_RETRY_generation | 0 |
| HARNESS_RETRY_same_prediction | 13 |
| interruptions_moved_aside | 2 |

Reasoning tokens vs completion tokens: **included (completion_tokens = visible + reasoning)** ({"n_calls": 1451, "beta_reasoning": 1.007, "alpha_per_visible_char": 0.317, "implied_visible_chars_per_token": 3.15, "reasoning_le_completion_all": true}).

## Case-study candidates (sorted by instance ID)

- **successful_both** (5): django__django-16485, matplotlib__matplotlib-14623, matplotlib__matplotlib-20676, matplotlib__matplotlib-21568, sphinx-doc__sphinx-11510
- **unsuccessful_both** (19): astropy__astropy-8872, matplotlib__matplotlib-22719, matplotlib__matplotlib-22865, matplotlib__matplotlib-22871, matplotlib__matplotlib-23299, matplotlib__matplotlib-25311, pylint-dev__pylint-6386, pylint-dev__pylint-6903, pylint-dev__pylint-7080, pylint-dev__pylint-7277, sphinx-doc__sphinx-8459, sphinx-doc__sphinx-8475, sphinx-doc__sphinx-8548, sphinx-doc__sphinx-8551, sphinx-doc__sphinx-8593, sphinx-doc__sphinx-8595, sphinx-doc__sphinx-8621, sphinx-doc__sphinx-8638, sphinx-doc__sphinx-8721
- **methods_disagree** (1): sympy__sympy-15017

## Leaderboard rows

| Team | Method | Success Rate | Coverage | Applicability | Cost | Avg Generation Time |
|---|---|---|---|---|---|---|
| Mihir Barvaliya & Sanket Sabhaya | mini-SWE-agent + DeepSeek-Flash (baseline) | 20.0% | 39.0% | 76.0% | $0.4427 | 77.8 s |
| Mihir Barvaliya & Sanket Sabhaya | mini-SWE-agent + DeepSeek-Flash + execution-feedback wrapper | 24.0% | 41.0% | 76.0% | $1.1149 | 215.4 s |
