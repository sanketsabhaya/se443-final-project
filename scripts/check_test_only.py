#!/usr/bin/env python3
"""Rule-4 validity check + harness input builder. Applied IDENTICALLY to both arms.

Reads mini-SWE-agent preds.json files (dict keyed by instance_id), classifies each
patch by the file paths in its diff headers only, and writes:
  <out_prefix>.validity.json   per-instance: files touched, valid flag, reason
  <out_prefix>.jsonl           harness predictions; INVALID patches are submitted as
                               model_patch "" so they stay in the denominator as failures.
The original preds.json is never modified. Patch text is never printed or edited.

Invalid reasons: missing (no prediction / null), empty, no_diff_headers,
non_test_files (touches any file that is not a test file).

Usage: check_test_only.py <out_prefix> <expected_instance_id>... -- <preds.json>...
"""
import json
import os
import re
import sys
from pathlib import PurePosixPath

DIFF_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.MULTILINE)
TEST_DIRS = {"test", "tests", "testing"}


def is_test_file(path: str) -> bool:
    p = PurePosixPath(path)
    if any(part in TEST_DIRS for part in p.parts[:-1]):
        return True
    name = p.name
    return (
        (name.startswith("test_") and name.endswith(".py"))
        or name.endswith("_test.py")
        or name in {"tests.py", "conftest.py"}
    )


def classify(patch):
    if patch is None:
        return False, "missing", []
    if not patch.strip():
        return False, "empty", []
    files = sorted({p for pair in DIFF_HEADER.findall(patch) for p in pair if p != "/dev/null"})
    if not files:
        return False, "no_diff_headers", []
    non_test = [f for f in files if not is_test_file(f)]
    if non_test:
        return False, "non_test_files", files
    return True, "ok", files


def main(argv):
    if "--" not in argv:
        sys.exit(__doc__)
    sep = argv.index("--")
    out_prefix, expected, pred_files = argv[0], argv[1:sep], argv[sep + 1 :]
    preds = {}
    for f in pred_files:
        preds.update(json.load(open(f)))

    # One model name per harness run (harness groups logs by it); missing preds reuse it.
    names = {p.get("model_name_or_path") for p in preds.values() if p and p.get("model_name_or_path")}
    default_name = sorted(names)[0] if names else "unknown"

    validity, lines = {}, []
    for iid in expected:
        pred = preds.get(iid)
        patch = pred.get("model_patch") if pred else None
        valid, reason, files = classify(patch)
        validity[iid] = {
            "valid": valid,
            "reason": reason,
            "files": files,
            "non_test_files": [f for f in files if not is_test_file(f)],
            "model_name_or_path": pred.get("model_name_or_path") if pred else None,
        }
        lines.append({
            "instance_id": iid,
            "model_name_or_path": (pred or {}).get("model_name_or_path") or default_name,
            "model_patch": patch if valid else "",
        })

    for suffix in (".validity.json", ".jsonl"):
        if os.path.exists(out_prefix + suffix):
            sys.exit(f"ERROR: {out_prefix + suffix} exists; refusing to overwrite")
    with open(out_prefix + ".validity.json", "w") as fh:
        json.dump(validity, fh, indent=2)
    with open(out_prefix + ".jsonl", "w") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
    for iid, v in validity.items():
        print(f"{iid}: valid={v['valid']} reason={v['reason']} files={v['files']}")


if __name__ == "__main__":
    main(sys.argv[1:])
