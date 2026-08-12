#!/usr/bin/env python3
"""Compare a paired run (two independent samples per case) against the
recorded baselines, reporting only what is decidable.

    uv run python tools/eval_run6_report.py 6a 6b

Why paired. Two runs of the *same unchanged system* disagree about as much
as the system disagrees with its previous version -- measured at Jaccard
0.524 and 3/18 identical for run4a vs run4b. A single run therefore cannot
show that anything changed. Sampling each case twice and reading the
reproducible subset is what separates signal from that noise floor.

What this reports, and what it deliberately does not:

  * sibling compliance -- decidable, and the thing the protocol was added
    to move. Baselines: run3 31%, run4a 28%, run4b 18%.
  * class-count inflation -- the failure mode the sibling rule invites. An
    answer that adds classes just to have siblings to dismiss satisfies the
    rule and is worse, so the count is reported beside the compliance.
  * domain findings -- from tools/eval_domains.py's rule, 9 across the 116
    pre-existing answers.
  * paired agreement -- Jaccard and exact-match over classes_proposed,
    against the 0.524 / 3-of-18 floor.

It reports no judged quality number. Judges are unreliable here: the same
rubric scored one run 17/24 and, re-run blind, 2/24. A judged figure is
only meaningful beside its own blinded control, which is a separate pass.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Recorded in HANDOFF.md from the runs that predate the sibling requirement.
BASELINE_COMPLIANCE = {"run3": (25, 81), "run4a": (23, 81), "run4b": (12, 65)}
BASELINE_PAIRED = {"identical": 3, "of": 18, "jaccard": 0.524}


def load_run(tag: str) -> dict[str, dict]:
    out = {}
    for path in sorted((DATA / "eval").glob(f"manswer{tag}-*.json")):
        case = path.stem[len(f"manswer{tag}-"):]
        out[case] = json.loads(path.read_text(encoding="utf-8"))
    return out


def classes_of(answer: dict) -> set[str]:
    return {str(c).strip().upper() for c in (answer.get("classes_proposed") or [])}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 1.0


def compliance(answers: dict, onto: dict) -> tuple[int, int]:
    """Proposed classes whose nearest rival was weighed, via eval_siblings."""
    from tools.eval_siblings import check, sibling_map

    siblings = sibling_map(onto)
    ok = total = 0
    for answer in answers.values():
        result = check(answer, siblings)
        ok += result["ok"]
        total += result["total"]
    return ok, total


def domain_findings(answers: dict, onto: dict) -> list[tuple[str, str, str]]:
    from tools.eval_domains import check

    out = []
    for case, answer in sorted(answers.items()):
        for f in check(answer, onto)["findings"]:
            out.append((case, f["property"], f["kind"]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("tag_a", help="first sample's run tag, e.g. 6a")
    ap.add_argument("tag_b", help="second sample's run tag, e.g. 6b")
    args = ap.parse_args()

    onto = json.loads((DATA / "ontology.json").read_text(encoding="utf-8"))
    a, b = load_run(args.tag_a), load_run(args.tag_b)
    paired = sorted(set(a) & set(b))

    print(f"run{args.tag_a}: {len(a)} answers   run{args.tag_b}: {len(b)} answers   "
          f"paired: {len(paired)}")
    if not paired:
        raise SystemExit("no cases answered by both runs; nothing to compare")
    missing = sorted((set(a) | set(b)) - set(paired))
    if missing:
        # Never silently narrow: an unpaired case is excluded from every
        # paired figure below and the reader has to know which.
        print(f"UNPAIRED (excluded from paired figures): {' '.join(missing)}")

    print("\n== sibling compliance (proposed classes whose rival was weighed) ==")
    for tag, answers in ((args.tag_a, a), (args.tag_b, b)):
        ok, total = compliance(answers, onto)
        pct = f"{100 * ok / total:.0f}%" if total else "n/a"
        print(f"  run{tag:4} {ok:3}/{total:3}  {pct}")
    print("  baselines, before the requirement existed:")
    for name, (ok, total) in BASELINE_COMPLIANCE.items():
        print(f"  {name:8} {ok:3}/{total:3}  {100 * ok / total:.0f}%")

    print("\n== class-count inflation check ==")
    for tag, answers in ((args.tag_a, a), (args.tag_b, b)):
        counts = [len(classes_of(x)) for x in answers.values()]
        print(f"  run{tag:4} mean {statistics.mean(counts):.2f} classes/answer  "
              f"median {statistics.median(counts):.1f}  max {max(counts)}  "
              f"total {sum(counts)}")
    for tag in ("4a", "4b"):
        prior = load_run(tag)
        if prior:
            counts = [len(classes_of(x)) for x in prior.values()]
            print(f"  run{tag:4} mean {statistics.mean(counts):.2f} classes/answer  "
                  f"median {statistics.median(counts):.1f}  max {max(counts)}  "
                  f"total {sum(counts)}   (baseline)")

    print("\n== class-count inflation, SAME CASES ONLY ==")
    # The global mean above is confounded by which cases a run covered: a
    # slice that genuinely needs extension classes lifts the average without
    # anyone padding. Comparing each case against its own history is what
    # separates inflation from slice composition.
    priors = {tag: load_run(tag) for tag in ("", "2", "3", "4a", "4b")}
    per_case = []
    for case in paired:
        hist = [len(classes_of(r[case])) for r in priors.values() if case in r]
        now = [len(classes_of(a[case])), len(classes_of(b[case]))]
        if hist:
            per_case.append((case, hist, now))
    if per_case:
        print(f"  {'case':20} {'prior runs':>22}  {'run6a/6b':>10}   prior mean -> run6")
        for case, hist, now in per_case:
            print(f"  {case:20} {str(hist):>22}  {str(now):>10}   "
                  f"{statistics.mean(hist):.2f} -> {statistics.mean(now):.2f}")
        flat_hist = [n for _, h, _ in per_case for n in h]
        flat_now = [n for _, _, w in per_case for n in w]
        pm, nm = statistics.mean(flat_hist), statistics.mean(flat_now)
        print(f"\n  prior mean {pm:.2f}   run6 mean {nm:.2f}   "
              f"delta {100 * (nm - pm) / pm:+.0f}%")
        at_or_above = sum(1 for _, h, w in per_case if min(w) >= max(h))
        print(f"  cases where BOTH run6 samples equal or exceed the case's own"
              f" historical maximum: {at_or_above}/{len(per_case)}")
        print("  This is the failure mode the sibling rule invites: an answer that"
              "\n  adds classes just to have siblings to dismiss satisfies the rule"
              "\n  and is worse. A large positive delta here outweighs a compliance"
              "\n  gain -- read the two together, never the compliance alone.")

    print("\n== paired agreement on classes_proposed ==")
    ident, js = 0, []
    rows = []
    for case in paired:
        sa, sb = classes_of(a[case]), classes_of(b[case])
        j = jaccard(sa, sb)
        js.append(j)
        if sa == sb:
            ident += 1
        rows.append((case, j, sorted(sa & sb), sorted(sa ^ sb)))
    print(f"  identical: {ident}/{len(paired)}   mean Jaccard {statistics.mean(js):.3f}")
    print(f"  noise floor (run4a vs run4b): "
          f"{BASELINE_PAIRED['identical']}/{BASELINE_PAIRED['of']}   "
          f"{BASELINE_PAIRED['jaccard']:.3f}")
    print("\n  per case (agreed core | disagreed):")
    for case, j, core, diff in rows:
        print(f"    {case:20} {j:.2f}  [{' '.join(core)}] | [{' '.join(diff)}]")

    agreed = [c for c, j, _, _ in rows if j == 1.0]
    print(f"\n  fully reproducible cases ({len(agreed)}): {' '.join(agreed) or '(none)'}")
    print("  Only these support a claim that a difference from a previous run"
          "\n  is real rather than resampling noise.")

    print("\n== domain findings (property proposed without the class carrying it) ==")
    for tag, answers in ((args.tag_a, a), (args.tag_b, b)):
        found = domain_findings(answers, onto)
        print(f"  run{tag}: {len(found)} finding(s) across {len(answers)} answers")
        for case, prop, kind in found:
            print(f"    {case:20} {prop:8} {kind}")
    print("  baseline: 9 across the 116 pre-existing answers (7.8% of answers)")

    print("\nNo judged quality figure is reported here. See the judging pass,"
          "\nwhich is only meaningful beside its own blinded control.")


if __name__ == "__main__":
    main()
