#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 82ef497a8c88f0f6e50d84520e7276bfbf65025d >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 82ef497a8c88f0f6e50d84520e7276bfbf65025d
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_ext_viewcode.py b/tests/test_ext_viewcode.py
index 79864095b..06663d61a 100755
--- a/tests/test_ext_viewcode.py
+++ b/tests/test_ext_viewcode.py
@@ -9,6 +9,7 @@
 """
 
 import re
+from zipfile import ZipFile
 
 import pytest
 
@@ -102,3 +103,38 @@ def test_local_source_files(app, status, warning):
 
     assert result.count('href="_modules/not_a_package/submodule.html#not_a_package.submodule.Class3.class_attr"') == 1
     assert result.count('This is the class attribute class_attr') == 1
+
+
+@pytest.mark.sphinx('html', testroot='ext-viewcode')
+def test_viewcode_epub_disabled(app, make_app):
+    # ``make html epub`` builds HTML first.  The subsequent EPUB build reuses
+    # the doctree environment, including the viewcode module metadata collected
+    # by the HTML build.  It must still respect viewcode_enable_epub=False.
+    app.build()
+
+    html_module_page = app.outdir / '_modules/spam/mod1.html'
+    assert html_module_page.exists()
+    assert 'Source code for spam.mod1' in html_module_page.read_text()
+
+    epub_app = make_app('epub', srcdir=app.srcdir)
+    assert epub_app.config.viewcode_enable_epub is False
+    epub_app.build()
+
+    # viewcode must not create module pages for the EPUB output.
+    module_page = epub_app.outdir / '_modules/spam/mod1.xhtml'
+    module_index = epub_app.outdir / '_modules/index.xhtml'
+    assert not module_page.exists(), (
+        'viewcode generated an EPUB module page despite '
+        'viewcode_enable_epub=False: %s' % module_page
+    )
+    assert not module_index.exists()
+    assert not (epub_app.outdir / '_modules').exists()
+
+    # The generated EPUB archive must not contain any module pages either.
+    epub_files = [name for name in epub_app.outdir.listdir()
+                  if name.endswith('.epub')]
+    assert len(epub_files) == 1
+    with ZipFile(str(epub_app.outdir / epub_files[0])) as archive:
+        module_pages = [name for name in archive.namelist()
+                        if name.startswith('_modules/')]
+    assert not module_pages, 'EPUB archive contains viewcode module pages: %s' % module_pages

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/ext/viewcode\.py)' -m tox -epy39 -v -- tests/test_ext_viewcode.py
cat coverage.cover
git checkout 82ef497a8c88f0f6e50d84520e7276bfbf65025d
git apply /root/pre_state.patch
