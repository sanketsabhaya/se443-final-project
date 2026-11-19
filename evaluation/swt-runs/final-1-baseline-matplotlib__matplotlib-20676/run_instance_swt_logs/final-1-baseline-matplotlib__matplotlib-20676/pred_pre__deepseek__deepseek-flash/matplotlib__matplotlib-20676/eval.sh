#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 6786f437df54ca7780a047203cbcfaa1db8dc542 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 6786f437df54ca7780a047203cbcfaa1db8dc542
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
diff --git a/lib/matplotlib/tests/test_widgets.py b/lib/matplotlib/tests/test_widgets.py
index 71ebd176f..ff8bbc5eb 100644
--- a/lib/matplotlib/tests/test_widgets.py
+++ b/lib/matplotlib/tests/test_widgets.py
@@ -259,6 +259,20 @@ def test_span_selector_drag(drag_from_anywhere):
     assert tool.extents == (175, 185)
 
 
+@pytest.mark.parametrize('direction', ['horizontal', 'vertical'])
+def test_span_selector_interactive_axes_limits(direction):
+    fig, ax = plt.subplots()
+    ax.plot([10, 20], [10, 20])
+    xlim = ax.get_xlim()
+    ylim = ax.get_ylim()
+
+    widgets.SpanSelector(ax, lambda *args: None, direction, interactive=True)
+
+    fig.canvas.draw()
+    assert_allclose(ax.get_xlim(), xlim)
+    assert_allclose(ax.get_ylim(), ylim)
+
+
 def test_span_selector_direction():
     ax = get_ax()
 

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(lib/matplotlib/widgets\.py)' -m pytest --no-header -rA  -p no:cacheprovider lib/matplotlib/tests/test_widgets.py
cat coverage.cover
git checkout 6786f437df54ca7780a047203cbcfaa1db8dc542
git apply /root/pre_state.patch
