#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 3ea1ec84cc610f7a9f4f6b354e264565254923ff >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 3ea1ec84cc610f7a9f4f6b354e264565254923ff
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_build_linkcheck.py b/tests/test_build_linkcheck.py
index c09c81fe0..fa86e13fa 100644
--- a/tests/test_build_linkcheck.py
+++ b/tests/test_build_linkcheck.py
@@ -274,6 +274,43 @@ def test_follows_redirects_on_GET(app, capsys):
     )
 
 
+@pytest.mark.sphinx('linkcheck', testroot='linkcheck-localserver', freshenv=True)
+def test_too_many_redirects_on_HEAD(app):
+    requests_seen = []
+
+    class TooManyRedirectsHandler(http.server.BaseHTTPRequestHandler):
+        def do_HEAD(self):
+            requests_seen.append("HEAD")
+            self.send_response(302, "Found")
+            self.send_header("Location", "http://localhost:7777/")
+            self.end_headers()
+
+        def do_GET(self):
+            requests_seen.append("GET")
+            self.send_response(200, "OK")
+            self.end_headers()
+
+    with http_server(TooManyRedirectsHandler):
+        app.builder.build_all()
+
+    with open(app.outdir / 'output.json') as fp:
+        content = json.load(fp)
+
+    # The HEAD request follows redirects until requests raises
+    # TooManyRedirects.  Linkcheck should then fall back to a GET request
+    # and report the link as working instead of broken.
+    assert content == {
+        "code": 0,
+        "status": "working",
+        "filename": "index.rst",
+        "lineno": 1,
+        "uri": "http://localhost:7777/",
+        "info": "",
+    }
+    assert requests_seen.count("GET") == 1
+    assert requests_seen[-1] == "GET"
+
+
 class OKHandler(http.server.BaseHTTPRequestHandler):
     def do_HEAD(self):
         self.send_response(200, "OK")

EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/builders/linkcheck\.py)' -m tox -epy39 -v -- tests/test_build_linkcheck.py
cat coverage.cover
git checkout 3ea1ec84cc610f7a9f4f6b354e264565254923ff
git apply /root/pre_state.patch
