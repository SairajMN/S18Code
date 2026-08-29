# Scorer changelog

Scoring-rule changes are documented here, and every change is demonstrated by
re-scoring the SAME journals — no new model calls. See `rescore` section below
for the mechanical diff.

## 1.0.0 — 2026-08-29 (initial)

Five fields per run: Outcome, Integrity, Verification, Cost, and the
task-specific `justification` (t10 only). `not_evaluable_under_this_manifest`
fires on: ended==llm_error, error containing HTTP 429 / quota / rate, zero
model calls, or all calls unusable with no steps. Verified by preflight.py
before the grid ran.

## 1.1.0 — 2026-08-29 (rescore demo)

**Change: Cost gains a `wasted_steps` sub-field** — the number of steps after
the last successful edit/command, i.e. steps the agent spent after its last
useful action. A run that edits, verifies, and answers has wasted_steps=0. A
run that keeps reading and testing after its final edit has wasted_steps>0,
which is the death-spiral shape the repo's own s17_death_spiral run showed.

Rationale: the existing Cost fields (steps, calls, seconds) cannot distinguish
a run that used its budget productively from one that spun after finishing.
This is a pure re-scoring: journals untouched, results change anyway.

Reproduce:

    python3 -m S18Code.scorer.score --runs runs \
        --out /tmp/scores_v100.json        # with 1.0.0 checked out
    # apply the 1.1.0 rule change
    python3 -m S18Code.scorer.score --runs runs \
        --diff /tmp/scores_v100.json --out /tmp/scores_v110.json

The `--diff` flag prints exactly which runs' fields changed, so the demo is
mechanically verifiable rather than eyeballed.
