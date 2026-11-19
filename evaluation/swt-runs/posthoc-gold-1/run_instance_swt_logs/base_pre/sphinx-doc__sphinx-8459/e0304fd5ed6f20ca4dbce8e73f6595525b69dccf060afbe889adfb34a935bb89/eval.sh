#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 68aa4fb29e7dfe521749e1e14f750d7afabb3481 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 68aa4fb29e7dfe521749e1e14f750d7afabb3481
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/ext/autodoc/typehints\.py)' -m tox -epy39 -v -- tests/test_ext_autodoc_configs.py
cat coverage.cover
git checkout 68aa4fb29e7dfe521749e1e14f750d7afabb3481
git apply /root/pre_state.patch
