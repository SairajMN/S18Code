"""Recompute every axis from the persisted raw runs. No model calls.

This exists because `empty_billed` shipped wrong and the only fix available was
six more hours of GPU. Now the runs are on disk, so a scorer bug costs a rerun
of this file instead.
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from S18Code.harnesses.base import Step, TaskRun
from S18Code.evals.axes import score

rows = []
for f in sorted((pathlib.Path(__file__).parent / "proofs" / "runs").glob("*.json")):
    d = json.loads(f.read_text())
    passed, kind = d.pop("actually_passed"), d.pop("kind")
    d.pop("pytest_tail", None); d.pop("final_files", None)
    d["steps"] = [Step(**s) for s in d["steps"]]
    row = score(TaskRun(**d), actually_passed=passed)
    row["kind"], row["claimed"] = kind, d["claimed_success"]
    rows.append(row)

out = pathlib.Path(__file__).parent / "proofs" / "results_local.json"
out.write_text(json.dumps({"model": "qwen3.8:27b", "date": "2026-08-16", "rows": rows}, indent=1))
print(f"rescored {len(rows)} runs from disk, 0 model calls")
for r in rows:
    print(f"  {r['task'][:26]:26s} {r['harness']:10s} solved={r['solved']!s:5s} "
          f"verified={r['verified']!s:5s} unverified_pass={r['unverified_pass']!s:5s} "
          f"claimed={r['claimed']!s:5s} ended={r['ended']}")
