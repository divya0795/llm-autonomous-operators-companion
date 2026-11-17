#!/usr/bin/env python3
"""Compute Cohen's kappa (inter-coder agreement) between the primary autonomy-level
coding (evidence_matrix.csv) and an independent rule-based second coding
(evidence_matrix_recode.csv), over Definition 1's {O, R, A, F, none} label set.

Stdlib only. Run:  python3 compute_recode_kappa.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_primary():
    out = {}
    with open(os.path.join(HERE, "evidence_matrix.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["bibkey"]] = row["autonomy_level"].strip()
    return out


def load_recode():
    a, b = [], []
    with open(os.path.join(HERE, "evidence_matrix_recode.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            a.append(row["autonomy_primary"].strip())
            b.append(row["autonomy_recode"].strip())
    return a, b


def cohen_kappa(a, b):
    assert len(a) == len(b)
    n = len(a)
    cats = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = {c: a.count(c) / n for c in cats}
    pb = {c: b.count(c) / n for c in cats}
    pe = sum(pa[c] * pb[c] for c in cats)
    kappa = (po - pe) / (1 - pe) if pe != 1 else 1.0
    return po, pe, kappa, n


def main():
    primary = load_primary()
    a, b = load_recode()
    # sanity: recode primary column must match evidence_matrix.csv
    with open(os.path.join(HERE, "evidence_matrix_recode.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            assert primary[row["bibkey"]] == row["autonomy_primary"].strip(), (
                "primary mismatch for %s" % row["bibkey"])
    po, pe, kappa, n = cohen_kappa(a, b)
    disagree = sum(1 for x, y in zip(a, b) if x != y)
    # subset over the 34 decision-loop (R/A/F) rows under the primary coding
    dl = [(x, y) for x, y in zip(a, b) if x in ("R", "A", "F")]
    dl_po = sum(1 for x, y in dl if x == y) / len(dl)
    print("rows (all):            %d" % n)
    print("disagreements:         %d" % disagree)
    print("observed agreement po: %.4f" % po)
    print("expected agreement pe: %.4f" % pe)
    print("Cohen's kappa (all):   %.4f" % kappa)
    print("decision-loop rows:    %d" % len(dl))
    print("decision-loop po:      %.4f" % dl_po)


if __name__ == "__main__":
    main()
