# replay_harness — CPU pilot

A scale-*down* reference implementation of the trace-replay protocol. It runs a
**toy, rule-based** operator agent over a single synthetic incident and writes a
trace that conforms to `../schema/trace_schema.yaml` and passes
`../validate_trace.py`.

## What this is and is not

- **IS:** a stdlib-only demonstration that the autonomy-invariant contract is
  *satisfiable* end-to-end — an agent decides observe / recommend / act over an
  incident, every actuation it emits respects its autonomy level, and the
  validator returns valid output on the produced trace.
- **IS NOT:** a real ML inference run, and not production-scale benchmark
  execution. There is no model, no GPU, no live system. The "agent" is a fixed
  rule set; the incident is synthetic.

## Run it (no install needed)

```
python cpu_pilot.py                 # writes pilot_trace.jsonl (stdlib only)
python ../validate_trace.py pilot_trace.jsonl
```

Both finish in seconds on a laptop CPU (well inside the < 5 min budget).

## Expected output shape

`cpu_pilot.py` writes ~12 JSONL records for `run_id = cpu-pilot-001`:
a mix of `observation`, `reasoning_step`, `tool_call`, and `actuation` events.
The actuations span three autonomy levels, each satisfying its invariant:

| autonomy_level | action_class           | invariant satisfied                          |
|----------------|------------------------|----------------------------------------------|
| R              | propose_scale_replicas | `proposal_only=true` (no state change)       |
| F              | restart_pod            | pod-scoped (<= declared) + `rollback_handle` |
| A              | scale_replicas         | non-empty `approval_token` + rollback handle |

`validate_trace.py` then prints a `RESULT: PASS` line, event-type counts, and a
metrics summary (actuations, blast-radius-violation rate `0.0000`,
unsafe-action rate `0.0000`) and exits 0.

## Scale-up path (optional)

To swap the toy rule set for a real LLM-driven agent, see
`requirements.txt` for the optional `torch`/`transformers` pins. The default
pilot does **not** import them; keep `cpu_pilot.py` emitting the same schema so
the same validator still applies.
