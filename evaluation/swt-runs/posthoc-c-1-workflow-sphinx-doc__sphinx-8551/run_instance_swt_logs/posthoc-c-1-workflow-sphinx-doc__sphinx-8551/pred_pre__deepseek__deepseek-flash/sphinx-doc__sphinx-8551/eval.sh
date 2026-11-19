#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 57ed10c68057c96491acbd3e62254ccfaf9e3861 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 57ed10c68057c96491acbd3e62254ccfaf9e3861
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_domain_py.py b/tests/test_domain_py.py
index 2dc97bed9..b4b5529e8 100644
--- a/tests/test_domain_py.py
+++ b/tests/test_domain_py.py
@@ -865,3 +865,42 @@ def test_warn_missing_reference(app, status, warning):
     assert 'index.rst:6: WARNING: undefined label: no-label' in warning.getvalue()
     assert ('index.rst:6: WARNING: Failed to create a cross reference. A title or caption not found: existing-label'
             in warning.getvalue())
+
+
+@pytest.mark.sphinx('dummy', testroot='domain-py', freshenv=True)
+def test_doc_field_xref_uses_current_module(app, warning):
+    (app.srcdir / 'index.rst').write_text(
+        ".. py:class:: mod.A\n"
+        "\n"
+        ".. py:class:: mod.submod.A\n"
+        "\n"
+        ".. py:currentmodule:: mod\n"
+        "\n"
+        ".. py:function:: f1()\n"
+        "\n"
+        "   :param A a: description\n"
+        "   :rtype: A\n"
+        "\n"
+        ".. py:currentmodule:: mod.submod\n"
+        "\n"
+        ".. py:function:: f2()\n"
+        "\n"
+        "   :param A a: description\n"
+        "   :rtype: A\n")
+    app.build()
+
+    # The info fields should create one implicit cross-reference for each
+    # unqualified type name.
+    doctree = app.env.get_doctree('index')
+    refnodes = list(doctree.traverse(pending_xref))
+    assert len(refnodes) == 4
+    for refnode in refnodes:
+        assert_node(refnode, refdomain='py', reftype='class', reftarget='A')
+
+    # They should resolve relative to the current module rather than searching
+    # every module and reporting an ambiguous target.
+    doctree = app.env.get_and_resolve_doctree('index', app.builder)
+    refnodes = list(doctree.traverse(nodes.reference))
+    assert [refnode['refid'] for refnode in refnodes] == [
+        'mod.A', 'mod.A', 'mod.submod.A', 'mod.submod.A']
+    assert "more than one target found for cross-reference 'A'" not in warning.getvalue()

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/util/docfields\.py|sphinx/domains/python\.py)' -m tox -epy39 -v -- tests/test_domain_py.py
cat coverage.cover
git checkout 57ed10c68057c96491acbd3e62254ccfaf9e3861
git apply /root/pre_state.patch
