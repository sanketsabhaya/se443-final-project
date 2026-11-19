#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 6786f437df54ca7780a047203cbcfaa1db8dc542 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 6786f437df54ca7780a047203cbcfaa1db8dc542
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(lib/matplotlib/widgets\.py)' -m pytest --no-header -rA  -p no:cacheprovider lib/matplotlib/tests/test_widgets.py
cat coverage.cover
git checkout 6786f437df54ca7780a047203cbcfaa1db8dc542
git apply /root/pre_state.patch
