#!/usr/bin/env python3
"""Did the answer engage with the nearest rival to each class it proposed?

`search.py concept <id>` prints a siblings block -- the other subclasses of
the same parent, each with a one-line gloss -- because choosing between
siblings is what a modelling question mostly is. Two runs of the same system
showed the block being read and not acted on:

  * archives-c1 run4a ran `concept E10` as its SECOND query. That output lists
    E8 Acquisition, glossed "transfers of legal ownership from one or more
    instances of E39 Actor to one or more other instances of E39 Actor". The
    case is about ledgers formally donated in 2010. The answer neither
    proposed E8 nor rejected it. The other run proposed it, and the strict
    reviewer had already flagged its absence as an error.
  * built-c2 run4a ran `concept E4`, whose siblings block lists E93 Presence.
    Same outcome: not proposed, not rejected, and the reviewer had called E93
    the prescribed construct.

Neither is a retrieval failure. Retrieval is deterministic and both classes
were on screen. What is missing is the discipline of accounting for what was
shown, which `tools/EVAL_MODELLING_ANSWERING.md` asks for in prose ("if you
cannot say why the neighbouring class is wrong, you have not finished") and
nothing checked.

    uv run python tools/eval_siblings.py 'manswer4a-*.json'

The criterion is deliberately weak: **at least one** sibling per proposed
class. Requiring all of them was measured and rejected -- across 18 cases the
proposed classes have 405 siblings between them, about 22 per answer, and
demanding a line on each would buy padding rather than thought. E10 alone has
14. One forces engagement with the neighbourhood; fourteen forces filler.

Measured baseline before the requirement existed, over the same 18 cases:

    run3    25/81 proposed classes (31%) engaged with a sibling
    run4a   23/81 (28%)
    run4b   12/65 (18%)

so this is a real gap, not a formality already satisfied. (An earlier version
of this check reported 38/30/20 by matching identifiers against a JSON dump of
both fields; that credited a class whenever another entry happened to name it,
and inflated every figure. See `weighed_by_class`.)
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


def sibling_map(onto: dict) -> dict[str, set[str]]:
    """{class id: its siblings}, over CRMbase and the family extensions.

    A sibling is another subclass of any of this class's parents. The CRM
    hierarchy is a DAG, so a class with two parents has two sibling groups and
    both count -- E4 Period sits under E2 and E92, and E93 Presence is only
    reachable through the E92 side. That is exactly the sibling the built-c2
    answer needed, so collapsing to a single parent would hide the case this
    tool was written for.
    """
    from lib.ontology import _model_view

    classes, _ = _model_view(onto)
    children: dict[str, set[str]] = {}
    for cid, entry in classes.items():
        for parent in entry.get("sub_class_of") or []:
            children.setdefault(parent, set()).add(cid)
    out: dict[str, set[str]] = {}
    for cid, entry in classes.items():
        sibs: set[str] = set()
        for parent in entry.get("sub_class_of") or []:
            sibs |= children.get(parent, set())
        out[cid] = sibs - {cid}
    return out


_ID = re.compile(r"\b((?:E|P|S|O|A|AP|SP|I|F|R)\d{1,3})\b")


def weighed_by_class(answer: dict, siblings: dict[str, set[str]]) -> dict[str, set[str]]:
    """{proposed class: siblings it was actually weighed against}.

    `siblings_considered` is read structurally, not as text. Dumping it to a
    string and looking for identifiers credits the wrong class: an entry
    {"of": "E16", "sibling": ...} puts "E16" in the blob, and E16 is a sibling
    of E17, so a bogus entry about E16 silently satisfied E17. A mutation test
    caught that -- an entry naming a class that is not a sibling scored 1/5
    instead of 0/5.

    `rejected_alternatives` has no such structure, so its text is scanned with
    a word-boundary pattern; without the boundary "E1" matches inside "E16".
    A rejected alternative only credits the class whose sibling it names.
    """
    out: dict[str, set[str]] = {}
    for entry in answer.get("siblings_considered") or []:
        if not isinstance(entry, dict):
            continue
        of, sib = str(entry.get("of", "")), str(entry.get("sibling", ""))
        if sib and sib in siblings.get(of, set()):     # must really be a sibling
            out.setdefault(of, set()).add(sib)

    rejected_ids: set[str] = set()
    for entry in answer.get("rejected_alternatives") or []:
        text = json.dumps(entry, ensure_ascii=False) if isinstance(entry, dict) else str(entry)
        rejected_ids |= set(_ID.findall(text))
    for cid in {str(c) for c in (answer.get("classes_proposed") or [])}:
        hit = rejected_ids & siblings.get(cid, set())
        if hit:
            out.setdefault(cid, set()).update(hit)
    return out


def check(answer: dict, siblings: dict[str, set[str]]) -> dict:
    """Per proposed class: was at least one of its true siblings weighed?

    Both `rejected_alternatives` and `siblings_considered` count -- the point
    is that the rival was weighed, not which key recorded it. The answer prose
    is deliberately NOT searched: a class named in passing while explaining
    something else is not evidence it was considered and dismissed.
    """
    weighed = weighed_by_class(answer, siblings)
    proposed = sorted({str(c) for c in (answer.get("classes_proposed") or [])})
    rows = []
    for cid in proposed:
        sibs = siblings.get(cid, set())
        if not sibs:
            continue                       # a root or an only child: nothing to weigh
        named = sorted(weighed.get(cid, set()))
        rows.append({"class": cid, "siblings": len(sibs),
                     "named": named, "ok": bool(named)})
    return {
        "case_id": answer.get("case_id", "?"),
        "rows": rows,
        "ok": sum(1 for r in rows if r["ok"]),
        "total": len(rows),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("patterns", nargs="*", default=["manswer-*.json"])
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    paths = []
    for pattern in args.patterns:
        matched = sorted(Path().glob(pattern)) or sorted((DATA / "eval").glob(pattern))
        if not matched:
            raise SystemExit(f"pattern matched no files: {pattern!r}")
        paths += matched

    onto = json.loads((DATA / "ontology.json").read_text(encoding="utf-8"))
    siblings = sibling_map(onto)

    results = [check(json.loads(p.read_text(encoding="utf-8")), siblings) for p in paths]
    print(f"{'case':26} {'engaged':>8} {'of':>4}   classes with no sibling weighed")
    print("-" * 78)
    for r in sorted(results, key=lambda r: r["case_id"]):
        missing = [row["class"] for row in r["rows"] if not row["ok"]]
        print(f"{r['case_id']:26} {r['ok']:8} {r['total']:4}   {' '.join(missing)}")
    ok = sum(r["ok"] for r in results)
    total = sum(r["total"] for r in results)
    print(f"\nproposed classes whose nearest rival was weighed: {ok}/{total} "
          f"({100 * ok / total:.0f}%)" if total else "\nno proposed classes with siblings")


if __name__ == "__main__":
    main()
