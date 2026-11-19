#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 39f83765e12b0e5d260b7939fc3fe281d879b279 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 39f83765e12b0e5d260b7939fc3fe281d879b279
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
diff --git a/tests/template_tests/filter_tests/test_floatformat.py b/tests/template_tests/filter_tests/test_floatformat.py
index 361a888ce3..db8498ff1c 100644
--- a/tests/template_tests/filter_tests/test_floatformat.py
+++ b/tests/template_tests/filter_tests/test_floatformat.py
@@ -108,6 +108,8 @@ class FunctionTests(SimpleTestCase):
         self.assertEqual(floatformat(0, 6), "0.000000")
         self.assertEqual(floatformat(0, 7), "0.0000000")
         self.assertEqual(floatformat(0, 10), "0.0000000000")
+        self.assertEqual(floatformat("0.00", 0), "0")
+        self.assertEqual(floatformat(Decimal("0.00"), 0), "0")
         self.assertEqual(
             floatformat(0.000000000000000000015, 20), "0.00000000000000000002"
         )

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(django/template/defaultfilters\.py)' ./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 template_tests.filter_tests.test_floatformat
cat coverage.cover
git checkout 39f83765e12b0e5d260b7939fc3fe281d879b279
git apply /root/pre_state.patch
