#!/usr/bin/env python3
"""Screen modelling cases against the corpus they are meant to test.

A case that restates something the specification or the mailing list already
works through measures recitation, not reasoning. Authors are blind to the
corpus, so this is the check that their independence actually held.

Single-term frequency is the wrong signal: "engraving" or "kiln" will occur
somewhere in 26 years of a cultural-heritage list, and that says nothing. What
matters is CO-OCCURRENCE -- whether one message or one section of the spec
already contains most of what makes this case distinctive. That is the
fingerprint of the same scenario being discussed.

    uv run python tools/eval_novelty.py
"""

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
EVAL = DATA / "eval"

# A case is flagged when one corpus document holds at least this many of its
# distinctive terms. Two is ordinary vocabulary overlap; three in one place
# starts to look like the same example.
CO_OCCURRENCE_LIMIT = 3


def corpus():
    """Every unit a scenario could already live in, as (label, lowered text)."""
    units = []
    docs = DATA / "documents.jsonl"
    if docs.exists():
        for line in open(docs, encoding="utf-8"):
            r = json.loads(line)
            where = r.get("concept_id") or " > ".join(r.get("section_path") or [])
            units.append((f"spec:{where}", r["text"].lower()))
    clean = DATA / "clean.jsonl"
    if clean.exists():
        for line in open(clean, encoding="utf-8"):
            r = json.loads(line)
            units.append((f"mail:{r['id']}", f"{r['subject']}\n{r['body']}".lower()))
    return units


def screen(case: dict, units) -> dict:
    terms = [t.lower().strip() for t in case.get("distinctive_terms") or [] if t.strip()]
    # Word-boundary matching so "kiln" does not fire on "kilns" being absent
    # while "ill" fires inside "still".
    patterns = {t: re.compile(rf"\b{re.escape(t)}\b") for t in terms}

    per_term = {t: 0 for t in terms}
    worst, worst_where, worst_terms = 0, "", []
    for label, text in units:
        present = [t for t, p in patterns.items() if p.search(text)]
        for t in present:
            per_term[t] += 1
        if len(present) > worst:
            worst, worst_where, worst_terms = len(present), label, present

    return {
        "terms": len(terms),
        "per_term_documents": per_term,
        "max_co_occurrence": worst,
        "where": worst_where,
        "which": worst_terms,
        "verdict": "REVIEW" if worst >= CO_OCCURRENCE_LIMIT else "novel",
    }


def main() -> None:
    units = corpus()
    print(f"screening against {len(units):,} corpus units "
          f"(spec sections + mailing-list messages)\n")
    cases, flagged = [], 0
    for path in sorted(EVAL.glob("modelling-*.json")):
        slice_name = path.stem.removeprefix("modelling-")
        try:
            authored = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  SKIP {path.name}: unparseable ({exc})")
            continue
        for n, case in enumerate(authored, 1):
            result = screen(case, units)
            case_id = f"{slice_name}-c{n}"
            cases.append({"case_id": case_id, "slice": slice_name, **case,
                          "novelty": result})
            mark = "  " if result["verdict"] == "novel" else "**"
            print(f"{mark} {case_id:26} {result['verdict']:6} "
                  f"max {result['max_co_occurrence']}/{result['terms']} terms in one unit")
            if result["verdict"] != "novel":
                flagged += 1
                print(f"      {result['where']}")
                print(f"      shared: {result['which']}")

    out = EVAL / "modelling_cases.json"
    out.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(cases)} cases, {flagged} flagged for review -> {out}")
    if flagged:
        print("A flag is not automatic rejection: read the unit and decide "
              "whether it is the same scenario or coincidental vocabulary.")


if __name__ == "__main__":
    main()
