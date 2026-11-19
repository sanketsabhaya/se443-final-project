#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD d65c9ca20ddf81ef91199e6d819f9d3506ef477c >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff d65c9ca20ddf81ef91199e6d819f9d3506ef477c
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(lib/matplotlib/ticker\.py|lib/mpl_toolkits/mplot3d/axes3d\.py|lib/matplotlib/axes/_base\.py)' -m pytest --no-header -rA  -p no:cacheprovider lib/matplotlib/tests/test_axes.py
cat coverage.cover
git checkout d65c9ca20ddf81ef91199e6d819f9d3506ef477c
git apply /root/pre_state.patch
