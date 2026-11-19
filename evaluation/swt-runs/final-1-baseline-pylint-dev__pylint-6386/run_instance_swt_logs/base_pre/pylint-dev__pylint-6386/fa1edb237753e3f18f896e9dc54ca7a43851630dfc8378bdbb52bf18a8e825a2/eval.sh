#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD 754b487f4d892e3d4872b6fc7468a71db4e31c13 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff 754b487f4d892e3d4872b6fc7468a71db4e31c13
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .
git apply -v - <<'EOF_114329324912'
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(pylint/config/arguments_manager\.py|pylint/config/utils\.py|pylint/config/argument\.py|pylint/lint/base_options\.py)' -m pytest --no-header -rA  -p no:cacheprovider tests/config/test_argparse_config.py
cat coverage.cover
git checkout 754b487f4d892e3d4872b6fc7468a71db4e31c13
git apply /root/pre_state.patch
