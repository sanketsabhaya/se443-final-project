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
diff --git a/lib/matplotlib/widgets.py b/lib/matplotlib/widgets.py
--- a/lib/matplotlib/widgets.py
+++ b/lib/matplotlib/widgets.py
@@ -2156,7 +2156,12 @@ def new_axes(self, ax):
             self.artists.append(self._rect)
 
     def _setup_edge_handle(self, props):
-        self._edge_handles = ToolLineHandles(self.ax, self.extents,
+        # Define initial position using the axis bounds to keep the same bounds
+        if self.direction == 'horizontal':
+            positions = self.ax.get_xbound()
+        else:
+            positions = self.ax.get_ybound()
+        self._edge_handles = ToolLineHandles(self.ax, positions,
                                              direction=self.direction,
                                              line_props=props,
                                              useblit=self.useblit)

EOF_114329324912
git apply -v - <<'EOF_114329324912'
diff --git a/lib/matplotlib/tests/test_widgets.py b/lib/matplotlib/tests/test_widgets.py
index 71ebd176f..19094bca8 100644
--- a/lib/matplotlib/tests/test_widgets.py
+++ b/lib/matplotlib/tests/test_widgets.py
@@ -302,6 +302,35 @@ def test_tool_line_handle():
     assert tool_line_handle.positions == positions
 
 
+@pytest.mark.parametrize('direction', ("horizontal", "vertical"))
+def test_span_selector_bound(direction):
+    fig, ax = plt.subplots(1, 1)
+    ax.plot([10, 20], [10, 30])
+    ax.figure.canvas.draw()
+    x_bound = ax.get_xbound()
+    y_bound = ax.get_ybound()
+
+    tool = widgets.SpanSelector(ax, print, direction, interactive=True)
+    assert ax.get_xbound() == x_bound
+    assert ax.get_ybound() == y_bound
+
+    bound = x_bound if direction == 'horizontal' else y_bound
+    assert tool._edge_handles.positions == list(bound)
+
+    press_data = [10.5, 11.5]
+    move_data = [11, 13]  # Updating selector is done in onmove
+    release_data = move_data
+    do_event(tool, 'press', xdata=press_data[0], ydata=press_data[1], button=1)
+    do_event(tool, 'onmove', xdata=move_data[0], ydata=move_data[1], button=1)
+
+    assert ax.get_xbound() == x_bound
+    assert ax.get_ybound() == y_bound
+
+    index = 0 if direction == 'horizontal' else 1
+    handle_positions = [press_data[index], release_data[index]]
+    assert tool._edge_handles.positions == handle_positions
+
+
 def check_lasso_selector(**kwargs):
     ax = get_ax()
 

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(lib/matplotlib/widgets\.py)' -m pytest --no-header -rA  -p no:cacheprovider lib/matplotlib/tests/test_widgets.py
cat coverage.cover
git checkout 6786f437df54ca7780a047203cbcfaa1db8dc542
git apply /root/pre_state.patch
