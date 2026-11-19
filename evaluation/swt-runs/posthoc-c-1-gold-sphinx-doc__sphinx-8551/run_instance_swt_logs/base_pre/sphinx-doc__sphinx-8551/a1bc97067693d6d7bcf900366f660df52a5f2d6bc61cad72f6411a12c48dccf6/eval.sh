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
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/domains/python\.py|sphinx/util/docfields\.py)' -m tox -epy39 -v -- tests/test_domain_py.py
cat coverage.cover
git checkout 57ed10c68057c96491acbd3e62254ccfaf9e3861
git apply /root/pre_state.patch
