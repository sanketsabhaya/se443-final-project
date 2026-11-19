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
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/builders/html/transforms\.py)' -m tox -epy39 -v -- tests/test_markup.py
cat coverage.cover
git checkout 21698c14461d27933864d73e6fba568a154e83b3
git apply /root/pre_state.patch
