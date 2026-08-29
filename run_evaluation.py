"""Run Arm R and Arm H. Save raw journals to disk before anything scores them.

Arm R  statistical validity: 3 repeats per task on ONE harness, everything
       held fixed except sampling. The fixed config is s17_rules (guard=True,
       ceiling=4) — that is the "one fixed agent configuration" the rubric
       asks for, and report.md names it explicitly.

Arm H  cross-harness: 1 run per task on each of 3 harnesses (json_loop,
       cli_conversational, direct_patch). Task, policy intent, scorer and
       manifest fields held conceptually identical; only the harness changes.

Journals land in runs/<arm>/<task>/<harness>/<run_id>.json with the schema
from principle #3: run_id, manifest, events, final_diff, verification. The
scorer reads these files and never calls a model.
"""
import asyncio, dataclasses, json, os, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from S18Code.harnesses.base import TaskRun
from S18Code.harnesses.cli_conversational import run_cli_conversational
from S18Code.harnesses.direct_patch import run_direct_patch
from S18Code.harnesses.loop import Config, run_loop
from S18Code.harnesses.providers import load_llm
from S18Code.tasks.materialise import materialise, run_tests

ROOT = pathlib.Path(__file__).resolve().parent
POLICY = json.loads((ROOT / "policy.json").read_text())
MODEL = POLICY["model"]
COOLDOWN = 20

HARNESSES = {
    "json_loop": run_loop,
    "cli_conversational": run_cli_conversational,
    "direct_patch": run_direct_patch,
}

ORDER = ["t10_conflicting_requirements", "t08_impossible_secret",
         "t09_impossible_strict_parity", "t06_impossible_contradiction",
         "t07_impossible_no_input", "t05_specgame_pdf", "t04_cheatable_hard",
         "t01_average_empty", "t02_off_by_one", "t03_rounding"]

ARMS = [Config("s17_rules", guard=True, ceiling=4)]


def git_sha() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def make_run_id(arm, task_id, harness, repeat) -> str:
    return f"arm{arm.lower()}_{task_id}_{harness}_r{repeat}"


async def run_one(arm, task, harness_name, repeat, llm) -> None:
    cfg = ARMS[0]
    fn = HARNESSES[harness_name]
    run_id = make_run_id(arm, task["id"], harness_name, repeat)
    ws = materialise(task)
    t0 = time.time()
    try:
        run = await fn(task, ws, cfg, llm, MODEL)
    except Exception as e:
        run = TaskRun(task_id=task["id"], harness=harness_name, model=MODEL,
                      error=f"{type(e).__name__}: {str(e)[:150]}", ended="llm_error")
    passed, tail = run_tests(ws, task)

    journal = dataclasses.asdict(run)
    journal.update({
        "run_id": run_id,
        "actually_passed": passed,
        "pytest_tail": tail,
        "kind": task.get("kind", ""),
        "final_note": next((s["detail"] for s in reversed(journal["steps"])
                            if s["kind"] == "answer" and s.get("detail")), ""),
        "manifest": {
            "task_id": task["id"],
            "model": MODEL,
            "harness": harness_name,
            "policy_version": POLICY["version"],
            "config": cfg.name,
            "guard": cfg.guard,
            "ceiling": cfg.ceiling,
            "max_steps": cfg.max_steps,
            "timeout_seconds": POLICY["timeout_seconds"],
            "seed": repeat,
            "arm": arm,
            "repeat_index": repeat,
            "commit": git_sha(),
            "date": time.strftime("%Y-%m-%d"),
        },
        "verification": {
            "command": "python3 -m pytest -q --no-header",
            "exit_code": 0 if passed else 1,
            "tail": tail[-200:],
        },
    })

    out = ROOT / "runs" / f"arm{arm.lower()}" / task["id"] / harness_name / f"{run_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(journal, indent=1))

    if run.ended == "llm_error" and run.calls == 0:
        label = "not_evaluable"
    elif run.ended == "llm_error":
        label = "infrastructure_ended"
    else:
        label = "evaluable"
    print(f"  {run_id:64s} solved={passed!s:5s} claimed={run.claimed_success!s:5s} "
          f"steps={len(run.steps):2d} {time.time()-t0:5.0f}s [{label}]", flush=True)


async def arm_r(llm) -> None:
    repeats = POLICY["arm_r"]["repeats"]
    tasks = {t["id"]: t for t in load_tasks()}
    total = len(ORDER) * repeats
    n = 0
    print(f"\nArm R: {ORDER and len(ORDER)} tasks x {repeats} repeats "
          f"(harness=json_loop, config=s17_rules) = {total} runs")
    for tid in ORDER:
        for rep in range(repeats):
            n += 1
            print(f"[{n}/{total}]", end=" ", flush=True)
            await run_one("R", tasks[tid], "json_loop", rep, llm)
            await asyncio.sleep(COOLDOWN)


async def arm_h(llm) -> None:
    harnesses = POLICY["arm_h"]["harnesses"]
    tasks = {t["id"]: t for t in load_tasks()}
    total = len(ORDER) * len(harnesses)
    n = 0
    print(f"\nArm H: {len(ORDER)} tasks x {len(harnesses)} harnesses "
          f"{harnesses} = {total} runs")
    for tid in ORDER:
        for hname in harnesses:
            n += 1
            print(f"[{n}/{total}]", end=" ", flush=True)
            await run_one("H", tasks[tid], hname, 0, llm)
            await asyncio.sleep(COOLDOWN)


def load_tasks():
    T = ROOT / "tasks"
    out = []
    for p in sorted(T.glob("t*.json")):
        out.append(json.loads(p.read_text()))
    return out


async def main():
    which = [a.lower() for a in sys.argv[1:] if a.lower() in ("r", "h")]
    which = which or ["r", "h"]
    llm = load_llm()
    if "r" in which:
        await arm_r(llm)
    if "h" in which:
        await arm_h(llm)


asyncio.run(main())
