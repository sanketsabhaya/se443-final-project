#!/usr/bin/env python3
"""Full-run driver: for each instance (fixed plain-sorted order), run baseline, then workflow, then
the SWT-Bench harness on both arms of that instance. Sequential, resumable, logs everything.

Usage: run_experiment.py <run_id> [--instances FILE] [--only IID ...]
Start detached with scripts/start_experiment.sh (setsid + nohup; survives Claude Code exiting).

Resume rules:
  - an arm with done.json is skipped;
  - an arm directory without done.json (interrupted) is MOVED to <dir>.interrupted-<ts> (never deleted) and rerun;
  - a harness run whose run_meta.txt lacks "exit_code:" is moved aside the same way and rerun.
The driver records harness exit codes and paths only. It never reads harness results, and nothing from
~/se443/swt-runs is ever passed to the agent or the wrapper.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
# Overridable only for the driver's own dry-run test (fake launchers in a scratch directory).
PROJECT = Path(os.environ.get("EXP_PROJECT_ROOT", HOME / "se443/project"))
SWT_RUNS = Path(os.environ.get("EXP_SWT_RUNS", HOME / "se443/swt-runs"))
MIN_FREE_GB = 40
MAX_ATTEMPTS = 2


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


class Driver:
    def __init__(self, run_id, instances):
        self.run_id = run_id
        self.exp = PROJECT / "runs/experiment" / run_id
        self.exp.mkdir(parents=True, exist_ok=True)
        self.log_fh = open(self.exp / "driver.log", "a")
        self.status = self.exp / "status.tsv"
        if not self.status.exists():
            self.status.write_text("time\tinstance_id\tarm\tstage\texit_code\tpath\n")
        order_file = self.exp / "run_order.txt"
        if order_file.exists():
            recorded = order_file.read_text().split()
            if recorded != instances:
                sys.exit(f"run order differs from recorded {order_file}; refusing")
        else:
            order_file.write_text("\n".join(instances) + "\n")
        self.instances = instances

    def log(self, msg):
        line = f"[{now()}] {msg}"
        print(line, flush=True)
        self.log_fh.write(line + "\n")
        self.log_fh.flush()

    def record(self, iid, arm, stage, rc, path):
        with open(self.status, "a") as fh:
            fh.write(f"{now()}\t{iid}\t{arm}\t{stage}\t{rc}\t{path}\n")

    def move_aside(self, path):
        dest = path.with_name(f"{path.name}.interrupted-{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}")
        shutil.move(str(path), str(dest))
        self.log(f"moved incomplete {path} -> {dest}")
        return dest

    def free_gb(self):
        return shutil.disk_usage("/mnt/d").free / 1e9

    def run(self, cmd, logfile):
        self.log(f"run: {' '.join(map(str, cmd))}")
        with open(logfile, "a") as fh:
            fh.write(f"\n===== {now()} {' '.join(map(str, cmd))}\n")
            fh.flush()
            return subprocess.call(list(map(str, cmd)), stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    # ------------------------------------------------------------ generation
    def generate(self, iid, arm):
        arm_dir = PROJECT / "runs" / arm / self.run_id / iid
        if (arm_dir / "done.json").exists():
            self.log(f"{iid} {arm}: already done, skipping")
            return True
        launcher = PROJECT / "scripts" / ("run_baseline.sh" if arm == "baseline" else "run_workflow.sh")
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if arm_dir.exists():
                self.move_aside(arm_dir)
            if attempt > 1:  # only reached when the previous attempt left NO done.json (infrastructure crash)
                self.record(iid, arm, "INFRA_RETRY_generation", attempt, arm_dir)
                self.log(f"{iid} {arm}: INFRA RETRY {attempt}/{MAX_ATTEMPTS} (previous attempt left no done.json)")
            self.record(iid, arm, f"generate_start_attempt{attempt}", "", arm_dir)
            rc = self.run([launcher, self.run_id, iid], self.exp / f"{arm}_launcher.log")
            done = (arm_dir / "done.json").exists()
            self.record(iid, arm, f"generate_end_attempt{attempt}", rc, arm_dir)
            self.log(f"{iid} {arm}: attempt {attempt} rc={rc} done={done}")
            if done:
                return True
        self.log(f"{iid} {arm}: NO done.json after {MAX_ATTEMPTS} attempts (infrastructure failure); "
                 "counts as missing prediction")
        return False

    # ------------------------------------------------------------ harness (per instance, after both arms)
    @staticmethod
    def harness_status(hdir):
        """(complete, ok). complete: run_meta.txt has an exit_code line. ok: exit code 0 AND the harness
        reported 0 error instances. Only the error count is read (needed to decide an infrastructure retry);
        resolved/unresolved are never read by the driver."""
        meta = hdir / "run_meta.txt"
        if not meta.exists() or "exit_code:" not in meta.read_text():
            return False, False
        code = meta.read_text().split("exit_code:")[-1].split()[0]
        errors = None
        for f in (hdir / "evaluation_results").glob("*.json"):
            errors = json.loads(f.read_text()).get("error_instances")
        return True, code == "0" and errors == 0

    def harness(self, iid, arm):
        """Harness on the FINAL prediction of one arm. Retries (max MAX_ATTEMPTS) re-run the UNCHANGED
        prediction (same harness_input.jsonl); generation is never redone because of a harness error."""
        arm_dir = PROJECT / "runs" / arm / self.run_id / iid
        hid = f"{self.run_id}-{arm}-{iid}"
        hdir = SWT_RUNS / hid
        marker = self.exp / "harness_final" / f"{hid}.json"
        if marker.exists():
            self.log(f"{iid} {arm}: harness final, skipping")
            return
        prefix = arm_dir / "harness_input"
        if not Path(str(prefix) + ".jsonl").exists():
            preds = arm_dir / ("preds.json" if arm == "baseline" else "final_preds.json")
            if not preds.exists():  # no prediction at all -> missing (stays in the denominator)
                arm_dir.mkdir(parents=True, exist_ok=True)
                preds = arm_dir / "no_prediction.json"
                if not preds.exists():
                    preds.write_text("{}")
            rc = self.run([sys.executable, PROJECT / "scripts/check_test_only.py", prefix, iid, "--", preds],
                          self.exp / "rule4.log")
            self.record(iid, arm, "rule4_check", rc, str(prefix) + ".validity.json")
        input_sha = subprocess.run(["sha256sum", str(prefix) + ".jsonl"], capture_output=True, text=True).stdout.split()[0]
        ok, attempt = False, 0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if hdir.exists():
                complete, ok = self.harness_status(hdir)
                if complete and ok:  # finished cleanly before a driver restart
                    break
                self.move_aside(hdir)  # incomplete or errored run: kept as data, never deleted
            if attempt > 1:
                self.record(iid, arm, "HARNESS_RETRY_same_prediction", attempt, hdir)
                self.log(f"{iid} {arm}: HARNESS RETRY {attempt}/{MAX_ATTEMPTS} with unchanged prediction (sha256 {input_sha[:12]})")
            self.record(iid, arm, "harness_start", "", hdir)
            rc = self.run([PROJECT / "scripts/run_swt_harness.sh", hid, str(prefix) + ".jsonl", iid],
                          self.exp / "harness_launcher.log")
            complete, ok = self.harness_status(hdir)
            self.record(iid, arm, "harness_end", rc, hdir)
            self.log(f"{iid} {arm}: harness attempt {attempt} exit={rc} complete={complete} ok(no error instances)={ok}")
            if ok:
                break
        marker.parent.mkdir(exist_ok=True)
        marker.write_text(json.dumps({"harness_run_id": hid, "ok": ok, "attempts": attempt,
                                      "input_sha256": input_sha, "time": now()}))
        if not ok:
            self.log(f"{iid} {arm}: harness still erroring after {attempt} attempts; recorded as harness error")

    # ------------------------------------------------------------ image cleanup (user-approved)
    @staticmethod
    def eval_images():
        out = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                             capture_output=True, text=True).stdout.split()
        return sorted(i for i in out if i.startswith("exec.eval."))  # harness INSTANCE-level images only

    def harness_done(self, iid, arm):
        return (self.exp / "harness_final" / f"{self.run_id}-{arm}-{iid}.json").exists()

    def snapshot_before_harness(self, iid):
        d = self.exp / "images"
        d.mkdir(exist_ok=True)
        snap = d / f"{iid}.eval_images_before.json"
        if not snap.exists():  # written once; reused on resume
            snap.write_text(json.dumps(self.eval_images()))

    def cleanup_images(self, iid):
        d = self.exp / "images"
        removed = d / f"{iid}.removed.json"
        if removed.exists() or not all(self.harness_done(iid, a) for a in ("baseline", "workflow")):
            return
        before = set(json.loads((d / f"{iid}.eval_images_before.json").read_text()))
        mini_img = f"docker.io/swebench/sweb.eval.x86_64.{iid.replace('__', '_1776_')}:latest".lower()
        targets = [i for i in self.eval_images() if i not in before] + [mini_img]
        records = []
        for img in targets:
            insp = subprocess.run(["docker", "image", "inspect", "--format",
                                   "{{.Id}}\t{{json .RepoDigests}}\t{{.Size}}", img], capture_output=True, text=True)
            if insp.returncode != 0:
                records.append({"image": img, "present": False})
                continue
            iid_, digests, size = insp.stdout.strip().split("\t")
            rc = subprocess.run(["docker", "rmi", img], capture_output=True, text=True).returncode
            records.append({"image": img, "id": iid_, "repo_digests": json.loads(digests),
                            "size_bytes": int(size), "rmi_exit_code": rc})
        removed.write_text(json.dumps({"time": now(), "images": records}, indent=2))
        self.log(f"{iid}: removed instance-level images {[(r['image'], r.get('rmi_exit_code')) for r in records]}")

    def main(self, only=None):
        self.log(f"driver start run_id={self.run_id} instances={len(self.instances)}")
        for iid in self.instances:
            if only and iid not in only:
                continue
            free = self.free_gb()
            if free < MIN_FREE_GB:
                self.log(f"STOP: only {free:.0f} GB free on D: (< {MIN_FREE_GB} GB). Nothing deleted; resume after freeing space.")
                sys.exit(2)
            self.log(f"===== {iid} (D: free {free:.0f} GB)")
            ok_b = self.generate(iid, "baseline")
            ok_w = self.generate(iid, "workflow")
            self.snapshot_before_harness(iid)
            for arm, ok in (("baseline", ok_b), ("workflow", ok_w)):
                if not ok:
                    self.record(iid, arm, "generation_failed_missing_prediction", "", "")
                self.harness(iid, arm)
            self.cleanup_images(iid)
        self.log("driver finished all instances")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--instances", default=str(PROJECT / "configs/eval_instances.txt"))
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    instances = sorted(l.strip() for l in open(a.instances) if l.strip())  # fixed plain sorted order
    exp = PROJECT / "runs/experiment" / a.run_id
    exp.mkdir(parents=True, exist_ok=True)
    lock = open(exp / "driver.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("another driver holds the lock for this run_id")
    lock.write(json.dumps({"pid": __import__("os").getpid(), "started": now()}))
    lock.flush()
    Driver(a.run_id, instances).main(only=set(a.only) if a.only else None)


if __name__ == "__main__":
    main()
