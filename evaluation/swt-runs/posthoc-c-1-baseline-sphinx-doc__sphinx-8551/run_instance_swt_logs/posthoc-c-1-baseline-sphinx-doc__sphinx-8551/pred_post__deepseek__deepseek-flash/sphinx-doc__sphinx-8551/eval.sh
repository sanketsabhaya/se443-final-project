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
diff --git a/sphinx/domains/python.py b/sphinx/domains/python.py
--- a/sphinx/domains/python.py
+++ b/sphinx/domains/python.py
@@ -272,6 +272,8 @@ def make_xref(self, rolename: str, domain: str, target: str,
         result = super().make_xref(rolename, domain, target,  # type: ignore
                                    innernode, contnode, env)
         result['refspecific'] = True
+        result['py:module'] = env.ref_context.get('py:module')
+        result['py:class'] = env.ref_context.get('py:class')
         if target.startswith(('.', '~')):
             prefix, result['reftarget'] = target[0], target[1:]
             if prefix == '.':
diff --git a/sphinx/util/docfields.py b/sphinx/util/docfields.py
--- a/sphinx/util/docfields.py
+++ b/sphinx/util/docfields.py
@@ -295,6 +295,7 @@ def transform(self, node: nodes.field_list) -> None:
                         self.directive.domain,
                         target,
                         contnode=content[0],
+                        env=self.directive.state.document.settings.env
                     )
                     if _is_single_paragraph(field_body):
                         paragraph = cast(nodes.paragraph, field_body[0])

EOF_114329324912
git apply -v - <<'EOF_114329324912'
diff --git a/tests/roots/test-domain-py-xref-types/conf.py b/tests/roots/test-domain-py-xref-types/conf.py
new file mode 100644
index 000000000..6b73318d7
--- /dev/null
+++ b/tests/roots/test-domain-py-xref-types/conf.py
@@ -0,0 +1,2 @@
+project = 'test-domain-py-xref-types'
+master_doc = 'index'
diff --git a/tests/roots/test-domain-py-xref-types/index.rst b/tests/roots/test-domain-py-xref-types/index.rst
new file mode 100644
index 000000000..9facb4804
--- /dev/null
+++ b/tests/roots/test-domain-py-xref-types/index.rst
@@ -0,0 +1,14 @@
+test-domain-py-xref-types
+=========================
+
+.. py:class:: mod.A
+.. py:class:: mod.submod.A
+
+.. py:currentmodule:: mod.submod
+
+.. py:function:: f()
+
+   - :py:class:`A`
+
+   :param A a: parameter
+   :rtype: A
diff --git a/tests/test_domain_py.py b/tests/test_domain_py.py
index 2dc97bed9..cdd5fed4d 100644
--- a/tests/test_domain_py.py
+++ b/tests/test_domain_py.py
@@ -164,6 +164,18 @@ def test_domain_py_objects(app, status, warning):
     assert objects['NestedParentB.child_1'][2] == 'method'
 
 
+@pytest.mark.sphinx('html', testroot='domain-py-xref-types')
+def test_domain_py_field_type_xrefs(app, status, warning):
+    """Type fields should resolve names relative to the current module."""
+    app.builder.build_all()
+
+    assert 'more than one target found for cross-reference' not in warning.getvalue()
+
+    content = (app.outdir / 'index.html').read_text()
+    assert content.count('href="#mod.submod.A" title="mod.submod.A"') == 3
+    assert 'href="#mod.A" title="mod.A"' not in content
+
+
 @pytest.mark.sphinx('html', testroot='domain-py')
 def test_resolve_xref_for_properties(app, status, warning):
     app.builder.build_all()

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/domains/python\.py|sphinx/util/docfields\.py)' -m tox -epy39 -v -- tests/roots/test-domain-py-xref-types/conf.py tests/roots/test-domain-py-xref-types/index.rst tests/test_domain_py.py
cat coverage.cover
git checkout 57ed10c68057c96491acbd3e62254ccfaf9e3861
git apply /root/pre_state.patch
