#!/usr/bin/env python3
"""Decode blind three-way rankings and read the control BEFORE the result.

    uv run python tools/eval_rank_report.py <key.json> 'mrank6-*.json'

The design: each case's three answers are run4a, run6a and run6b, shuffled
into slots A/B/C. run6a and run6b are two independent samples of the SAME
system, so the judge should have no systematic preference between them. That
comparison is the control, and it is printed first, because if the judge
cannot separate two samples of one system then its preference for run6 over
run4a carries no information either.

This is the discipline HANDOFF records the hard way: the same rubric scored
one run 17/24 correct and, re-run blind, 2/24. A judged number without its
control is not evidence.

Nothing here reports a winner unless the control supports it.
"""

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data"


def load(pattern: str) -> dict[str, dict]:
    paths = sorted(glob.glob(pattern)) or sorted(
        str(p) for p in (DATA / "eval").glob(pattern))
    if not paths:
        raise SystemExit(f"pattern matched no files: {pattern!r}")
    out = {}
    for p in paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        out[d.get("case_id") or Path(p).stem] = d
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("key", help="the slot->run key written when inputs were built")
    ap.add_argument("pattern", nargs="?", default="mrank6-*.json")
    args = ap.parse_args()

    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    verdicts = load(args.pattern)
    cases = sorted(set(key) & set(verdicts))
    if not cases:
        raise SystemExit("no case has both a key entry and a verdict")
    missing = sorted(set(key) - set(verdicts))

    print(f"{len(cases)} of {len(key)} cases ranked")
    if missing:
        print(f"NOT YET RANKED (excluded): {' '.join(missing)}")

    # ---- the control, first ------------------------------------------------
    print("\n== CONTROL: run6a vs run6b (same system, so any systematic")
    print("            preference is judge noise, not signal) ==")
    a_over_b = b_over_a = 0
    adjacent = 0
    rows = []
    for case in cases:
        order = verdicts[case].get("ranking") or []
        slot_to_run = key[case]
        pos = {slot_to_run[s]: i for i, s in enumerate(order) if s in slot_to_run}
        if "run6a" not in pos or "run6b" not in pos:
            continue
        if pos["run6a"] < pos["run6b"]:
            a_over_b += 1
        else:
            b_over_a += 1
        if abs(pos["run6a"] - pos["run6b"]) == 1:
            adjacent += 1
        rows.append((case, pos))
    n = a_over_b + b_over_a
    print(f"  run6a ranked above run6b: {a_over_b}/{n}")
    print(f"  run6b ranked above run6a: {b_over_a}/{n}")
    print(f"  the two samples ranked ADJACENT (1st+2nd or 2nd+3rd): {adjacent}/{n}")
    if n:
        skew = abs(a_over_b - b_over_a) / n
        print(f"  split {a_over_b}-{b_over_a}; |skew| {skew:.2f}"
              f"  (0.00 = perfectly balanced, as it should be)")
        print("  Adjacency is the sharper test: two samples of one system should"
              "\n  bracket each other. Splitting them apart means the judge is"
              "\n  reacting to sampling noise as if it were quality.")

    # ---- confidence -------------------------------------------------------
    conf = Counter(bool(verdicts[c].get("confident")) for c in cases)
    print(f"\n  judge self-reported confident: {conf[True]}/{len(cases)}"
          f"   not confident: {conf[False]}/{len(cases)}")

    # ---- the result, second and conditional -------------------------------
    print("\n== RESULT: run6 vs run4a ==")
    wins = Counter()
    for case in cases:
        order = verdicts[case].get("ranking") or []
        slot_to_run = key[case]
        pos = {slot_to_run[s]: i for i, s in enumerate(order) if s in slot_to_run}
        if len(pos) < 3:
            continue
        best = min(pos, key=lambda r: pos[r])
        wins[best] += 1
        # how often did a run6 sample beat run4a, counting both samples
        for s in ("run6a", "run6b"):
            wins[f"{s} beat run4a"] += 1 if pos[s] < pos["run4a"] else 0
    print(f"  ranked first:  run4a {wins['run4a']}   run6a {wins['run6a']}"
          f"   run6b {wins['run6b']}")
    total = 2 * len([c for c in cases if len(key[c]) == 3])
    beat = wins["run6a beat run4a"] + wins["run6b beat run4a"]
    print(f"  a run6 sample ranked above run4a: {beat}/{total} pairings")

    # ---- breadth verdicts, the question the ranking exists to answer -------
    print("\n== BREADTH: is the extra breadth load-bearing, or padding? ==")
    per_run = {r: Counter() for r in ("run4a", "run6a", "run6b")}
    for case in cases:
        slot_to_run = key[case]
        for entry in (verdicts[case].get("per_answer") or []):
            slot = entry.get("label")
            if slot not in slot_to_run:
                continue
            per_run[slot_to_run[slot]][str(entry.get("breadth") or "?")] += 1
    labels = sorted({k for c in per_run.values() for k in c})
    print(f"  {'run':8}" + "".join(f"{l:>20}" for l in labels))
    for run, c in per_run.items():
        print(f"  {run:8}" + "".join(f"{c[l]:>20}" for l in labels))
    print("\n  'padding' counts against run6 directly; 'under-specified' against"
          "\n  run4a. This is the row that decides whether the +70% class-count"
          "\n  rise is the protocol working or the protocol being gamed.")

    print("\n== how to read this ==")
    print("  If the control is skewed or the two samples are rarely adjacent,")
    print("  the RESULT section above is noise and must not be reported as a")
    print("  finding. Read the control first, every time.")


if __name__ == "__main__":
    main()
