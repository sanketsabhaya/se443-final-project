#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 21698c14461d27933864d73e6fba568a154e83b3 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 21698c14461d27933864d73e6fba568a154e83b3
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
diff --git a/sphinx/builders/html/transforms.py b/sphinx/builders/html/transforms.py
--- a/sphinx/builders/html/transforms.py
+++ b/sphinx/builders/html/transforms.py
@@ -37,7 +37,7 @@ class KeyboardTransform(SphinxPostTransform):
     """
     default_priority = 400
     builders = ('html',)
-    pattern = re.compile(r'(-|\+|\^|\s+)')
+    pattern = re.compile(r'(?<=.)(-|\+|\^|\s+)(?=.)')
 
     def run(self, **kwargs: Any) -> None:
         matcher = NodeMatcher(nodes.literal, classes=["kbd"])

EOF_114329324912
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_markup.py b/tests/test_markup.py
index a2bcb2dc1..11a412af5 100644
--- a/tests/test_markup.py
+++ b/tests/test_markup.py
@@ -266,6 +266,71 @@ def get_verifier(verify, verify_re):
          '</kbd></p>'),
         '\\sphinxkeyboard{\\sphinxupquote{M\\sphinxhyphen{}x  M\\sphinxhyphen{}s}}',
     ),
+    (
+        # kbd role: a trailing separator is a keystroke, not a split point
+        'verify',
+        ':kbd:`Alt+^`',
+        ('<p><kbd class="kbd docutils literal notranslate">'
+         '<kbd class="kbd docutils literal notranslate">Alt</kbd>'
+         '+'
+         '<kbd class="kbd docutils literal notranslate">^</kbd>'
+         '</kbd></p>'),
+        '\\sphinxkeyboard{\\sphinxupquote{Alt+\\textasciicircum{}}}',
+    ),
+    (
+        # kbd role: a standalone separator is a single keystroke
+        'verify',
+        ':kbd:`-`',
+        '<p><kbd class="kbd docutils literal notranslate">-</kbd></p>',
+        '\\sphinxkeyboard{\\sphinxupquote{\\sphinxhyphen{}}}',
+    ),
+    (
+        # kbd role: a standalone separator is a single keystroke
+        'verify',
+        ':kbd:`+`',
+        '<p><kbd class="kbd docutils literal notranslate">+</kbd></p>',
+        None,
+    ),
+    (
+        # kbd role: a standalone separator is a single keystroke
+        'verify',
+        ':kbd:`^`',
+        '<p><kbd class="kbd docutils literal notranslate">^</kbd></p>',
+        None,
+    ),
+    (
+        # kbd role: a trailing separator is a keystroke, not a split point
+        'verify',
+        ':kbd:`Shift-+`',
+        ('<p><kbd class="kbd docutils literal notranslate">'
+         '<kbd class="kbd docutils literal notranslate">Shift</kbd>'
+         '-'
+         '<kbd class="kbd docutils literal notranslate">+</kbd>'
+         '</kbd></p>'),
+        None,
+    ),
+    (
+        # kbd role: a trailing separator is a keystroke, not a split point
+        'verify',
+        ':kbd:`Ctrl+-`',
+        ('<p><kbd class="kbd docutils literal notranslate">'
+         '<kbd class="kbd docutils literal notranslate">Ctrl</kbd>'
+         '+'
+         '<kbd class="kbd docutils literal notranslate">-</kbd>'
+         '</kbd></p>'),
+        None,
+    ),
+    (
+        # kbd role: a trailing separator is a keystroke, not a split point
+        'verify',
+        ':kbd:`Shift-^`',
+        ('<p><kbd class="kbd docutils literal notranslate">'
+         '<kbd class="kbd docutils literal notranslate">Shift</kbd>'
+         '-'
+         '<kbd class="kbd docutils literal notranslate">^</kbd>'
+         '</kbd></p>'),
+        None,
+    ),
     (
         # non-interpolation of dashes in option role
         'verify_re',

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/builders/html/transforms\.py)' -m tox -epy39 -v -- tests/test_markup.py
cat coverage.cover
git checkout 21698c14461d27933864d73e6fba568a154e83b3
git apply /root/pre_state.patch
