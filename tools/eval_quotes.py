#!/usr/bin/env python3
"""Check the quotations an answer puts in quote marks against the real sources.

`eval_citations.py` verifies the citations an answer DECLARES: identifiers in
the `citations` list exist, and a `quote` carried alongside one occurs in the
source named with it. That leaves the larger surface untouched. Answers quote
in running prose -- "E11's scope note says '...'", "Martin Doerr states '...'"
-- and those quotations name no source id at all, so nothing checked them.

That gap is where the modelling evaluation's worst failure lived: a phrase
attributed to a thread that never uses that wording, which a reviewer with
full archive access read and confirmed anyway. A human reviewer cannot hold
100MB of source text in mind; literal containment is decidable, so decide it
mechanically and hand the reviewer only the residue.

    uv run python tools/eval_quotes.py 'manswer2-*.json'

Output is deliberately not pass/fail. A quotation that is not literally
present is not automatically fabricated -- it may be elided, truncated, or
faithfully compressed. So for every span that does not match, this prints the
longest prefix that DOES occur plus the surrounding real text, which is
normally enough to classify it at a glance:

    faithful    the source says the same thing in the same words, modulo an
                elision, a trailing comma, or a dropped parenthetical
    compressed  real passage, reworded inside quote marks -- a defect, but of
                honesty about quoting, not of grounding
    absent      no meaningful prefix occurs anywhere -- either a fabrication,
                or the answer is quoting the CASE it was given rather than a
                source, which is legitimate and common

Two traps are worth naming, because both produced confidently wrong output
when this check was first written by hand:

 1. **The delimiter.** These answers quote with ' rather than ". A naive
    `'([^']+)'` matches from the apostrophe of "CRM's" to the one in "doesn't"
    and reports the resulting garbage as an unverifiable quotation -- 192
    "misses" out of 234, essentially all spurious. A quotation opens after
    whitespace or a bracket and closes before whitespace or punctuation; a
    possessive or contraction apostrophe always sits between two letters, and
    that single rule separates them.
 2. **The corpus.** The first run checked the archive and the specification
    only, and duly reported the E96 Purchase scope note and the E10 auction
    examples as unverifiable -- they live in crm_family.json and the cached
    issue pages. An incomplete corpus does not under-report, it manufactures
    fabrications. Everything `search.py` can put in front of an answerer has
    to be in here, which is what `load_corpus` is for.
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data"

# A quotation opens at the start of the text or after whitespace/an opening
# bracket, and closes at the end or before whitespace/closing punctuation.
# See trap 1 in the module docstring: this is the whole defence against
# possessives and contractions being read as quote delimiters.
QUOTED = re.compile(
    r"""(?:(?<=^)|(?<=[\s(\[]))          # opens at start or after space/bracket
        (?: ' ([^']{25,400}) '           # '...'
          | " ([^"]{25,400}) "           # "..."
          | “ ([^”]{25,400}) ” )
        (?=$|[\s.,;:)\]?!])              # closes before space or punctuation
    """,
    re.VERBOSE,
)

# "A ... B" and "A [editorial] B" are ordinary quoting conventions, not
# evidence of invention. Each side is checked on its own.
ELISION = re.compile(r"\s*(?:\.\.\.|\[[^\]]*\])\s*")

# Fragments this short carry no evidential weight -- "in the role of" occurs
# everywhere -- so they neither prove nor disprove a quotation.
MIN_WORDS = 5
MIN_FRAGMENT_WORDS = 4

_SUBSTITUTIONS = [
    ("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
    ("—", "-"), ("–", "-"), ("…", "..."), (" ", " "),
]


def norm(s: str) -> str:
    """Fold the differences that are never what a quotation is wrong about.

    Smart quotes, dashes and non-breaking spaces differ between the mbox, the
    docx and the scraped HTML for the same sentence, so comparing them
    literally would report the transport encoding as a misquote.
    """
    s = unicodedata.normalize("NFKD", s)
    for a, b in _SUBSTITUTIONS:
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s)
    # A space before punctuation is a typo in the source, not a difference in
    # wording, and 21% of messages and 38% of document chunks have one. Anyone
    # quoting such a sentence writes it correctly, so leaving the space in
    # place reports accurate quotations as unverifiable. Matches the same rule
    # in lib.retrieve._normalize_ws_quotes -- the two checks must not disagree
    # about what counts as the same text.
    return re.sub(r"\s+([.,;:?!])", r"\1", s).lower()


def _strings(obj, out: list[str]) -> None:
    """Every string anywhere in a JSON structure.

    Walking blindly is deliberate: these files have several nested shapes
    (scope notes, examples, FOL, issue outcomes, reference lists) and a quote
    may come from any of them. Enumerating the fields that matter is exactly
    the whitelist mistake that trap 2 describes.
    """
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _strings(v, out)


def load_corpus(verbose: bool = False) -> str:
    """Every source `search.py` can put in front of an answerer, normalised.

    Ordered from most to least likely to be quoted, though the result is one
    concatenated blob and order only affects the reported context. `body_raw`
    joins `body` because a quotation may fall inside quoted-reply text that
    `body` strips.
    """
    parts: list[str] = []
    counts: dict[str, int] = {}

    def add(label: str, chunks: list[str]) -> None:
        text = "\n".join(c for c in chunks if c)
        counts[label] = len(text)
        parts.append(text)

    messages: list[str] = []
    for line in open(DATA / "clean.jsonl", encoding="utf-8"):
        r = json.loads(line)
        messages += [r.get("body") or "", r.get("body_raw") or ""]
    add("archive", messages)

    docs = [json.loads(line).get("text") or ""
            for line in open(DATA / "documents.jsonl", encoding="utf-8")]
    add("documents", docs)

    for label, path in (("ontology", DATA / "ontology.json"),
                        ("issues", DATA / "issues.json"),
                        ("crm_family", PROJECT_ROOT / "sources" / "crm_family.json"),
                        ("crm_issues", PROJECT_ROOT / "sources" / "crm_issues.json")):
        if path.exists():
            buf: list[str] = []
            _strings(json.loads(path.read_text(encoding="utf-8")), buf)
            add(label, buf)

    # The cached SIG pages are included as raw HTML rather than via the
    # parser: a quotation may come from prose our field-based parse does not
    # keep, and for a containment check the tags are harmless noise.
    pages_dir = DATA / "issue_pages"
    if pages_dir.is_dir():
        raw = [p.read_text(encoding="utf-8", errors="ignore")
               for p in sorted(pages_dir.iterdir()) if p.is_file()]
        add("issue_pages", raw)

    if verbose:
        for label, size in counts.items():
            print(f"  {label:14} {size:>12,} chars", file=sys.stderr)
    return norm("\n".join(parts))


def extract_quotations(answer: dict) -> list[str]:
    """The quoted spans in an answer's prose fields.

    Identifier lists and citation ids are skipped -- `eval_citations.py`
    already checks those, and they contain no prose to quote.
    """
    prose = [str(answer.get("answer", ""))]
    for alt in answer.get("rejected_alternatives") or []:
        if isinstance(alt, dict):
            prose.append(str(alt.get("why_not", "")))
        else:
            prose.append(str(alt))
    for key in ("caveats", "confidence_note", "notes", "uncertainty"):
        if answer.get(key):
            prose.append(str(answer[key]))

    spans: list[str] = []
    for match in QUOTED.finditer(" ".join(prose)):
        span = next(g for g in match.groups() if g is not None).strip()
        if len(span.split()) >= MIN_WORDS:
            spans.append(span)
    return spans


def longest_prefix(needle: str, corpus: str) -> int:
    """Length of the longest prefix of `needle` occurring in `corpus`.

    Binary search rather than a scan: the corpus is ~100M characters and this
    runs for every unmatched span.
    """
    lo, hi = 0, len(needle)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if needle[:mid] in corpus:
            lo = mid
        else:
            hi = mid - 1
    return lo


def verify(span: str, corpus: str) -> dict:
    """Classify one quoted span against the corpus.

    `matched` is literal containment, whole or fragment-wise. Anything else
    reports where it diverges rather than a bare failure, because the answer
    to "is this fabricated?" is usually visible in the real text next to it
    and is not the same question as "is this literal?".
    """
    text = norm(span)
    if text in corpus:
        return {"status": "matched", "how": "literal"}

    fragments = [f for f in ELISION.split(text)
                 if len(f.split()) >= MIN_FRAGMENT_WORDS]
    if len(fragments) > 1 and all(f in corpus for f in fragments):
        return {"status": "matched", "how": "elided"}

    target = next((f for f in fragments if f not in corpus), text)
    n = longest_prefix(target, corpus)
    if n < 25:
        return {"status": "absent", "prefix_chars": n}
    at = corpus.find(target[:n])
    return {
        "status": "partial",
        "prefix_chars": n,
        "of_chars": len(target),
        "source": corpus[max(0, at - 70): at + n + 160],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("patterns", nargs="*", default=["manswer-*.json"],
                    help="globs under data/eval (default: manswer-*.json)")
    ap.add_argument("--quiet", action="store_true",
                    help="counts only; omit the divergence report")
    args = ap.parse_args()

    paths = sorted({p for pat in args.patterns for p in (DATA / "eval").glob(pat)})
    if not paths:
        raise SystemExit("no answer files found")

    print("loading corpus...", file=sys.stderr)
    corpus = load_corpus(verbose=not args.quiet)

    rows, residue = [], []
    for path in paths:
        try:
            answer = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  {path.name}: unparseable ({exc})")
            continue
        case_id = answer.get("case_id", path.stem)
        results = [(s, verify(s, corpus)) for s in extract_quotations(answer)]
        matched = sum(1 for _, r in results if r["status"] == "matched")
        rows.append((case_id, len(results), matched))
        residue += [(case_id, s, r) for s, r in results if r["status"] != "matched"]

    print(f"\n{'case':26} {'quoted':>7} {'verbatim':>9} {'residue':>8}")
    print("-" * 54)
    for case_id, total, matched in rows:
        print(f"{case_id:26} {total:7} {matched:9} {total - matched:8}")
    total_q = sum(t for _, t, _ in rows)
    total_m = sum(m for _, _, m in rows)
    print(f"\nverbatim in a real source: {total_m}/{total_q}")
    print(f"needs a human read: {total_q - total_m}")

    if residue and not args.quiet:
        print("\n" + "=" * 74)
        print("SPANS THAT ARE NOT VERBATIM -- classify each")
        print("=" * 74)
        for case_id, span, r in residue:
            print(f"\n--- {case_id}")
            print(f"  quoted : {span}")
            if r["status"] == "absent":
                print(f"  source : NOTHING MATCHES "
                      f"(longest prefix {r['prefix_chars']} chars) "
                      f"-- fabricated, or quoting the case rather than a source")
            else:
                print(f"  matches: first {r['prefix_chars']} of "
                      f"{r['of_chars']} chars")
                print(f"  source : ...{r['source']}...")


if __name__ == "__main__":
    main()
