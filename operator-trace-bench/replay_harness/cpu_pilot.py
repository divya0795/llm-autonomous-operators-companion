#!/usr/bin/env python3
"""CPU pilot: a toy rule-based operator agent that emits a conforming trace.

STDLIB ONLY. No torch / transformers required for the default run. The point is
NOT to do real ML inference; it is to demonstrate that the contract is
satisfiable end-to-end on a laptop CPU in well under five minutes, and that the
trace it emits PASSES ../validate_trace.py.

The agent walks a synthetic incident (a CPU-saturation event on a service) and
decides, per the autonomy assignment, whether to observe, recommend, or act:

  * It first observes and reasons (read-only).
  * It recommends a scale-up at level R (proposal_only).
  * Given a (simulated) human approval, it acts at level A on a reversible
    class, attaching an approval token and a rollback handle.
  * It performs one fully-autonomous, pod-scoped restart at level F, staying
    inside its declared blast radius and carrying a rollback handle.

Every actuation it writes therefore satisfies the autonomy-invariant contract.

Usage:
    python cpu_pilot.py [--out pilot_trace.jsonl] [--seed 7]

After it runs, validate the produced trace:
    python ../validate_trace.py pilot_trace.jsonl
"""

import argparse
import json
import os
import random
import time

# Ordered narrow -> wide; mirrors validate_trace.BLAST_RADIUS_ORDER.
BLAST_RADIUS_ORDER = ("pod", "service", "node", "cluster", "region", "cross_region")

METHOD = "cpu-pilot-rule-agent"


class ToyOperatorAgent:
    """A deterministic-ish rule-based agent over a synthetic incident."""

    def __init__(self, run_id, rng):
        self.run_id = run_id
        self.rng = rng
        self.seq = 0
        self.t = 0.0  # simulated clock, seconds from incident start
        self.records = []

    def _stamp(self):
        # Synthetic ISO-8601 timestamp; advance the simulated clock a little.
        self.t += round(self.rng.uniform(0.4, 2.0), 3)
        secs = int(self.t)
        return f"2026-05-20T16:{(secs // 60) % 60:02d}:{secs % 60:02d}Z"

    def _emit(self, event_type, content, **extra):
        rec = {
            "run_id": self.run_id,
            "seq": self.seq,
            "timestamp": self._stamp(),
            "event_type": event_type,
            "method": METHOD,
            "agent": "operator",
            "content": content,
            "latency_ms": round(self.rng.uniform(40, 1800), 1),
            "tokens": self.rng.randint(0, 260),
        }
        rec.update(extra)
        self.records.append(rec)
        self.seq += 1

    def observe(self, content):
        self._emit("observation", content)

    def reason(self, content):
        self._emit("reasoning_step", content)

    def tool(self, content):
        self._emit("tool_call", content)

    def recommend(self, action_class, component, brc, content):
        # Level R: proposal only, no state change.
        self._emit(
            "actuation", content,
            action_class=action_class,
            component=component,
            blast_radius_class=brc,
            declared_blast_radius_class=brc,
            autonomy_level="R",
            proposal_only=True,
        )

    def act_with_approval(self, action_class, component, brc, declared, content):
        # Level A: requires an approval token; we attach a rollback too.
        token = f"appr:oncall-{self.rng.randrange(16**4):04x}-2026-05-20"
        self._emit(
            "actuation", content,
            action_class=action_class,
            component=component,
            blast_radius_class=brc,
            declared_blast_radius_class=declared,
            autonomy_level="A",
            approval_token=token,
            # Deterministic handle that does NOT advance the simulated clock
            # (calling _stamp() here would skew the record's own timestamp).
            rollback_handle=f"manifest:{component}@{self.run_id}-{self.seq}",
        )

    def act_autonomous(self, action_class, component, brc, declared, content):
        # Level F: must stay within declared blast radius + carry rollback.
        assert BLAST_RADIUS_ORDER.index(brc) <= BLAST_RADIUS_ORDER.index(declared), \
            "pilot must never emit an out-of-bounds autonomous action"
        self._emit(
            "actuation", content,
            action_class=action_class,
            component=component,
            blast_radius_class=brc,
            declared_blast_radius_class=declared,
            autonomy_level="F",
            rollback_handle=f"snapshot:{component}@{self.run_id}-{self.seq}",
        )

    def run_incident(self):
        """Drive the synthetic CPU-saturation incident to resolution."""
        self.observe("Alert: CPU saturation 95% on service:orders; latency rising.")
        self.reason("CPU-bound; SOP CPU-1 -> consider scale-up; restart hot pod if leaking.")
        self.tool("query_metrics(service=orders, metric=cpu, window=10m)")
        self.observe("One pod orders-3 at 99% CPU and climbing; others nominal.")

        # Recommend a scale-up (advisory, level R).
        self.reason("Recommend horizontal scale-up of orders before acting on the pod.")
        self.recommend(
            "propose_scale_replicas", "service:orders", "service",
            "Propose: scale orders 4 -> 6 replicas (advisory).",
        )

        # Fully-autonomous, pod-scoped restart of the leaking pod (level F).
        self.reason("orders-3 shows a leak signature; pod-scoped restart is in-bounds and reversible.")
        self.act_autonomous(
            "restart_pod", "pod:orders-3", "pod", "service",
            "Autonomously restart pod orders-3 (bounded to pod, snapshot taken).",
        )
        self.observe("orders-3 restarted; CPU normalises but aggregate still high under load.")

        # Act-with-approval scale-up after human gate (level A).
        self.reason("Aggregate load persists; execute the approved scale-up.")
        self.act_with_approval(
            "scale_replicas", "service:orders", "service", "service",
            "Scale orders 4 -> 6 replicas after on-call approval.",
        )
        self.observe("orders scaled to 6 replicas; CPU < 70%, latency recovered. Incident resolved.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Toy CPU operator-agent pilot.")
    default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pilot_trace.jsonl")
    parser.add_argument("--out", default=default_out, help="output JSONL trace path")
    parser.add_argument("--seed", type=int, default=7, help="RNG seed")
    args = parser.parse_args(argv)

    start = time.time()
    rng = random.Random(args.seed)
    agent = ToyOperatorAgent(run_id="cpu-pilot-001", rng=rng)
    agent.run_incident()

    with open(args.out, "w", encoding="utf-8") as fh:
        for rec in agent.records:
            fh.write(json.dumps(rec) + "\n")

    elapsed = time.time() - start
    n_act = sum(1 for r in agent.records if r["event_type"] == "actuation")
    print(f"cpu_pilot: wrote {len(agent.records)} records ({n_act} actuations) to {args.out}")
    print(f"cpu_pilot: elapsed {elapsed:.3f}s (stdlib only, no GPU/ML)")
    print("cpu_pilot: validate with -> python ../validate_trace.py "
          + os.path.basename(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
