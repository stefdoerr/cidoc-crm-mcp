#!/usr/bin/env python3
"""Check that citations in a produced answer resolve to real things.

Answer quality needs a judge. Whether a citation EXISTS does not -- it is
decidable, and deciding it mechanically removes the one thing a judge is worst
at. The blind archive evaluation showed the system's characteristic failure is
a confident answer with fabricated support, which reads exactly like a good
answer unless you already know better. This is the check that tells them apart.

    uv run python tools/eval_citations.py data/eval/manswer-*.json

Existence turned out not to be enough. The modelling-advice evaluation
resolved 297 citations this way with zero invented identifiers, and two were
still wrong: a thread cited for a line no participant in it wrote, and a
phrase attributed to a thread that never uses that wording. A reviewer with
full archive access confirmed one of them anyway. Containment is just as
decidable as existence, so a citation may now also carry a `quote`, checked
against the real source text via `Retriever.find_quote` -- see lib/retrieve.py.
The existence-only path (a bare string citation) is unchanged.
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data"
# tools/ is not the project root, so `lib` (used only for the quote
# containment check below) is not importable without this -- unlike
# search.py, which sits at the root and gets it for free.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CRM_ID = re.compile(r"\b([EP]\d{1,3})(?:\.\d)?i?\b")
THREAD_ID = re.compile(r"\bt\d{4}\b")
EPISODE_ID = re.compile(r"\bt\d{4}-e\d+\b")
SECTION = re.compile(r"\[([^\]]{4,120})\]")


def load():
    onto = json.loads((DATA / "ontology.json").read_text(encoding="utf-8"))
    known_ids = (set(onto["classes"]) | set(onto["properties"])
                 | set(onto["historical"]) | set(onto.get("extensions", {})))
    threads = set(json.loads((DATA / "threads.json").read_text(encoding="utf-8")))
    episodes, sections = set(), set()
    ep_path = DATA / "episodes.jsonl"
    if ep_path.exists():
        for line in open(ep_path, encoding="utf-8"):
            episodes.add(json.loads(line)["episode_id"])
    doc_path = DATA / "documents.jsonl"
    if doc_path.exists():
        for line in open(doc_path, encoding="utf-8"):
            r = json.loads(line)
            if r.get("section_path"):
                sections.add(" > ".join(r["section_path"]).lower())
            if r.get("heading"):
                sections.add(r["heading"].lower())
    return known_ids, threads, episodes, sections


def citation_entries(citations: list) -> tuple[list[str], list[tuple[str, str]]]:
    """Split a raw `citations` list into what the existing existence scan
    reads (plain strings) and the (source_id, quote) pairs the new
    containment check verifies.

    A citation stays a bare string for existence-only checking -- the
    behaviour every existing answer file already relies on -- or becomes
    `{"id": "<same string as before>", "quote": "<phrase>"}` to additionally
    assert that the phrase actually occurs in that source. Only the second
    key is new; the first is unchanged so a mixed list still existence-checks
    every entry exactly as before.
    """
    tokens: list[str] = []
    quote_checks: list[tuple[str, str]] = []
    for c in citations or []:
        if isinstance(c, dict):
            cid = c.get("id") or c.get("source") or ""
            tokens.append(cid)
            if c.get("quote"):
                quote_checks.append((cid, c["quote"]))
        else:
            tokens.append(str(c))
    return tokens, quote_checks


def check(text: str, known_ids, threads, episodes, sections,
          quote_checks: list[tuple[str, str]] | None = None, retriever=None) -> dict:
    found = {
        "crm_ids": sorted({m.group(1) for m in CRM_ID.finditer(text)}),
        "threads": sorted(set(THREAD_ID.findall(text))),
        "episodes": sorted(set(EPISODE_ID.findall(text))),
    }
    bad = {
        # An invented identifier is the clearest possible fabrication: the
        # vocabularies are closed and finite.
        "crm_ids": [i for i in found["crm_ids"] if i not in known_ids],
        "threads": [t for t in found["threads"] if t not in threads],
        "episodes": [e for e in found["episodes"] if e not in episodes],
    }
    # Bracketed spans are only treated as section citations when they look like
    # one; ordinary bracketed prose must not be scored as a bad citation.
    claimed_sections = [
        s for s in SECTION.findall(text)
        if " > " in s or s.lower() in sections
    ]
    bad["sections"] = [s for s in claimed_sections if s.lower() not in sections]
    # Existence of the source is necessary but not sufficient: t1022 is a
    # real thread and still doesn't contain the line once attributed to it.
    # A quote is checked against the source named alongside it, not folded
    # into `found`/`bad` above -- containment is a different question from
    # "does this id exist", and reports separately for the same reason.
    bad["quotes"] = []
    for source_id, quote in (quote_checks or []):
        result = retriever.find_quote(source_id, quote)
        if not result.get("found"):
            bad["quotes"].append(f"{source_id}: {quote!r} not found")
    total = sum(len(v) for k, v in found.items()) + len(claimed_sections) + len(quote_checks or [])
    wrong = sum(len(v) for v in bad.values())
    return {
        "cited": total,
        "unresolvable": wrong,
        "detail": {k: v for k, v in bad.items() if v},
        "grounded": total > 0 and wrong == 0,
    }


def main() -> None:
    known_ids, threads, episodes, sections = load()
    # Cheap to construct regardless of whether any file uses `quote`:
    # Retriever() only computes paths at init, and find_quote() never touches
    # Chroma or an embedding model -- see lib/retrieve.py.
    from lib.retrieve import Retriever

    retriever = Retriever()
    # A pattern that matches nothing must be an error, never a quiet fallback
    # to the default set. It silently reported one run's results under
    # another run's name for a whole evaluation: the patterns were resolved
    # relative to the working directory rather than data/eval, matched
    # nothing, and the default `manswer-*.json` ran instead -- with 24 plausible
    # rows and no indication the requested files had not been read. Patterns
    # are now resolved against data/eval as well as the working directory,
    # and an unmatched one stops the run.
    patterns = [a for a in sys.argv[1:] if not a.startswith("-")]
    if patterns:
        paths = []
        for pattern in patterns:
            matched = sorted(Path().glob(pattern)) or sorted((DATA / "eval").glob(pattern))
            if not matched:
                raise SystemExit(f"pattern matched no files: {pattern!r}")
            paths += matched
    else:
        paths = sorted((DATA / "eval").glob("manswer-*.json"))
    if not paths:
        raise SystemExit("no answer files found")
    rows = []
    for path in paths:
        try:
            a = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  {path.name}: unparseable ({exc})")
            continue
        citation_tokens, quote_checks = citation_entries(a.get("citations"))
        text = json.dumps(a.get("answer", ""), ensure_ascii=False) + " " + \
            " ".join(citation_tokens)
        result = check(text, known_ids, threads, episodes, sections, quote_checks, retriever)
        rows.append((a.get("case_id", path.stem), result))

    print(f"{'case':26} {'cited':>6} {'bad':>4}  detail")
    print("-" * 74)
    for case_id, r in rows:
        flag = "" if r["unresolvable"] == 0 else "  <-- FABRICATED"
        print(f"{case_id:26} {r['cited']:6} {r['unresolvable']:4}  "
              f"{r['detail'] if r['detail'] else ''}{flag}")
    clean = sum(1 for _, r in rows if r["grounded"])
    nocite = sum(1 for _, r in rows if r["cited"] == 0)
    print(f"\nfully grounded: {clean}/{len(rows)}")
    print(f"no citation at all: {nocite}/{len(rows)}")


if __name__ == "__main__":
    main()
