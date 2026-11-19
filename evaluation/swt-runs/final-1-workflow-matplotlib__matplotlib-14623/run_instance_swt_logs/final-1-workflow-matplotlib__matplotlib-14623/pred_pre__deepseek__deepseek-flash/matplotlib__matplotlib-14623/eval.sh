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
diff --git a/lib/matplotlib/tests/test_axes.py b/lib/matplotlib/tests/test_axes.py
index 06ff5aca4..9acffd966 100644
--- a/lib/matplotlib/tests/test_axes.py
+++ b/lib/matplotlib/tests/test_axes.py
@@ -939,6 +939,35 @@ def test_inverted_limits():
     plt.close()
 
 
+@pytest.mark.parametrize('axis', ['x', 'y'])
+@pytest.mark.parametrize('scale', ['linear', 'log'])
+def test_inverted_limits_via_set_lim(axis, scale):
+    # Test gh:14646: reversing the limits of a log-scaled axis must invert
+    # the axis just like it does for a linear scale.
+    data = np.linspace(100, 1, 10)
+    fig, ax = plt.subplots()
+    if axis == 'x':
+        ax.plot(data, np.arange(data.size))
+    else:
+        ax.plot(np.arange(data.size), data)
+    getattr(ax, f'set_{axis}scale')(scale)
+
+    limits = (100, 1)
+    result = getattr(ax, f'set_{axis}lim')(*limits)
+
+    assert result == limits
+    assert getattr(ax, f'get_{axis}lim')() == limits
+    assert getattr(ax, f'{axis}axis_inverted')()
+
+    # The larger data value should be displayed first on the inverted axis.
+    if axis == 'x':
+        positions = ax.transData.transform([(100, 0), (1, 0)])[:, 0]
+    else:
+        positions = ax.transData.transform([(0, 100), (0, 1)])[:, 1]
+    assert positions[0] < positions[1]
+    plt.close(fig)
+
+
 @image_comparison(baseline_images=['nonfinite_limits'])
 def test_nonfinite_limits():
     x = np.arange(0., np.e, 0.01)

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(lib/matplotlib/ticker\.py|lib/mpl_toolkits/mplot3d/axes3d\.py|lib/matplotlib/axes/_base\.py)' -m pytest --no-header -rA  -p no:cacheprovider lib/matplotlib/tests/test_axes.py
cat coverage.cover
git checkout d65c9ca20ddf81ef91199e6d819f9d3506ef477c
git apply /root/pre_state.patch
