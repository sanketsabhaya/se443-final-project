#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 3c5eca2ded3dd2b59ebaf23eb289453b5d2930f0 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 3c5eca2ded3dd2b59ebaf23eb289453b5d2930f0
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
diff --git a/pylint/lint/expand_modules.py b/pylint/lint/expand_modules.py
--- a/pylint/lint/expand_modules.py
+++ b/pylint/lint/expand_modules.py
@@ -52,6 +52,7 @@ def _is_ignored_file(
     ignore_list_re: list[Pattern[str]],
     ignore_list_paths_re: list[Pattern[str]],
 ) -> bool:
+    element = os.path.normpath(element)
     basename = os.path.basename(element)
     return (
         basename in ignore_list

EOF_114329324912
git apply -v - <<'EOF_114329324912'
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(pylint/lint/expand_modules\.py)' -m pytest --no-header -rA  -p no:cacheprovider tests/test_self.py
cat coverage.cover
git checkout 3c5eca2ded3dd2b59ebaf23eb289453b5d2930f0
git apply /root/pre_state.patch
