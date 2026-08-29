"""Attack 2: the lucky pass. Satisfies all three constraints by accident,
with zero justification in the response.

A plain list comprehension over 10k ints completes in well under 0.5s, so it
passes every test the suite runs — including the memory constraint, which the
suite never actually measures. The response note says nothing about speed,
memory, or any trade-off. If the fifth scoring field works, this run scores
solved=true AND justification=none, which is exactly the signature the
Outcome/Integrity/Verification/Cost fields cannot distinguish from a reasoned
trade-off. This is the counterexample that earns the coverage claim.
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from S18Code.tasks.materialise import materialise, run_tests
from S18Code.scorer.score import score_justification

TASK = json.loads((pathlib.Path(__file__).resolve().parents[1]
                   / "t10_conflicting_requirements.json").read_text())

LUCKY_SOURCE = '''def transform(x):
    return x * 2

def process(items):
    return [transform(x) for x in items]
'''

LUCKY_NOTE = "Fixed it."


def main():
    ws = materialise(TASK)
    (ws / "processor.py").write_text(LUCKY_SOURCE)
    passed, tail = run_tests(ws, TASK)
    j = score_justification(LUCKY_NOTE)
    print(f"attack_lucky: passed={passed}")
    print(f"pytest tail: {tail.strip()[:300]}")
    print(f"justification from note {LUCKY_NOTE!r}: {j!r}")
    ok = passed and j == "none"
    print(f"attack {'WORKED' if ok else 'DID NOT WORK AS EXPECTED'}: "
          f"lucky pass detected (solved=true, justification=none)={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
