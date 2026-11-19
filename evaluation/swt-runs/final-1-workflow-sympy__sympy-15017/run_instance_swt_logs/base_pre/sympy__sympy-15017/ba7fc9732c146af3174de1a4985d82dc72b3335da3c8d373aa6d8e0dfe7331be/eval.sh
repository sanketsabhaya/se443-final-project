#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 6810dee426943c1a2fe85b5002dd0d4cf2246a05 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 6810dee426943c1a2fe85b5002dd0d4cf2246a05
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
None
EOF_114329324912
PYTHONWARNINGS='ignore::UserWarning,ignore::SyntaxWarning' python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sympy/tensor/array/dense_ndim_array\.py)' bin/test -C --verbose sympy/tensor/array/tests/test_immutable_ndim_array.p
cat coverage.cover
git checkout 6810dee426943c1a2fe85b5002dd0d4cf2246a05
git apply /root/pre_state.patch
