"""Pre-flight: check the model exists and that 429s are classified correctly.

Run this BEFORE the full grid. Two checks:

1. Model ID: hit Groq's /models endpoint and confirm the configured model is
   served. A typo here does not fail loudly; it quietly returns errors that a
   naive scorer records as agent failure. We were warned about exactly this.

2. Classification: run two single-task runs (t01, fast; t08, exercises guard),
   then score them and confirm any quota/error run lands in
   not_evaluable_under_this_manifest, never honest_failure. Discovered after
   60 journals are already scored wrong is the expensive way to learn this.
"""
import asyncio, json, os, pathlib, sys, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from S18Code.harnesses.loop import Config
from S18Code.harnesses.providers import _SSL, load_llm
from S18Code.scorer.score import not_evaluable, score_run
from S18Code.tasks.materialise import materialise, run_tests

MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")


def check_model_id() -> bool:
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).resolve().parent / ".env")
    load_dotenv()
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        print("  no GROQ_API_KEY; cannot check model list")
        return False
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}",
                 "User-Agent": "S18Code-eval/1.0 (python-urllib)"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=_SSL) as r:
            models = json.load(r)
    except Exception as e:
        print(f"  model list unavailable: {type(e).__name__}: {e}")
        return False
    ids = [m["id"] for m in models.get("data", [])]
    print(f"  {len(ids)} models served; looking for {MODEL!r}")
    if MODEL in ids:
        print(f"  OK: {MODEL} exists")
        return True
    close = [i for i in ids if "qwen" in i.lower()]
    print(f"  MISSING: {MODEL!r} not served. Qwen-family models available: {close}")
    return False


async def smoke_runs() -> bool:
    llm = load_llm()
    cfg = Config("s17_rules", guard=True, ceiling=4)
    tasks_dir = pathlib.Path(__file__).resolve().parent / "tasks"
    ok = True
    for tid in ("t01_average_empty", "t08_impossible_secret"):
        task = json.loads((tasks_dir / f"{tid}.json").read_text())
        ws = materialise(task)
        try:
            run = await run_loop_wrapper(task, ws, cfg, llm)
            passed, _ = run_tests(ws, task)
        except Exception as e:
            print(f"  {tid}: harness raised {type(e).__name__}: {e}")
            run = {"task_id": tid, "harness": "s17_rules", "ended": "llm_error",
                   "error": str(e)[:200], "calls": 0, "steps": [],
                   "actually_passed": False, "claimed_success": False}
            passed = False
        if isinstance(run, dict):
            journal = run
        else:
            from dataclasses import asdict
            journal = asdict(run)
            journal["actually_passed"] = passed
        label = ("not_evaluable_under_this_manifest"
                 if not_evaluable(journal) else "evaluable")
        scored = score_run(journal)
        hf = (scored.get("integrity") or {}).get("honest_failure", False)
        print(f"  {tid}: ended={journal.get('ended', '?')} calls={journal.get('calls', 0)} "
              f"label={label} honest_failure={hf} seconds={journal.get('seconds', 0):.0f}")
        if hf:
            ok = False
            print(f"    CLASSIFICATION BUG: honest_failure on a possibly-infrastructure run")
    return ok


async def run_loop_wrapper(task, ws, cfg, llm):
    from S18Code.harnesses.loop import run_loop
    return await run_loop(task, ws, cfg, llm, MODEL)


def main():
    print("preflight 1: model ID")
    model_ok = check_model_id()
    print("\npreflight 2: classification smoke test")
    class_ok = asyncio.run(smoke_runs())
    print(f"\nmodel_id={'OK' if model_ok else 'CHECK MANUALLY'} "
          f"classification={'OK' if class_ok else 'BROKEN'}")
    if not class_ok:
        sys.exit(1)
    if not model_ok:
        print("model ID unverified: fix GROQ_MODEL before running the grid")
        sys.exit(1)


if __name__ == "__main__":
    main()
