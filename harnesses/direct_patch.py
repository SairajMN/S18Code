"""Harness #3: single-shot direct patch.

The other two harnesses let the agent explore. This one removes exploration
entirely: dump every source file into one prompt, ask for a unified diff,
apply it, verify. One model call, one shot.

It is the cheapest possible harness and the easiest to fail at: the agent
never sees the test failures, so it must reason from source alone. Where the
other harnesses measure repair behaviour, this one measures one-shot
reasoning under the same policy.
"""
from __future__ import annotations

import pathlib, subprocess, time

from S18Code.harnesses.base import Step, TaskRun
from S18Code.harnesses.loop import Config


SYSTEM = """You are fixing code. You will see every source file and the task goal.
Reply with ONE unified diff (git format) that fixes the problem, and nothing else.
Format:
```diff
--- a/file.py
+++ b/file.py
@@ ...
```
Do not modify tests. Do not explain. Diff only, then a final line:
NOTE: <one line describing what you fixed and why>"""


def _apply_diff(diff_text: str, ws: pathlib.Path) -> tuple[bool, str]:
    diff_text = diff_text.strip()
    if diff_text.startswith("```"):
        lines = diff_text.splitlines()
        diff_text = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
    r = subprocess.run(["git", "apply", "-p1", "--unsafe-paths", "--directory=."],
                       cwd=ws, input=diff_text, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        r2 = subprocess.run(["patch", "-p1", "--fuzz=3"],
                            cwd=ws, input=diff_text, capture_output=True, text=True, timeout=30)
        return r2.returncode == 0, (r2.stdout or r2.stderr)[-300:]
    return True, (r.stdout or "applied")[-300:]


async def run_direct_patch(task: dict, ws: pathlib.Path, cfg: Config,
                           llm, model: str) -> TaskRun:
    run = TaskRun(task_id=task["id"], harness="direct_patch", model=model)
    t0 = time.time()

    sources = {}
    for rel, body in task["files"].items():
        sources[rel] = body
    listing = "\n\n".join(f"=== {k} ===\n{v}" for k, v in sources.items())

    prompt = f"Goal: {task['prompt']}\n\n{listing}\n\nProvide the unified diff now."
    run.calls += 1
    try:
        raw = await llm(prompt, SYSTEM)
    except Exception as e:
        run.error = f"llm: {type(e).__name__}"
        run.ended = "llm_error"
        run.seconds = time.time() - t0
        return run

    run.tokens += len(raw or "") // 4

    if "diff" not in (raw or "").lower() and "---" not in raw:
        run.unusable_replies += 1
        run.steps.append(Step("refused", "diff", False, "no diff found in reply"))
        run.ended = "max_steps"
        run.seconds = time.time() - t0
        return run

    ok, detail = _apply_diff(raw, ws)
    if ok:
        run.steps.append(Step("edit", "unified diff", True, detail))
        note = ""
        for line in (raw or "").splitlines():
            if line.startswith("NOTE:"):
                note = line[5:].strip()[:200]
                break
        run.claimed_success = True
        run.steps.append(Step("answer", detail=note))
        run.ended = "done"
    else:
        run.steps.append(Step("refused", "unified diff", False, f"apply failed: {detail}"))
        run.ended = "max_steps"

    run.seconds = time.time() - t0
    return run
