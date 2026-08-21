"""Write a task into a fresh workspace, and run its tests.

The tests are the ground truth and the agent never gets to write them. They are
materialised read-only-by-convention and the graders read them from the task
file, not from disk, so an agent that edits them on disk changes nothing about
the verdict.
"""
from __future__ import annotations

import json, pathlib, shutil, subprocess, tempfile


def materialise(task: dict, root: str | None = None) -> pathlib.Path:
    d = pathlib.Path(root or tempfile.mkdtemp(prefix="s18_"))
    if d.exists() and root is None:
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    for rel, body in {**task["files"], **task["tests"]}.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return d


def run_tests(workspace: pathlib.Path, task: dict) -> tuple[bool, str]:
    """Grade from the task's own tests, restored fresh.

    Restoring before grading is the whole guard: if the agent edited a test to
    make it pass, the edit is discarded and the original question is asked again.
    """
    for rel, body in task["tests"].items():
        p = workspace / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    r = subprocess.run(["python3", "-m", "pytest", "-q", "--no-header"],
                       cwd=workspace, capture_output=True, text=True, timeout=120)
    return r.returncode == 0, (r.stdout or r.stderr)[-400:]
