#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 68aa4fb29e7dfe521749e1e14f750d7afabb3481 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 68aa4fb29e7dfe521749e1e14f750d7afabb3481
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
diff --git a/sphinx/ext/autodoc/typehints.py b/sphinx/ext/autodoc/typehints.py
--- a/sphinx/ext/autodoc/typehints.py
+++ b/sphinx/ext/autodoc/typehints.py
@@ -27,7 +27,7 @@ def record_typehints(app: Sphinx, objtype: str, name: str, obj: Any,
         if callable(obj):
             annotations = app.env.temp_data.setdefault('annotations', {})
             annotation = annotations.setdefault(name, OrderedDict())
-            sig = inspect.signature(obj)
+            sig = inspect.signature(obj, type_aliases=app.config.autodoc_type_aliases)
             for param in sig.parameters.values():
                 if param.annotation is not param.empty:
                     annotation[param.name] = typing.stringify(param.annotation)

EOF_114329324912
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_ext_autodoc_configs.py b/tests/test_ext_autodoc_configs.py
index 496059b7c..c1f4127e9 100644
--- a/tests/test_ext_autodoc_configs.py
+++ b/tests/test_ext_autodoc_configs.py
@@ -778,6 +778,23 @@ def test_autodoc_type_aliases(app):
     ]
 
 
+@pytest.mark.sphinx('text', testroot='ext-autodoc',
+                    confoverrides={'autodoc_typehints': 'description',
+                                   'autodoc_type_aliases': {'myint': 'myint'}})
+def test_autodoc_type_aliases_with_typehints_description(app):
+    doctree = restructuredtext.parse(app, '.. autofunction:: target.annotations.sum')
+    assert doctree.astext() == (
+        '\n\n'
+        'target.annotations.sum(x, y)\n\n'
+        'docstring\n\n'
+        'Parameters\n\n'
+        'x (myint) -- \n\n'
+        'y (myint) -- \n\n'
+        'Return type\n\n'
+        'myint'
+    )
+
+
 @pytest.mark.sphinx('html', testroot='ext-autodoc')
 def test_autodoc_default_options(app):
     # no settings

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/ext/autodoc/typehints\.py)' -m tox -epy39 -v -- tests/test_ext_autodoc_configs.py
cat coverage.cover
git checkout 68aa4fb29e7dfe521749e1e14f750d7afabb3481
git apply /root/pre_state.patch
