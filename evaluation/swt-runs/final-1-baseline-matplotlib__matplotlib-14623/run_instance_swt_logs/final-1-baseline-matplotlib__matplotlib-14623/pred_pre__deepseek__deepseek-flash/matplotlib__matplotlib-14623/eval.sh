#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD d65c9ca20ddf81ef91199e6d819f9d3506ef477c >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff d65c9ca20ddf81ef91199e6d819f9d3506ef477c
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
diff --git a/lib/matplotlib/tests/test_scale.py b/lib/matplotlib/tests/test_scale.py
index e406b1b9a..483e89249 100644
--- a/lib/matplotlib/tests/test_scale.py
+++ b/lib/matplotlib/tests/test_scale.py
@@ -123,6 +123,20 @@ def test_logscale_invert_transform():
     assert isinstance(Log10Transform().inverted(), InvertedLog10Transform)
 
 
+def test_logscale_inverted_limits():
+    # Explicitly inverted limits should be preserved on log-scaled axes.
+    fig, ax = plt.subplots()
+    ax.set_yscale('log')
+    ax.set_ylim(100, 1)
+    assert ax.get_ylim() == (100, 1)
+    assert ax.yaxis_inverted()
+
+    ax.set_xscale('log')
+    ax.set_xlim(100, 1)
+    assert ax.get_xlim() == (100, 1)
+    assert ax.xaxis_inverted()
+
+
 def test_logscale_transform_repr():
     # check that repr of log transform succeeds
     fig, ax = plt.subplots()

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(lib/matplotlib/axes/_base\.py|lib/matplotlib/ticker\.py|lib/mpl_toolkits/mplot3d/axes3d\.py)' -m pytest --no-header -rA  -p no:cacheprovider lib/matplotlib/tests/test_scale.py
cat coverage.cover
git checkout d65c9ca20ddf81ef91199e6d819f9d3506ef477c
git apply /root/pre_state.patch
