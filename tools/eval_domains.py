#!/usr/bin/env python3
"""Was every proposed property given the class that carries it?

A property is declared on a domain. An answer that recommends `P70
documents` without ever saying that something is an E31 Document has not
given the reader a model they can instantiate -- the recommendation is
incomplete, whether or not it is wrong.

    uv run python tools/eval_domains.py 'manswer4a-*.json'

Nine such findings exist across the 116 answers in data/eval/, all nine
hand-verified. The pattern is consistent: the answer names the missing
entity in prose ("the grave cut is a physical feature that occupies an E53
Place", "the 1839 tithe survey record documents...") and never assigns it a
class.

**Range is deliberately NOT checked.** Measured over the same corpus,
requiring a proposed class for each property's RANGE produces 133 flags,
dominated by E39 Actor (51), E52 Time-Span (21), E18 Physical Thing (18)
and E55 Type (10). Those are plumbing -- nobody lists Time-Span as a
modelling decision -- so the range direction is all noise. Do not add it.

Answer PROSE is also not scanned, for the reason tools/eval_siblings.py
already gives: a class named in passing while explaining something else is
not evidence it was proposed. Tested rather than assumed here -- unioning
prose-named classes into classes_proposed moves the run4a-vs-run4b noise
floor from 0.524 to 0.514 and from 3/18 to 2/18 identical. It adds noise in
both directions; the divergence between runs is real.
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_DOTTED = re.compile(r"^([A-Z]{1,3}\d{1,3})\.(\d)$")


def satisfied_classes(onto: dict, proposed) -> set[str]:
    """Every class an instance of some proposed class also is.

    A property declared on E7 Activity applies to an E12 Production, so the
    ancestor closure -- not the literal list -- is what a domain must be
    found in. CRMbase and the family extensions are merged, because the
    hierarchy genuinely crosses models (CRMarchaeo declares A1 a subclass of
    E12, so an A1 inherits CRMbase properties through it).
    """
    from lib.ontology import _ancestors_in, _model_view

    classes, _ = _model_view(onto)
    out: set[str] = set()
    for cid in proposed:
        cid = str(cid).strip().upper()
        if cid in classes:
            out |= _ancestors_in(classes, cid)
    return out


def orphan_classes(onto: dict, proposed) -> list[str]:
    """Proposed classes with no recorded parent.

    122 of 219 extension classes have none -- FRBRoo 49, CRMdig 22, LRM 11
    -- because FRBRoo is PDF-sourced and has no declaration card to scrape a
    hierarchy from. Such a class satisfies only itself, so a finding in an
    answer that proposes one may be incompleteness in the family data rather
    than in the answer. Reported alongside the finding, never used to
    suppress it.
    """
    from lib.ontology import _model_view

    classes, _ = _model_view(onto)
    out = []
    for cid in proposed:
        cid = str(cid).strip().upper()
        entry = classes.get(cid)
        if entry is not None and not (entry.get("sub_class_of") or []):
            out.append(cid)
    return sorted(out)


def resolve(onto: dict, pid: str) -> tuple[str | None, str]:
    """(canonical id, kind) for a proposed property identifier.

    kind is "plain", "inverse", "dotted" or "unknown". The inverse form
    matters because it swaps which end of the property the subject sits at:
    P108 has produced is E12 -> E22, so P108i is produced by attaches to the
    E22. Dotted ids are property-of-property declarations (P14.1 in the role
    of); they have no class-valued domain at all and take their own rule.
    """
    from lib.ontology import _model_view

    _, properties = _model_view(onto)
    ident = str(pid).strip().upper()

    if _DOTTED.fullmatch(ident):
        return (ident, "dotted") if ident in (onto.get("property_of_property") or {}) \
            else (None, "unknown")
    if ident in properties:
        return ident, "plain"
    if ident.endswith("I") and ident[:-1] in properties:
        return ident[:-1], "inverse"
    return None, "unknown"


def check(answer: dict, onto: dict) -> dict:
    """Per proposed property: is the class it attaches to also proposed?"""
    from lib.ontology import _model_view

    _, properties = _model_view(onto)
    proposed_classes = answer.get("classes_proposed") or []
    proposed_props = [str(p).strip().upper()
                      for p in (answer.get("properties_proposed") or [])]
    satisfied = satisfied_classes(onto, proposed_classes)
    orphans = orphan_classes(onto, proposed_classes)

    # Canonical form of every proposed property, so the dotted rule's
    # membership test below compares like with like. proposed_props holds
    # raw uppercased strings -- an answer that proposes "P14i" (P14's
    # inverse) alongside "P14.1" names P14 just as much as one that writes
    # "P14" plainly, but a literal-string check misses that: confirmed by
    # hand, ["P14i", "P14.1"] was flagged as missing P14 while ["P14",
    # "P14.1"] correctly was not.
    canonical_proposed = {resolve(onto, p)[0] for p in proposed_props} - {None}

    findings = []
    for raw in proposed_props:
        canonical, kind = resolve(onto, raw)
        if kind == "unknown":
            findings.append({"property": raw, "kind": "unknown",
                             "needs": None, "orphans": orphans})
            continue
        if kind == "dotted":
            base = (onto["property_of_property"][canonical]).get("of_property")
            if base and base not in canonical_proposed:
                findings.append({"property": raw, "kind": "dotted",
                                 "needs": base, "orphans": orphans})
            continue
        entry = properties[canonical]
        # The inverse direction attaches to the declared RANGE.
        needs = entry.get("range") if kind == "inverse" else entry.get("domain")
        if needs and needs not in satisfied:
            findings.append({"property": raw, "kind": "domain",
                             "needs": needs, "orphans": orphans})

    return {"case_id": answer.get("case_id", "?"),
            "findings": findings,
            "checked": len(proposed_props)}


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("patterns", nargs="*", default=["manswer-*.json"])
    args = ap.parse_args()

    paths = []
    for pattern in args.patterns:
        matched = sorted(Path().glob(pattern)) or sorted((DATA / "eval").glob(pattern))
        if not matched:
            raise SystemExit(f"pattern matched no files: {pattern!r}")
        paths += matched

    onto = json.loads((DATA / "ontology.json").read_text(encoding="utf-8"))

    total_checked = total_findings = 0
    print(f"{'case':26} {'property':9} {'kind':8} needs")
    print("-" * 78)
    for path in paths:
        answer = json.loads(path.read_text(encoding="utf-8"))
        result = check(answer, onto)
        total_checked += result["checked"]
        total_findings += len(result["findings"])
        for f in result["findings"]:
            note = ""
            if f["orphans"]:
                note = (f"   (no recorded hierarchy for {' '.join(f['orphans'])}"
                        " -- may be a family-data gap)")
            print(f"{result['case_id']:26} {f['property']:9} {f['kind']:8} "
                  f"{f['needs'] or '?'}{note}")

    print(f"\n{total_findings} finding(s) across {total_checked} proposed "
          f"properties in {len(paths)} answer(s).")
    print("Range is not checked; see this tool's docstring for the measurement.")


if __name__ == "__main__":
    main()
