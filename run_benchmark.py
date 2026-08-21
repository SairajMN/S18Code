import asyncio, itertools, json, pathlib, sys, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from S18Code.harnesses.loop import Config, run_loop
from S18Code.tasks.materialise import materialise, run_tests
from S18Code.evals.axes import score

# Keys come from the environment. Set GEMINI_API_KEYS to a comma-separated list to
# rotate across several free-tier keys; a single GEMINI_API_KEY also works.
import os
KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", "")).split(",") if k.strip()]
if not KEYS:
    raise SystemExit("set GEMINI_API_KEY (or GEMINI_API_KEYS) before running this")
cyc = itertools.cycle(KEYS)
MODEL = "gemini-3.7-flash"

async def llm(prompt, system):
    body = json.dumps({"system_instruction":{"parts":[{"text":system}]},
        "contents":[{"role":"user","parts":[{"text":prompt}]}],
        "generationConfig":{"temperature":0.2,"maxOutputTokens":8192}}).encode()
    last=None
    for _ in range(len(KEYS)*2):
        k=next(cyc)
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={k}"
        req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=120) as r: d=json.load(r)
            return "".join(p.get("text","") for p in d["candidates"][0]["content"]["parts"])
        except Exception as e:
            last=e; await asyncio.sleep(1.5)
    raise RuntimeError(f"gemini unavailable: {last}")

ARMS = [Config("baseline",  guard=False, ceiling=None),
        Config("s17_rules", guard=True,  ceiling=4)]

async def main():
    T = pathlib.Path(__file__).parent / "tasks"
    tasks = [json.loads(p.read_text()) for p in sorted(T.glob("t0*.json"))]
    rows=[]
    for t in tasks:
        for cfg in ARMS:
            ws = materialise(t)
            run = await run_loop(t, ws, cfg, llm, MODEL)
            passed, _ = run_tests(ws, t)          # graded from the task file, edits discarded
            row = score(run, actually_passed=passed)
            row["kind"] = t["kind"]
            row["claimed"] = run.claimed_success
            rows.append(row)
            print(f"  {t['id']:28s} {cfg.name:10s} solved={passed!s:5s} claimed={run.claimed_success!s:5s} "
                  f"cheated={row['cheated']!s:5s} steps={row['steps']:2d} {run.error[:40]}", flush=True)
    out = pathlib.Path(__file__).parent / "proofs" / "results.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"model":MODEL,"date":"2026-08-15","rows":rows}, indent=1))
    print(f"\n  wrote {out}")

asyncio.run(main())
