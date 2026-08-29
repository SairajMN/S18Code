# Runs — how to reproduce everything

## Manifest (held fixed across both arms)

| Field | Value |
|---|---|
| Model | `qwen/qwen3.8-27b` via Groq API (verified live against `/models` on 2026-08-29 by `preflight.py`) |
| Provider | Groq, HTTP 429/5xx retried up to 6x with linear backoff (15s, 30s, …) |
| Policy version | see `policy.json` (`version` field) |
| Fixed config (Arm R) | `s17_rules`: guard=True, repeat-failure ceiling=4, max_steps=14 |
| Harnesses (Arm H) | `json_loop`, `cli_conversational`, `direct_patch` |
| Timeout | 120s per model call; 300s per pytest invocation |
| Seed | sampling seed = repeat_index (r0/r1/r2); temperature 0.7 |
| Scorer | `scorer/score.py`, version in `SCORER_VERSION` |
| Commit | recorded per-journal in `manifest.commit` |

## Arms

**Arm R** (statistical validity): 3 repeats x 10 tasks x `json_loop` = 30 runs.
Everything held fixed except sampling; the single fixed agent configuration is
`s17_rules`. Raw counts are reported as "N of 3" — a single run is an
observation, not a result.

**Arm H** (cross-harness): 1 run x 10 tasks x 3 harnesses = 30 runs. Task,
policy intent, scorer and manifest fields are identical across the three
harnesses; only the harness differs. What each harness changes:

- `json_loop` — the repo's existing JSON-action protocol (read/write/test/done)
- `cli_conversational` — same model, same policy, natural-language tool
  descriptions, regex-parsed free-text replies
- `direct_patch` — no exploration at all: every source file in one prompt,
  one unified diff back, applied and graded. One model call.

Do not conflate the two arms into one number. They answer different questions
and are reported as separate tables.

## Rerun end to end

```bash
# 0. one-time: put GROQ_API_KEY in .env (see .env.example), then:
pip install -r requirements.txt

# 1. preflight: verify the model ID is real and that infra failures
#    classify as not_evaluable, never honest_failure
python3 -m S18Code.preflight

# 2. run the full grid (60 runs, ~40-90 min on free tier with backoff)
python3 -m S18Code.run_evaluation            # both arms
python3 -m S18Code.run_evaluation r          # Arm R only
python3 -m S18Code.run_evaluation h          # Arm H only

# 3. score from journals only (never calls a model)
python3 -m S18Code.scorer.score --runs runs --out runs/scores_current.json

# 4. rescore demo: rule change re-applied to the SAME journals
python3 -m S18Code.scorer.rescore \
    --runs runs --diff runs/scores_current.json --out runs/scores_110.json
```

## Journal schema (one file per run, saved before scoring)

`runs/<arm>/<task>/<harness>/<run_id>.json`:

- `run_id`, `task_id`, `harness`, `model`
- `manifest` — full config: policy version, guard, ceiling, max_steps,
  timeout, seed, arm, repeat_index, commit, date
- `steps` — ordered events: kind (read/edit/command/answer/refused), target,
  ok, detail
- `claimed_success`, `actually_passed`, `pytest_tail`
- `verification` — command, exit_code, tail
- `error`, `ended` — llm_error / done / ceiling / max_steps
- `calls`, `unusable_replies`, `seconds`

Raw files are kept even when junk. A run that never did agent work is labeled
`not_evaluable_under_this_manifest` by the scorer, not deleted. A run that
made real progress and then died on quota is labeled `infrastructure_ended` —
its completed steps stay in the evidence pool; only its final claim is
discounted. The distinction between those two labels is the Section 8 trap,
and preflight.py verifies the classifier before the grid runs.

## Labels used in scored output

| Label | Meaning |
|---|---|
| `evaluable` | normal run, agent had a fair chance |
| `infrastructure_ended` | real progress made, then 429/network killed it mid-run |
| `not_evaluable_under_this_manifest` | never did agent work; says nothing about the agent |
