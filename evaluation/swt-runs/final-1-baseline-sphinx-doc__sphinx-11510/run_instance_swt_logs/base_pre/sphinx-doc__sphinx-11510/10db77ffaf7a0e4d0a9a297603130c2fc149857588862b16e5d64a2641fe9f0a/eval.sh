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
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/directives/other\.py)' -m tox -epy39 -v -- tests/test_build_html.py
cat coverage.cover
git checkout 6cb783c0024a873722952a67ebb9f41771c8eb6d
git apply /root/pre_state.patch
