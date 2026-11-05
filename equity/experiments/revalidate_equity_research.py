"""Rerun saved equity audits in isolated report directories; never overwrite inputs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
OUT = ROOT/"experiments/equity_validation_review_2026_10_29"
AUDITS = ["equity_expanded_pca_reversal", "equity_persistence_regimes", "equity_persistence_images",
          "equity_full_basket_states", "equity_efa_vs_pca", "equity_expanded_structure", "equity_reversal_response"]


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def mirror(original, destination, exclude):
    destination.mkdir(parents=True, exist_ok=True)
    for p in original.iterdir():
        if p.name in exclude: continue
        target = destination/p.name
        if not target.exists() and not target.is_symlink(): target.symlink_to(p.resolve(), target_is_directory=p.is_dir())


def worker(name):
    if name == "equity_data":
        data = PROJECT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"
        destination = OUT/"rechecks/data"/data.name
        mirror(data, destination, {"independent_audit.json", "recent_60_session_liquidity_proxy.csv", "sector_counts.csv", "coverage_and_sectors.png"})
        old = destination.parent/"equity_daily_30_2016_2026-10-27"
        if not old.exists(): old.symlink_to(data.parent/old.name, target_is_directory=True)
        path = PROJECT/"market_data/audit_equity_expanded.py"
        sys.argv = [str(path), "--dataset", str(destination)]
    else:
        path = ROOT/"experiments"/("audit_"+name+".py")
        destination = OUT/"rechecks"/name
        mirror(ROOT/"experiments"/name, destination, {"independent_audit.json"})
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("audit_run", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    if name != "equity_data": module.OUT = destination
    if hasattr(module, "main"): module.main()
    else: module.audit()
    return destination/"independent_audit.json"


def snapshot():
    paths = set()
    for base in [ROOT, PROJECT/"market_data/datasets/equity_daily_30_2016_2026-10-27", PROJECT/"market_data/datasets/equity_daily_expanded_2016_2026-10-27"]:
        for p in base.rglob("*"):
            if p.is_file() and not p.is_symlink() and OUT not in p.parents and "__pycache__" not in p.parts:
                paths.add(p)
    return {str(p.relative_to(PROJECT)): digest(p) for p in sorted(paths)}


def main():
    OUT.mkdir(parents=True, exist_ok=True); (OUT/"logs").mkdir(exist_ok=True)
    before = snapshot(); (OUT/"before_sha256.json").write_text(json.dumps(before, indent=2)+"\n")
    env = os.environ.copy()
    env.update(MPLCONFIGDIR="/private/tmp/tda-mpl-cache", XDG_CACHE_HOME="/private/tmp/tda-cache", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    def run(name):
        begin = time.monotonic(); log = OUT/"logs"/(name+".txt")
        with log.open("w") as stream:
            completed = subprocess.run([sys.executable, str(Path(__file__)), "--worker", name], env=env, stdout=stream, stderr=subprocess.STDOUT)
        return {"audit": name, "returncode": completed.returncode, "seconds": time.monotonic()-begin, "log": str(log.relative_to(PROJECT))}
    results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run, name) for name in ["equity_data", *AUDITS]]
        for future in as_completed(futures):
            value = future.result(); results.append(value)
            print(json.dumps(value), flush=True)
    after = snapshot()
    changed = [p for p in before if after.get(p) != before[p]]
    result = {"audits": results, "all_passed": all(r["returncode"] == 0 for r in results),
        "original_files_checked": len(before), "changed_original_files": changed,
        "source_sha256": digest(Path(__file__))}
    (OUT/"audit_reruns.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2), flush=True)
    if changed or not result["all_passed"]: raise RuntimeError("Review audit logs or changed originals")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        try: worker(sys.argv[2])
        except Exception: traceback.print_exc(); raise
    else: main()
