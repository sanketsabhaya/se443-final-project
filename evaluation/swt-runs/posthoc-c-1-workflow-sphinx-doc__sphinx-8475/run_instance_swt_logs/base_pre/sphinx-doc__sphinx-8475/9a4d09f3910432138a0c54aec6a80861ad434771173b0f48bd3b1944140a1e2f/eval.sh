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
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/builders/linkcheck\.py)' -m tox -epy39 -v -- tests/test_build_linkcheck.py
cat coverage.cover
git checkout 3ea1ec84cc610f7a9f4f6b354e264565254923ff
git apply /root/pre_state.patch
