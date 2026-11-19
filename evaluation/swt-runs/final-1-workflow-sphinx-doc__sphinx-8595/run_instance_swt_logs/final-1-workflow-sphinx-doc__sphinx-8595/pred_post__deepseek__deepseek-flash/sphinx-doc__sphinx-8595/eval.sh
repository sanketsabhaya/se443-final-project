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
diff --git a/sphinx/ext/autodoc/__init__.py b/sphinx/ext/autodoc/__init__.py
--- a/sphinx/ext/autodoc/__init__.py
+++ b/sphinx/ext/autodoc/__init__.py
@@ -1074,7 +1074,7 @@ def get_module_members(self) -> Dict[str, ObjectMember]:
     def get_object_members(self, want_all: bool) -> Tuple[bool, ObjectMembers]:
         members = self.get_module_members()
         if want_all:
-            if not self.__all__:
+            if self.__all__ is None:
                 # for implicit module members, check __module__ to avoid
                 # documenting imported objects
                 return True, list(members.values())

EOF_114329324912
git apply -v - <<'EOF_114329324912'
diff --git a/tests/roots/test-ext-autodoc/target/empty_all.py b/tests/roots/test-ext-autodoc/target/empty_all.py
new file mode 100644
index 000000000..00c66c720
--- /dev/null
+++ b/tests/roots/test-ext-autodoc/target/empty_all.py
@@ -0,0 +1,13 @@
+__all__ = []
+
+
+def foo():
+    "docstring"
+
+
+def bar():
+    "docstring"
+
+
+def baz():
+    "docstring"
diff --git a/tests/test_ext_autodoc.py b/tests/test_ext_autodoc.py
index 39897eb7d..5339c3b8e 100755
--- a/tests/test_ext_autodoc.py
+++ b/tests/test_ext_autodoc.py
@@ -714,6 +714,19 @@ def test_autodoc_special_members(app):
     ]
 
 
+@pytest.mark.sphinx('html', testroot='ext-autodoc')
+def test_autodoc_empty_module_all(app):
+    options = {"members": None}
+    actual = do_autodoc(app, 'module', 'target.empty_all', options)
+
+    # An empty __all__ means that the module itself is documented, but none of
+    # its members are.
+    assert '.. py:module:: target.empty_all' in actual
+    assert '.. py:function:: foo()' not in actual
+    assert '.. py:function:: bar()' not in actual
+    assert '.. py:function:: baz()' not in actual
+
+
 @pytest.mark.sphinx('html', testroot='ext-autodoc')
 def test_autodoc_ignore_module_all(app):
     # default (no-ignore-module-all)

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/ext/autodoc/__init__\.py)' -m tox -epy39 -v -- tests/roots/test-ext-autodoc/target/empty_all.py tests/test_ext_autodoc.py
cat coverage.cover
git checkout b19bce971e82f2497d67fdacdeca8db08ae0ba56
git apply /root/pre_state.patch
