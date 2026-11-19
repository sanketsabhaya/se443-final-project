# final-1 case studies (post-hoc analysis)

Written 2026-11-14 after final-1 finished, with the user's approval to read harness results. Read-only analysis: no
result changed, nothing re-run. Harness information used: `resolved`, `patch_successfully_applied`,
`coverage_delta_pred`, the predicted tests' own before/after transitions (`tests_pred`), and the predicted
tests' output in `pred_pre` / `pred_post`. No reference fix, reference tests, or `tests_gold` were read.

Selection rule: the first two instances by ID in each paired category, skipping unevaluated instances. Added:
sympy-15017 (the only disagreement) and sphinx-11510 (diagnostic pick).

| Category | Picks |
|---|---|
| Both succeed | django-16485, matplotlib-14623 |
| Both fail (evaluated) | matplotlib-25311, pylint-6386 |
| Disagree | sympy-15017 (workflow only) |
| Diagnostic | sphinx-11510 (both succeed; wrapper said G4 three times) |

"Before" = predicted test on the buggy code, "after" = with the reference fix (harness `pred_pre` / `pred_post`).
F2P = fails before, passes after.

---

## 1. django__django-16485: both succeed

**Issue.** `floatformat("0.00", 0)` and `floatformat(Decimal("0.00"), 0)` raise
`ValueError: valid range for prec is [1, MAX_PREC]`.

**Tests.** Both arms add the same two assertions to the existing `FunctionTests.test_zero_values`; only their position in the test differs:
```python
self.assertEqual(floatformat("0.00", 0), "0")
self.assertEqual(floatformat(Decimal("0.00"), 0), "0")
```
- The baseline puts them in the middle of the test.
- The workflow puts them at the end.

**Harness.** Both arms: `test_zero_values` F2P, 9 other tests pass before and after, resolved.
- Coverage delta is 50% (baseline) vs 100% (workflow), even though the assertions are identical.

**Workflow.** 1 round, G5 (ValueError named in the issue). No revision.

**Represents the issue?** Yes. These are the issue's two reproduction calls, written as assertions on the expected result.

**What it reveals.** When an issue gives an exact crash recipe, both arms converge on the same test, and the wrapper only adds the cost of its check. Coverage delta depends on where the test lines sit, not only on what they test, so small coverage differences on few instances should not be read as test quality.

---

## 2. matplotlib__matplotlib-14623: both succeed

**Issue.** Since 3.1.0, `ax.set_ylim(max, min)` no longer inverts a log-scaled axis. It still works for linear axes.

**Baseline test.** A new `test_scale.py::test_logscale_inverted_limits`:
```python
ax.set_yscale('log'); ax.set_ylim(100, 1)
assert ax.get_ylim() == (100, 1)
assert ax.yaxis_inverted()
```
The same checks are repeated for x.

**Workflow test.** Final round 3, `test_axes.py::test_inverted_limits_via_set_lim`, parametrized over axis {x, y} and scale {linear, log}:
```python
result = getattr(ax, f'set_{axis}lim')(*limits)
assert result == limits
assert getattr(ax, f'get_{axis}lim')() == limits
assert getattr(ax, f'{axis}axis_inverted')()
```

**Harness.**
- **Baseline:** its test is F2P. One existing image test, `test_log_scales[pdf]`, fails both before and after the fix.
- **Workflow:** `[log-x]` and `[log-y]` are F2P, and the linear variants pass both before and after, which makes them a built-in control. 179 existing image-comparison tests in `test_axes.py` fail in this environment both before and after the fix. None of them come from the patch.
- **Both arms resolved.** Coverage delta is 85.7% (baseline) vs 14.3% (workflow).

**Workflow rounds.** G3, G3, G3, stop at `max_revisions`. **The G3 label is wrong.**
- In every round the wrapper's own run shows `[log-x]` and `[log-y]` FAILED with
  `AssertionError: assert (1.0, 100.0) == (100, 1)`, and `[linear-*]` PASSED.
- The classifier keeps only the first parametrization that matches the target (`[linear-x]`, PASSED). As a result, the agent was told twice that "All of your tests PASS on the current, unfixed code", which was false.
- The tests the wrapper selected and the test in the final patch are the same: `lib/matplotlib/tests/test_axes.py::test_inverted_limits_via_set_lim`.
- Re-classified offline with parametrizations combined, every round is G5, so the workflow would have stopped after round 1.

**Represents the issue?** Yes. It reverses the limits on a log axis and checks that the axis is inverted, which is the issue's scenario. The linear cases are a useful control.

**What it reveals.** A classifier bug with parametrized tests turned a correct test into false feedback. That cost two revisions, and the run could have ended with a worse test. Here the agent kept a correct test, so the outcome did not change.

---

## 3. matplotlib__matplotlib-25311: both fail (evaluated)

**Issue.** `pickle.dumps(fig)` fails with `TypeError: cannot pickle 'FigureCanvasQTAgg' object` once a legend or annotation is made draggable.

**Baseline test.** A new `test_pickle.py::test_pickle_draggable_artist`, parametrized over legend and annotation:
- it gives the figure an unpicklable canvas subclass (`__reduce__` raises TypeError),
- makes the artist draggable,
- then runs `pickle.loads(pickle.dumps(fig))`.

**Workflow test.** Round 1: `test_pickle_draggable[legend|annotation]`.
- It uses the same unpicklable-canvas idea, raising in `__getstate__`.
- After the round trip it asserts that the artist is still draggable.

**Harness.** Unresolved in both arms. No test is F2P; all 14 `test_pickle.py` tests fail both before and after the fix, existing tests included.
- In the harness environment, every test errors with `DeprecationWarning: Version scheme 'release-branch-semver' has been renamed to 'semver-pep440-release-branch'`. It comes from the newer setuptools_scm, and the test configuration turns warnings into errors.
- This is an environment failure, and it looks the same in both arms before and after the fix.

**Workflow.** 1 round, G5. In the wrapper's environment (the prebuilt SWE-bench image that mini also uses), the test failed with TypeError, which the issue names.

**Represents the issue?** Yes for both arms, judged by reading them. Each re-creates the issue's situation (a canvas that can't be pickled, a draggable artist, a pickle round trip). The workflow test also checks that dragging survives the round trip. The harness gives no evidence either way.

**What it reveals.** The harness verdict here reflects the harness's freshly built environment, not test quality. The wrapper ran the agent's test in a different, working environment.

---

## 4. pylint-dev__pylint-6386: both fail (evaluated)

**Issue.** `pylint mytest.py -v` fails with `error: argument --verbose/-v: expected one argument`. The short option expects a value, but the long option `--verbose` does not.

**Baseline test.** In `test_argparse_config.py`:
```python
run = Run([EMPTY_MODULE, "-v"], exit=False)
assert run.verbose
```

**Workflow test.** Final round 3, `test_config.py::test_short_verbose`:
- it runs `Run([..., "-v"], exit=False)`,
- catches `SystemExit` and asserts that `exc.code == 0`, with pylint's stderr in the failure message,
- otherwise asserts `runner.verbose`.

**Harness.** Unresolved in both arms. Every test in the affected files fails both before and after the fix, existing ones included, with
`UnknownMessageError: No such message id or symbol 'c-extension-no-member'`. That is a mismatch between the environment and the repository, the same in both arms (it also hits pylint-6903 and pylint-7080).

**Workflow rounds.** G4, G4, G5.
- **Rounds 1 and 2:** the wrapper's output shows exactly the issue's error, `argparse.ArgumentError: argument --verbose/-v: expected one argument`. argparse turns that into `SystemExit` (round 1) and pytest reports it as `Failed` (round 2).
- **Why G4:** neither SystemExit nor ArgumentError is named in the issue, which quotes the message, not an exception class. This is a limit of the fixed rules, not a parsing bug. Offline re-classification gives the same labels.
- **Round 3:** the agent turned the exit into an assertion, which the classifier accepted as G5.

**Represents the issue?** Yes. Both tests run `-v` without a value. The workflow version also gives a readable failure message.

**What it reveals.**
1. Some bugs show up as a CLI exit rather than a named exception, and the rule "exception named in the issue" misses them.
2. The feedback did push the agent toward a cleaner, assertion-based test. We can't tell whether that helps, because the harness environment is broken for pylint.

---

## 5. sympy__sympy-15017: disagreement (workflow only)

**Issue.** `len(sympy.Array(3))` returns 0, while `len(list(a))` is 1. It should be 1, as in numpy.

**Baseline test.**
- In the existing `test_ndim_array_initiation`, it changes `assert len(rank_zero_array) == 0` to `== 1`. It keeps the existing line `raises(ValueError, lambda: rank_zero_array[0])`.
- It also adds `test_rank_zero_array_len` (`assert len(Array(3)) == 1`).

**Workflow test.** Final round 3, the same edit in `test_ndim_array_initiation`, but it also replaces the `raises(ValueError, ...)` line with `assert rank_zero_array[0] == x`:
```python
-    assert len(rank_zero_array) == 0
+    assert len(rank_zero_array) == 1
+    assert len(list(rank_zero_array)) == 1
-    raises(ValueError, lambda: rank_zero_array[0])
+    assert rank_zero_array[0] == x
```

**Harness.**
- **Baseline:** `test_rank_zero_array_len` is F2P, but `test_ndim_array_initiation` fails both before and after the fix. After the fix it fails with `AssertionError: DID NOT RAISE`: the fixed code makes `rank_zero_array[0]` work, so the kept `raises(...)` line fails. Unresolved.
- **Workflow:** `test_ndim_array_initiation` is F2P. Resolved. Coverage delta is 50% in both arms.

**Workflow rounds.** G4, G4, G4, stop at `max_revisions`. **These labels are wrong.**
- The wrapper's own output shows a plain `AssertionError` at `assert len(rank_zero_array) == 1`.
- sympy 1.2's test runner prints each failure's header on two lines (a line of underscores, then the test name). The classifier only recognizes `____ name ____` headers, so it found no failure type.
- Re-classified offline with that format handled, all rounds are G5.
- **The final test is identical to round 1.** The changed lines in rounds 1 and 3 hash the same; round 2 differed, and round 3 went back to it.

**Represents the issue?** Yes for both. But the baseline test also kept checking old behavior (indexing a rank-0 array raises) that a correct fix changes. That is why the baseline failed after the fix.

**What it reveals.** The only paired difference in final-1 comes from what the two independent agent runs produced in their first attempt. The feedback played no part.
- With correct classification, the workflow would have stopped at round 1 with the same test.
- The two false G4 rounds changed nothing in the end.
- So this win should not be credited to the feedback loop.

---

## 6. sphinx-doc__sphinx-11510: diagnostic (both succeed, wrapper said G4 three times)

**Issue.** Changes a `source-read` event handler makes to a document are lost for files pulled in with `.. include::`.

**Baseline test.** `test_build_html.py::test_source_read_event_for_included_file`:
- it writes a `conf.py` whose `source-read` handler replaces `&REPLACE_ME;`,
- plus an `index.rst` that includes a second file containing the same marker,
- builds, and checks that the marker was replaced in the included content too.

**Workflow test.** Final round 3, identical to round 1:
- a new test root `test-directive-include` (`baz/baz.rst`, `foo.rst`, `text.txt`, `conf.py`),
- and `test_directive_other.py::test_include_source_read_event` plus `..._nested_includes`, which connect a `source-read` handler and assert which included documents it saw, with literal includes excluded.

**Harness.**
- **Baseline:** its test is F2P, and one existing test, `test_html_code_role`, fails both before and after the fix.
- **Workflow:** both tests are F2P.
- **Both arms resolved.** Coverage delta is 83.3% (baseline) vs 100% (workflow).

**Workflow rounds.** G4, G4, G4, stop at `max_revisions`. **These labels are wrong.**
- The wrapper's runs show both targets FAILED with plain `AssertionError`s.
- Sphinx's tox setup makes pytest print in colour, and the colour codes stop the patterns that find the failure type from matching. So it was reported as "unknown error", and the feedback read "fails, but not in a way related to the issue".
- Re-classified offline with the colour codes stripped, all rounds are G5.

**Represents the issue?** Yes for both. Each sets up an included file and checks that the `source-read` handler reaches it.

**What it reveals.** Every sphinx instance in final-1 had this bug. Each one used both revisions because of false feedback, which explains much of the workflow's extra cost and time. Here the final test happened to equal the first one.

---

## Cross-cutting findings

**1. Wrapper failure-type extraction had four bugs**, all on the input side of the fixed rules:
- **F1, colour codes:** ANSI colour codes in tox/pytest output (every sphinx instance).
- **F2, sympy headers:** sympy 1.2's two-line failure headers (sympy-15017).
- **F3, long test names:** pytest shortens the header to a single underscore on each side for very long parametrized names (sphinx-8621, round 2).
- **F4, parametrized tests:** only the first matching parametrization is checked (matplotlib-14623, 22865, sphinx-8621 round 3).

Re-running the wrapper's own `classify()` offline on the saved outputs with F1–F4 handled:
- **13 of the 14 revised instances would have been G5 in round 1**, and the workflow would have stopped there.
- **pylint-6386 is the only revision the rules really called for:** SystemExit and Failed are not exceptions named in the issue.
- **Revisions did change the tests:** 9 of the 13 falsely revised instances ended with a different test from round 1. The other 4 (sympy-15017, sphinx-11510, -8548, -8638) ended with exactly the round-1 test: the changed lines hash the same, and round 3 went back to it after round 2.
- **We can't know what the harness would have said** for the round-1 tests that differ from the final ones; they were not evaluated.

**2. The harness environment, not the tests, decided most "both fail" outcomes.** All 13 evaluated instances where both arms failed show an environment failure in both arms, before and after the fix:
- **Sphinx 3.x/4.0 (9 instances):** `ModuleNotFoundError: No module named 'roman'`. The test modules can't even be imported (for example `collected 0 items / 1 error`), and most of these runs report no test results at all.
- **pylint 6386, 6903, 7080:** `UnknownMessageError: 'c-extension-no-member'`.
- **matplotlib-25311:** the setuptools_scm DeprecationWarning, turned into an error.

Together with the 6 unevaluated instances, **only 6 of the 25 instances have a usable harness verdict**: django-16485, matplotlib-14623, -20676, -21568, sphinx-11510 and sympy-15017. On those 6, the baseline succeeds on 5 and the workflow on 6.

**3. The two environments differ.** The wrapper and the agent ran tests in the prebuilt SWE-bench images, where these test suites work. The SWT-Bench harness builds fresh images from today's package indexes, where they don't. Neither arm saw harness output, so the two arms were treated the same, but absolute success rates are strongly understated.
