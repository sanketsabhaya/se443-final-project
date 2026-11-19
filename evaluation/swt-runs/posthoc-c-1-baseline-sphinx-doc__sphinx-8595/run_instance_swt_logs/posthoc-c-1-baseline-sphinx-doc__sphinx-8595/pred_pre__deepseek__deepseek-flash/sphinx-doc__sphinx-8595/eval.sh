#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD b19bce971e82f2497d67fdacdeca8db08ae0ba56 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff b19bce971e82f2497d67fdacdeca8db08ae0ba56
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
diff --git a/tests/roots/test-ext-autodoc/target/empty_all.py b/tests/roots/test-ext-autodoc/target/empty_all.py
new file mode 100644
index 000000000..c39e90a36
--- /dev/null
+++ b/tests/roots/test-ext-autodoc/target/empty_all.py
@@ -0,0 +1,13 @@
+__all__ = []
+
+
+def foo():
+    """docstring"""
+
+
+def bar():
+    """docstring"""
+
+
+def baz():
+    """docstring"""
diff --git a/tests/test_ext_autodoc.py b/tests/test_ext_autodoc.py
index 39897eb7d..bbe81ab5c 100755
--- a/tests/test_ext_autodoc.py
+++ b/tests/test_ext_autodoc.py
@@ -738,6 +738,15 @@ def test_autodoc_ignore_module_all(app):
     ]
 
 
+@pytest.mark.sphinx('html', testroot='ext-autodoc')
+def test_autodoc_empty_module_all(app):
+    options = {"members": None}
+    actual = do_autodoc(app, 'module', 'target.empty_all', options)
+    assert list(filter(lambda line: '::' in line, actual)) == [
+        '.. py:module:: target.empty_all',
+    ]
+
+
 @pytest.mark.sphinx('html', testroot='ext-autodoc')
 def test_autodoc_noindex(app):
     options = {"noindex": True}

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/ext/autodoc/__init__\.py)' -m tox -epy39 -v -- tests/roots/test-ext-autodoc/target/empty_all.py tests/test_ext_autodoc.py
cat coverage.cover
git checkout b19bce971e82f2497d67fdacdeca8db08ae0ba56
git apply /root/pre_state.patch
