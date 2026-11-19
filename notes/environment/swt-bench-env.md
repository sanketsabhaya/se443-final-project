# SWT-Bench harness environment

Recorded: 2026-11-13T17:42:34-06:00

## Code
- Repo: https://github.com/logic-star-ai/SWT-Bench.git (README still says eth-sri/swt-bench; moved)
- Path: ~/se443/SWT-Bench, detached HEAD, treated as read-only
- Commit: be12d4c8e7a5315a6bd60b0cad72736e96a4af3e
- Commit info: 2026-11-04 12:56:33 +0100 Merge pull request #53 from logic-star-ai/feat/bugstack-verified-results
- Package version: pyproject 1.0.1, src/__init__ __version__ 1.2.0; requires-python >=3.9 (no upper bound)

## Python env
- ~/se443/SWT-Bench/.venv created with `uv sync --frozen --python 3.11` (uses repo's uv.lock)
- uv 0.13.8; Python 3.11.18

## Docker
- client 29.9.3 / server 29.9.3, Docker Desktop WSL2 backend
- NCPU=16 MemTotal=8019415040 driver=overlayfs root=/var/lib/docker
- Disk image location (per CLAUDE.md, set in Docker Desktop): D:\Docker\Data — not visible from WSL

## Dataset
- Name: princeton-nlp/SWE-bench_Verified, split test
- HF revision (sha): c104f840cc67f8b6eec6f759ebc8b2693d585d4a (last_modified 2025-02-18)
- Cached at ~/.cache/huggingface/hub/datasets--princeton-nlp--SWE-bench_Verified/snapshots/c104f840...
- SWT subset: --filter_swt excludes 67 IDs in dataset/filter_cases_verified.txt -> 433 instances (verified by count)
- Pinning: harness has no revision flag; all runs use HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 so the cached snapshot above is used.

## How to run (unit-test mode is the default exec_mode)
- cwd must contain dataset/filter_cases_verified.txt (relative path in src/dataset.py) and is where outputs go
  (image_build_logs/, run_instance_swt_logs/, evaluation_results/). We run from ~/se443/swt-runs/<run_id>/
  with a symlink dataset -> ~/se443/SWT-Bench/dataset.
- Command:
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONPATH=~/se443/SWT-Bench ~/se443/SWT-Bench/.venv/bin/python -m src.main \
    --dataset_name princeton-nlp/SWE-bench_Verified --filter_swt --predictions_path <preds.jsonl|gold> \
    --max_workers 1 --run_id <run_id> [--instance_ids ...]
- Defaults left as-is: --timeout 1800, --compute_coverage True, --cache_level env, --patch_types vanilla, --build_mode api
- src.report needs the 'figures' extras (imports figures.util); not installed, not needed (evaluation_results/*.json suffices).

## pip freeze (.venv)
```
aiohappyeyeballs==2.6.1
aiohttp==3.13.5
aiosignal==1.4.0
annotated-doc==0.0.4
anyio==4.13.0
attrs==26.1.0
certifi==2026.4.22
charset-normalizer==3.4.7
click==8.3.3
datasets==4.8.4
dill==0.4.1
docker==7.1.0
editdistance==0.8.1
filelock==3.29.0
fire==0.7.1
frozenlist==1.8.0
fsspec==2026.2.0
gitdb==4.0.12
gitpython==3.1.47
h11==0.16.0
hf-xet==1.4.3
httpcore==1.0.9
httpx==0.28.1
huggingface-hub==1.12.0
idna==3.13
markdown-it-py==4.0.0
mdurl==0.1.2
multidict==6.7.1
multiprocess==0.70.19
numpy==2.4.4
packaging==26.2
pandas==3.0.2
propcache==0.4.1
pyarrow==24.0.0
pygments==2.20.0
python-dateutil==2.9.0.post0
python-dotenv==1.2.2
pyyaml==6.0.3
requests==2.33.1
rich==15.0.0
shellingham==1.5.4
six==1.17.0
smmap==5.0.3
-e file:///home/mihir_barvaliya/se443/SWT-Bench
tabulate==0.10.0
termcolor==3.3.0
tqdm==4.67.3
typer==0.25.0
typing-extensions==4.15.0
unidiff==0.7.5
urllib3==2.6.3
xxhash==3.7.0
yarl==1.23.0
```
