"""Add wasted_steps to Cost. Pure re-scoring: journals untouched.

Rule change (see CHANGELOG.md 1.1.0): a run's steps after its last edit or
command are "wasted" — reading, testing, or re-explaining after the last
useful action. w = len(steps) - 1 - last_useful_index, clamped at 0 when
there is a useful step; a run with NO useful step wastes all of its steps.

The cleanest implementation is to bump SCORER_VERSION here and rebuild the
cost dict in score_run, but that would edit the scorer mid-demo. Instead
this wraps the current scorer: load journals, score with 1.0.0, then attach
wasted_steps computed from the same journals, and diff against a saved
1.0.0 scores file with the scorer's own --diff machinery.
"""
import argparse, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from S18Code.scorer.score import load_journal, score_run


def wasted_steps(steps: list) -> int:
    last_useful = -1
    for i, s in enumerate(steps):
        k = s.get("kind", "") if isinstance(s, dict) else s.kind
        if k in ("edit", "command"):
            last_useful = i
    if last_useful < 0:
        return len(steps)
    return len(steps) - 1 - last_useful


def score_v110(journal: dict) -> dict:
    row = score_run(journal)
    if row["cost"] is not None:
        row["cost"]["wasted_steps"] = wasted_steps(journal.get("steps", []))
    row["scorer_version"] = "1.1.0"
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", default=str(pathlib.Path(__file__).resolve().parents[1] / "runs"))
    p.add_argument("--diff", required=True, help="1.0.0 scores file to diff against")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    runs_dir = pathlib.Path(args.runs)
    rows = []
    for f in sorted(runs_dir.rglob("*.json")):
        if f.name.startswith(("results", "scores", "manifest")):
            continue
        rows.append(score_v110(load_journal(f)))

    out = {"scorer_version": "1.1.0", "rows": rows}

    prev = json.loads(pathlib.Path(args.diff).read_text())
    prev_by_id = {r.get("run_id"): r for r in prev.get("rows", [])}
    changed = []
    for r in rows:
        old = prev_by_id.get(r["run_id"])
        if old is None:
            changed.append({"run_id": r["run_id"], "fields": ["(new run)"]})
            continue
        diffs = [f for f in ("evaluable", "label", "outcome", "integrity",
                             "verification", "cost", "justification")
                 if r.get(f) != old.get(f)]
        if diffs:
            changed.append({"run_id": r["run_id"], "fields": diffs,
                            "old_cost": old.get("cost"), "new_cost": r.get("cost")})
    out["diff_from"] = str(args.diff)
    out["changed"] = changed

    print(f"rescore 1.1.0: {len(changed)} of {len(rows)} runs changed vs {args.diff}\n")
    for c in changed:
        old_w = (c.get("old_cost") or {}).get("wasted_steps", "-")
        new_w = (c.get("new_cost") or {}).get("wasted_steps", "-")
        print(f"  {c['run_id']}: {', '.join(c['fields'])}  (wasted_steps {old_w} -> {new_w})")

    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(out, indent=1))
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
