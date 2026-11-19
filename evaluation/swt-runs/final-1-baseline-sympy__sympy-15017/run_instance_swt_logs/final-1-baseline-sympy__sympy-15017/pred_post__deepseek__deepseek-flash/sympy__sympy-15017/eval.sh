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
diff --git a/sympy/tensor/array/dense_ndim_array.py b/sympy/tensor/array/dense_ndim_array.py
--- a/sympy/tensor/array/dense_ndim_array.py
+++ b/sympy/tensor/array/dense_ndim_array.py
@@ -149,7 +149,7 @@ def _new(cls, iterable, shape, **kwargs):
         self._shape = shape
         self._array = list(flat_list)
         self._rank = len(shape)
-        self._loop_size = functools.reduce(lambda x,y: x*y, shape) if shape else 0
+        self._loop_size = functools.reduce(lambda x,y: x*y, shape, 1)
         return self
 
     def __setitem__(self, index, value):

EOF_114329324912
git apply -v - <<'EOF_114329324912'
diff --git a/sympy/tensor/array/tests/test_immutable_ndim_array.py b/sympy/tensor/array/tests/test_immutable_ndim_array.py
index 5a576c44f..d1d98c9f5 100644
--- a/sympy/tensor/array/tests/test_immutable_ndim_array.py
+++ b/sympy/tensor/array/tests/test_immutable_ndim_array.py
@@ -73,13 +73,20 @@ def test_ndim_array_initiation():
 
     from sympy.abc import x
     rank_zero_array = ImmutableDenseNDimArray(x)
-    assert len(rank_zero_array) == 0
+    assert len(rank_zero_array) == 1
     assert rank_zero_array.shape == ()
     assert rank_zero_array.rank() == 0
     assert rank_zero_array[()] == x
     raises(ValueError, lambda: rank_zero_array[0])
 
 
+def test_rank_zero_array_len():
+    from sympy import Array
+    a = Array(3)
+    assert len(a) == 1
+    assert len(list(a)) == 1
+
+
 def test_reshape():
     array = ImmutableDenseNDimArray(range(50), 50)
     assert array.shape == (50,)

EOF_114329324912
PYTHONWARNINGS='ignore::UserWarning,ignore::SyntaxWarning' python3 /root/trace.py --count -C coverage.cover --include-pattern '/testbed/(sympy/tensor/array/dense_ndim_array\.py)' bin/test -C --verbose sympy/tensor/array/tests/test_immutable_ndim_array.p
cat coverage.cover
git checkout 6810dee426943c1a2fe85b5002dd0d4cf2246a05
git apply /root/pre_state.patch
