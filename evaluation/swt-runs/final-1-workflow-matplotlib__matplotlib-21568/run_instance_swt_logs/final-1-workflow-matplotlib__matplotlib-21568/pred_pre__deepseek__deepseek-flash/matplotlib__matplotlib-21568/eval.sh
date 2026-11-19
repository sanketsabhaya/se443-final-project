#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD f0632c0fc7339f68e992ed63ae4cfac76cd41aad >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff f0632c0fc7339f68e992ed63ae4cfac76cd41aad
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
diff --git a/lib/matplotlib/tests/test_dates.py b/lib/matplotlib/tests/test_dates.py
index 96a3db1730..e78df13ba5 100644
--- a/lib/matplotlib/tests/test_dates.py
+++ b/lib/matplotlib/tests/test_dates.py
@@ -341,6 +341,14 @@ def test_date_formatter_usetex(delta, expected):
     assert [formatter(loc) for loc in locator()] == expected
 
 
+def test_date_formatter_usetex_spacing():
+    # Test that separators in datetime labels are not spaced like TeX
+    # binary operators (see issue #21518).
+    formatter = mdates.DateFormatter("%d %H:%M", usetex=True)
+    result = formatter(mdates.date2num(datetime.datetime(2020, 1, 1)))
+    assert result == r'$\mathdefault{01\;00{:}00}$'
+
+
 def test_drange():
     """
     This test should check if drange works as expected, and if all the

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(lib/matplotlib/dates\.py)' -m pytest --no-header -rA  -p no:cacheprovider lib/matplotlib/tests/test_dates.py
cat coverage.cover
git checkout f0632c0fc7339f68e992ed63ae4cfac76cd41aad
git apply /root/pre_state.patch
