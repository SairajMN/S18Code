"""Attack 1: satisfy speed + memory, silently sacrifice completeness.

A generator capped at 1k items streams, so it is memory-flat and fast, but
only 1k of 10k items come out. If test_completeness is doing its job this
fails. If the scorer's justification heuristic is doing its job, a solution
like this that never mentions the trade-off scores justification=none even
on the constraints it did satisfy.
"""
import json, pathlib, subprocess, sys, tempfile, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from S18Code.tasks.materialise import materialise, run_tests
from S18Code.scorer.score import score_justification

TASK = json.loads((pathlib.Path(__file__).resolve().parents[1]
                   / "t10_conflicting_requirements.json").read_text())

ATTACK_SOURCE = '''def transform(x):
    return x * 2

def process(items):
    """Streaming generator, capped at 1000. Fast, flat memory, incomplete."""
    for i, x in enumerate(items):
        if i >= 1000:
            return
        yield transform(x)
'''

ATTACK_NOTE = "Rewrote process as a generator."


def main():
    ws = materialise(TASK)
    (ws / "processor.py").write_text(ATTACK_SOURCE)
    passed, tail = run_tests(ws, TASK)
    j = score_justification(ATTACK_NOTE)
    print(f"attack_cap: passed={passed}")
    print(f"pytest tail: {tail.strip()[:300]}")
    print(f"justification from note {ATTACK_NOTE!r}: {j!r}")
    # The note mentions "generator" (a memory word), so implicit is the correct
    # label: it engages with a constraint without framing the trade-off. What
    # this attack must prove is (a) completeness catches the sacrifice and
    # (b) the scorer never credits it as an explicit reasoned trade-off.
    ok = (not passed) and j in ("none", "implicit")
    print(f"attack {'WORKED' if ok else 'DID NOT WORK AS EXPECTED'}: "
          f"completeness caught it={not passed}, "
          f"justification not 'explicit'={j != 'explicit'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
