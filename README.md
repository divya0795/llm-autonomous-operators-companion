# Companion archive

Machine-readable artefacts for **A Design Framework for Sound LLM Operators of Distributed Systems: Autonomy Levels, Governing Laws, and a Reference Architecture** (Chukkapalli, 2026).

This archive backs the paper's *Data availability* statement.
Public mirror: <https://github.com/divya0795/llm-autonomous-operators-companion>.

## Contents

```
LICENSE                       # dual: MIT (code) + CC BY 4.0 (data)
CITATION.cff                  # how to cite this archive and the paper
search_log.csv                # per-query hit counts and screening decisions
evidence_matrix.csv           # the evidence matrix, one row per work (50 works)
evidence_matrix_recode.csv    # independent rule-based autonomy-level second coding, with per-row rationale
compute_recode_kappa.py       # reproduces the inter-coder Cohen's kappa (stdlib only)
taxonomy.yaml                 # taxonomy schema
operator-trace-bench/         # trace schema + stdlib contract validator + CPU pilot (see its README)
qaws_sim/qaws_sim.py          # QAWS attestation reference implementation + CPU-scale measurement
```

## Quick start (stdlib Python 3, no GPU)

```
python3 compute_recode_kappa.py
python3 operator-trace-bench/validate_trace.py operator-trace-bench/schema/example_trace.jsonl
python3 qaws_sim/qaws_sim.py
```

These artefacts check that the contracts are satisfiable and reproduce the paper's
reported statistics; they are not a production benchmark of operator agents.
