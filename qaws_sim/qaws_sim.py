#!/usr/bin/env python3
"""QAWS reference implementation + CPU-scale measurement.

Quorum-Attested Window-Signed telemetry (QAWS), the attestation mechanism of
Section "A Concrete Attestation Mechanism" of the paper. This is a *mechanism-level*
reference implementation and measurement --- it demonstrates (1) that the quorum
rule rejects a grounding-channel forgery and accepts the true aggregate under the
k>=2f+1 condition, and (2) that the agent's per-decision verification cost grows as
O(k + m*log n), sub-linear in event volume n. It is NOT a benchmark of operator
agents on real telemetry; that empirical sequel is left to a live testbed
(see the paper's Open Problems).

Stdlib only (hashlib/hmac stand in for a real signature scheme; the asymptotics and
the quorum-rejection property are independent of the signature primitive).

Run:  python3 qaws_sim.py
"""
import hashlib
import hmac
import math
import os

KEYS = {}  # collector_id -> secret key (stand-in for a signing key)


def _h(b):
    return hashlib.sha256(b).digest()


def sign(collector_id, msg):
    return hmac.new(KEYS[collector_id], msg, hashlib.sha256).digest()


def verify(collector_id, msg, sig):
    return hmac.compare_digest(sign(collector_id, msg), sig)


def merkle_root(leaves):
    """Merkle root over a list of byte leaves. Returns (root, levels) so an
    inclusion proof can be extracted."""
    if not leaves:
        return _h(b""), [[_h(b"")]]
    level = [_h(x) for x in leaves]
    levels = [level]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(_h(a + b))
        level = nxt
        levels.append(level)
    return level[0], levels


def inclusion_proof(levels, idx):
    proof = []
    for level in levels[:-1]:
        sib = idx ^ 1
        sib = sib if sib < len(level) else idx  # duplicate-last padding
        proof.append(level[sib])
        idx //= 2
    return proof


def verify_inclusion(leaf, idx, proof, root):
    h = _h(leaf)
    for sib in proof:
        if idx % 2 == 0:
            h = _h(h + sib)
        else:
            h = _h(sib + h)
        idx //= 2
    return h == root


class Collector:
    """A telemetry collector in an independent trust domain."""

    def __init__(self, cid):
        self.cid = cid
        KEYS[cid] = _h(("key-%d" % cid).encode())

    def window(self, wid, events, forged_aggregate=None):
        # events: list of (event_id_bytes). aggregate := count (a decision-relevant
        # scalar); a forger reports forged_aggregate but still signs its own data.
        leaves = list(events)
        root, levels = merkle_root(leaves)
        agg = forged_aggregate if forged_aggregate is not None else len(events)
        msg = b"%d|%s|%d" % (wid, root.hex().encode(), agg)
        sig = sign(self.cid, msg)
        return {"cid": self.cid, "wid": wid, "root": root, "levels": levels,
                "agg": agg, "msg": msg, "sig": sig}


def agent_accept(tuples, k, f, epsilon, cited=()):
    """Agent acceptance rule. Returns (accepted_aggregate or None, verify_ops)."""
    q = k - f
    ops = 0
    # (i) verify every signature
    good = []
    for t in tuples:
        ops += 1  # one signature verification
        if verify(t["cid"], t["msg"], t["sig"]):
            good.append(t)
    # (ii) quorum: largest agreeing-within-epsilon cluster of >= q collectors
    accepted = None
    for t in good:
        cluster = [u for u in good if abs(u["agg"] - t["agg"]) <= epsilon]
        if len(cluster) >= q:
            accepted = t["agg"]
            break
    # (iii) verify Merkle inclusion proofs for cited events against a quorum root
    if accepted is not None and cited:
        ref = next(u for u in good if abs(u["agg"] - accepted) <= epsilon)
        for (leaf, idx) in cited:
            proof = inclusion_proof(ref["levels"], idx)
            ops += len(proof)  # ~log2(n) hash ops per cited event
            verify_inclusion(leaf, idx, proof, ref["root"])
    return accepted, ops


def scenario(k, f, n=1024, epsilon=0):
    """Honest vs adversarial window. Adversary controls f collectors that report a
    forged aggregate (true aggregate = n). Returns dict of outcomes."""
    cols = [Collector(i) for i in range(k)]
    true_events = [b"e%d" % j for j in range(n)]
    forged = n + 100  # forged aggregate, > epsilon away from truth

    honest_tuples = [c.window(1, true_events) for c in cols]
    h_acc, _ = agent_accept(honest_tuples, k, f, epsilon)

    adv_tuples = []
    for i, c in enumerate(cols):
        if i < f:  # adversary-controlled collectors forge
            adv_tuples.append(c.window(1, [b"x%d" % j for j in range(forged)],
                                       forged_aggregate=forged))
        else:
            adv_tuples.append(c.window(1, true_events))
    a_acc, _ = agent_accept(adv_tuples, k, f, epsilon)

    return {"k": k, "f": f, "q": k - f, "bound_ok": k >= 2 * f + 1,
            "honest_accepts_truth": h_acc == n,
            "adv_accepts_truth": a_acc == n,
            "adv_accepts_forgery": a_acc == forged,
            "adv_withholds": a_acc is None}


def cost_table(k=5, f=2, m=4):
    rows = []
    for n in (100, 1000, 10_000, 100_000, 1_000_000):
        events = [b"e%d" % j for j in range(n)]
        cols = [Collector(i) for i in range(k)]
        tuples = [c.window(1, events) for c in cols]
        cited = [(events[j], j) for j in range(m)]
        _, ops = agent_accept(tuples, k, f, epsilon=0, cited=cited)
        rows.append((n, ops, n, round(n / ops, 1)))
    return rows


def main():
    print("=== QAWS forgery-rejection (k>=2f+1 => q=k-f) ===")
    print("k  f  q  bound  honest->truth  adv->truth  adv->forgery  withholds")
    for (k, f) in [(3, 1), (5, 2), (7, 3), (9, 4)]:
        r = scenario(k, f)
        print("%-2d %-2d %-2d %-5s  %-13s  %-10s  %-12s  %s" % (
            r["k"], r["f"], r["q"], r["bound_ok"], r["honest_accepts_truth"],
            r["adv_accepts_truth"], r["adv_accepts_forgery"], r["adv_withholds"]))
    print("\n=== boundary: violate k>=2f+1 (f too large) ===")
    for (k, f) in [(4, 2), (5, 3)]:  # 2f+1 > k
        r = scenario(k, f)
        print("k=%d f=%d q=%d bound_ok=%s adv_accepts_forgery=%s" % (
            r["k"], r["f"], r["q"], r["bound_ok"], r["adv_accepts_forgery"]))
    print("\n=== verification cost vs event volume n (k=5, f=2, m=4 cited) ===")
    print("n          verify_ops   naive_O(n)   speedup")
    for (n, ops, naive, speed) in cost_table():
        print("%-10d %-12d %-12d %sx" % (n, ops, naive, speed))


if __name__ == "__main__":
    main()
