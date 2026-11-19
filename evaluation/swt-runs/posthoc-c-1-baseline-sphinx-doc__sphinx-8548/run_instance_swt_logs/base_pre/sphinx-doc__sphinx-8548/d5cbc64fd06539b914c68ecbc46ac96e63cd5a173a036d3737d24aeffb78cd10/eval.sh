#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git diff HEAD dd1615c59dc6fff633e27dbb3861f2d27e1fb976 >> /root/pre_state.patch
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git diff dd1615c59dc6fff633e27dbb3861f2d27e1fb976
source /opt/miniconda3/bin/activate
conda activate testbed
python -m pip install -e .[test]
git apply -v - <<'EOF_114329324912'
None
EOF_114329324912
python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sphinx/ext/autodoc/importer\.py|sphinx/ext/autodoc/__init__\.py)' -m tox -epy39 -v -- tests/roots/test-ext-autodoc/target/instance_variable.py tests/test_ext_autodoc_autoclass.py
cat coverage.cover
git checkout dd1615c59dc6fff633e27dbb3861f2d27e1fb976
git apply /root/pre_state.patch
