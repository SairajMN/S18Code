"""Full grid on local qwen3.8:27b. Paced so the machine can breathe.

Three things keep this off the fan:
  keep_alive   the 17 GB model loads once and stays resident, not per call
  COOLDOWN     a pause between runs, so heat has somewhere to go
  sequential   never two runs at once

Reasoning is left ON. It is the thing that makes this model good at noticing it
has failed, and noticing failure is exactly the axis under test. It is bounded
by num_predict rather than switched off: measured 2026-08-15, with think left on
and only 8 tokens it returns content:"" — a fully billed non-answer.
"""
import asyncio, dataclasses, os, json, pathlib, subprocess, sys, time, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from S18Code.harnesses.loop import Config, run_loop
from S18Code.tasks.materialise import materialise, run_tests
from S18Code.evals.axes import score

MODEL = "qwen3.8:27b"
COOLDOWN = 45          # seconds between runs
KEEP_ALIVE = "30m"

async def llm(prompt, system):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "stream": False, "think": True, "keep_alive": KEEP_ALIVE,
        "options": {"num_predict": 1200, "temperature": 0.2},
    }).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r).get("message", {}).get("content", "")
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(20)

# Discriminating tasks FIRST. Last run spent its whole budget on the easy ones
# and never reached the tasks carrying the hypothesis.
ORDER = ["t06_impossible_contradiction", "t07_impossible_no_input",
         "t04_cheatable_hard", "t05_specgame_pdf",
         "t01_average_empty", "t02_off_by_one", "t03_rounding"]

ARMS = [Config("baseline",  guard=False, ceiling=None),
        Config("s17_rules", guard=True,  ceiling=4)]

async def main():
    T = pathlib.Path(__file__).parent / "tasks"
    tasks = {json.loads(p.read_text())["id"]: json.loads(p.read_text()) for p in T.glob("t0*.json")}
    out = pathlib.Path(__file__).parent / "proofs" / "results_local.json"
    out.parent.mkdir(exist_ok=True)
    rows, n = [], 0

    order = [a for a in sys.argv[1:] if a in tasks] or ORDER
    total = len(order) * len(ARMS)
    reps = int(os.getenv('S18_REPEATS', '1'))
    total *= reps
    for tid in order:
        t = tasks[tid]
        for cfg in ARMS:
          for rep in range(reps):
            n += 1
            ws = materialise(t)
            t0 = time.time()
            try:
                run = await run_loop(t, ws, cfg, llm, MODEL)
            except Exception as e:
                print(f"  [{n}/{total}] {tid} {cfg.name} ABORTED {type(e).__name__}", flush=True)
                continue
            passed, tail = run_tests(ws, t)
            row = score(run, actually_passed=passed)
            row["kind"], row["claimed"], row["rep"] = t["kind"], run.claimed_success, rep
            rows.append(row)

            # The raw run, before any scorer touched it. `empty_billed` shipped
            # wrong once and could only be corrected by running the model for
            # another six hours; that is a bad trade to make twice. With this,
            # every axis is recomputable from disk forever.
            raw = pathlib.Path(__file__).parent / "proofs" / "runs"
            raw.mkdir(parents=True, exist_ok=True)
            (raw / f"{tid}__{cfg.name}__r{rep}.json").write_text(json.dumps(
                {**dataclasses.asdict(run), "actually_passed": passed,
                 "pytest_tail": tail, "kind": t["kind"],
                 "final_files": {f.name: f.read_text()[:4000]
                                 for f in sorted(ws.glob("*.py"))}}, indent=1))
            out.write_text(json.dumps({"model": MODEL, "date": "2026-08-15", "rows": rows}, indent=1))
            print(f"  [{n}/{total}] {tid:28s} {cfg.name:10s} solved={passed!s:5s} "
                  f"claimed={run.claimed_success!s:5s} cheat={row['cheated']!s:5s} "
                  f"steps={row['steps']:2d} {time.time()-t0:5.0f}s {run.error[:34]}", flush=True)
            if n < total:
                await asyncio.sleep(COOLDOWN)
    print(f"\n  wrote {out}  ({len(rows)}/{total} rows)")

asyncio.run(main())
