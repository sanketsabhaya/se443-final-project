#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD f0632c0fc7339f68e992ed63ae4cfac76cd41aad >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff f0632c0fc7339f68e992ed63ae4cfac76cd41aad
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(lib/matplotlib/dates\.py)' -m pytest --no-header -rA  -p no:cacheprovider lib/matplotlib/tests/test_dates.py
cat coverage.cover
git checkout f0632c0fc7339f68e992ed63ae4cfac76cd41aad
git apply /root/pre_state.patch
