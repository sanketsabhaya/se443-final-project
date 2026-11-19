#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 07983a5a8704ad91ae855218ecbda1c8598200ca >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 07983a5a8704ad91ae855218ecbda1c8598200ca
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
diff --git a/tests/roots/test-ext-autodoc/target/private_variable.py b/tests/roots/test-ext-autodoc/target/private_variable.py
new file mode 100644
index 000000000..1eacd2d2d
--- /dev/null
+++ b/tests/roots/test-ext-autodoc/target/private_variable.py
@@ -0,0 +1 @@
+_foo = None  #: :meta public:
diff --git a/tests/test_ext_autodoc_private_members.py b/tests/test_ext_autodoc_private_members.py
index 6bce5ce78..17ff37ad4 100644
--- a/tests/test_ext_autodoc_private_members.py
+++ b/tests/test_ext_autodoc_private_members.py
@@ -81,3 +81,21 @@ def test_private_members(app):
         '   :meta public:',
         '',
     ]
+
+
+@pytest.mark.sphinx('html', testroot='ext-autodoc')
+def test_public_metadata_on_variable(app):
+    options = {"members": None}
+    actual = do_autodoc(app, 'module', 'target.private_variable', options)
+    assert list(actual) == [
+        '',
+        '.. py:module:: target.private_variable',
+        '',
+        '',
+        '.. py:data:: _foo',
+        '   :module: target.private_variable',
+        '   :value: None',
+        '',
+        '   :meta public:',
+        '',
+    ]

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/ext/autodoc/__init__\.py|sphinx/ext/autodoc/importer\.py)' -m tox -epy39 -v -- tests/roots/test-ext-autodoc/target/private_variable.py tests/test_ext_autodoc_private_members.py
cat coverage.cover
git checkout 07983a5a8704ad91ae855218ecbda1c8598200ca
git apply /root/pre_state.patch
