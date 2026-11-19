#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 6cb783c0024a873722952a67ebb9f41771c8eb6d >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 6cb783c0024a873722952a67ebb9f41771c8eb6d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_build_html.py b/tests/test_build_html.py
index 07f101d7a..11545410c 100644
--- a/tests/test_build_html.py
+++ b/tests/test_build_html.py
@@ -1839,3 +1839,38 @@ def test_copy_images(app, status, warning):
         'svgimg.svg',
         'testimäge.png',
     }
+
+
+def test_source_read_event_for_included_file(make_app, tmp_path):
+    """source-read changes must also apply to files pulled in by ``include``."""
+    (tmp_path / 'conf.py').write_text(
+        "def subst_vars_replace(app, docname, source):\n"
+        "    source[0] = source[0].replace('&REPLACE_ME;', 'REPLACED')\n"
+        "\n"
+        "def setup(app):\n"
+        "    app.connect('source-read', subst_vars_replace)\n",
+        encoding='utf-8',
+    )
+    (tmp_path / 'index.rst').write_text(
+        "This is a test\n"
+        "==============\n"
+        "\n"
+        ".. include:: something-to-include.rst\n"
+        "\n"
+        "&REPLACE_ME;\n",
+        encoding='utf-8',
+    )
+    (tmp_path / 'something-to-include.rst').write_text(
+        "Testing\n"
+        "=======\n"
+        "\n"
+        "&REPLACE_ME;\n",
+        encoding='utf-8',
+    )
+
+    app = make_app('html', srcdir=tmp_path)
+    app.build()
+    content = (app.outdir / 'index.html').read_text(encoding='utf-8')
+
+    assert 'REPLACE_ME' not in content
+    assert content.count('REPLACED') == 2

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/directives/other\.py)' -m tox -epy39 -v -- tests/test_build_html.py
cat coverage.cover
git checkout 6cb783c0024a873722952a67ebb9f41771c8eb6d
git apply /root/pre_state.patch
