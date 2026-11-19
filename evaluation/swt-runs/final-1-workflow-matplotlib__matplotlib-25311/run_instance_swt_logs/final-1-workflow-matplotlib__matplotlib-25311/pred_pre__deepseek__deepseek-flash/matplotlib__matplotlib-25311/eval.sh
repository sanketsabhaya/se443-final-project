#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 430fb1db88843300fb4baae3edc499bbfe073b0c >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 430fb1db88843300fb4baae3edc499bbfe073b0c
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
diff --git a/lib/matplotlib/tests/test_pickle.py b/lib/matplotlib/tests/test_pickle.py
index ec6bdcc2fe..1b5fcba213 100755
--- a/lib/matplotlib/tests/test_pickle.py
+++ b/lib/matplotlib/tests/test_pickle.py
@@ -7,6 +7,7 @@ import pytest
 
 import matplotlib as mpl
 from matplotlib import cm
+from matplotlib.backend_bases import FigureCanvasBase
 from matplotlib.testing import subprocess_run_helper
 from matplotlib.testing.decorators import check_figures_equal
 from matplotlib.dates import rrulewrapper
@@ -44,6 +45,30 @@ def test_simple():
     pickle.dump(fig, BytesIO(), pickle.HIGHEST_PROTOCOL)
 
 
+@pytest.mark.parametrize("draggable_artist", ["legend", "annotation"])
+def test_pickle_draggable(draggable_artist):
+    # The canvas itself is not pickleable, but Figure.__getstate__ normally
+    # drops it.  Draggable artists must not keep a second reference to it.
+    class UnpicklableCanvas(FigureCanvasBase):
+        def __getstate__(self):
+            raise TypeError("cannot pickle canvas")
+
+    fig = mfigure.Figure()
+    UnpicklableCanvas(fig)
+    ax = fig.subplots()
+    ax.plot([0, 1], [0, 1], label="speed")
+    if draggable_artist == "legend":
+        ax.legend().set_draggable(True)
+    else:
+        ax.annotate("foo", (0, 0)).draggable(True)
+
+    fig = pickle.loads(pickle.dumps(fig))
+    if draggable_artist == "legend":
+        assert fig.axes[0].get_legend().get_draggable()
+    else:
+        assert fig.axes[0].texts[0]._draggable is not None
+
+
 def _generate_complete_test_figure(fig_ref):
     fig_ref.set_size_inches((10, 6))
     plt.figure(fig_ref)

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(lib/matplotlib/offsetbox\.py)' -m pytest --no-header -rA  -p no:cacheprovider lib/matplotlib/tests/test_pickle.py
cat coverage.cover
git checkout 430fb1db88843300fb4baae3edc499bbfe073b0c
git apply /root/pre_state.patch
