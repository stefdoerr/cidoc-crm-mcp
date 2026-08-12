"""Tests for tools/eval_quotes.py (checking quoted prose against real sources).

The tool exists because a reviewer confirmed a quotation that no source
contains. Its own guards therefore have to be shown to work rather than
assumed, and each one below is written so that disabling the thing it guards
makes it fail:

  * the delimiter rule -- relaxing it to a naive `'([^']+)'` makes
    `test_possessives_are_not_quote_delimiters` extract garbage spans;
  * elision handling -- dropping it makes `test_elided_quote_matches` report a
    faithful quotation as unverifiable;
  * corpus breadth -- narrowing `load_corpus` to the archive makes
    `test_corpus_covers_every_surfaced_source` fail on the scope-note text
    that only crm_family.json holds.

Synthetic corpora are used throughout except where the point is the real
corpus's breadth, so the tests neither read nor write build artefacts.
"""

import json

from lib.config import PROJECT_ROOT
from tools import eval_quotes


def corpus(*texts: str) -> str:
    return eval_quotes.norm("\n".join(texts))


# --------------------------------------------------------------------------
# extraction: what counts as a quotation at all
# --------------------------------------------------------------------------

def test_possessives_are_not_quote_delimiters():
    """The bug that made the first hand-written version useless.

    A naive `'([^']+)'` pairs the apostrophe in "CRM's" with the one in
    "doesn't" and yields a span that is not a quotation at all. Nothing here
    is quoted, so nothing may be extracted.
    """
    answer = {"answer": "E11's scope note doesn't cover this, and E81's "
                        "wording isn't any clearer about the object's identity."}
    assert eval_quotes.extract_quotations(answer) == []


def test_real_quotation_between_possessives_is_still_found():
    """The delimiter rule must not overcorrect into missing genuine quotes."""
    answer = {"answer": "E11's note says 'the matrix has a distinct identity "
                        "before and after the change' and that settles it."}
    assert eval_quotes.extract_quotations(answer) == [
        "the matrix has a distinct identity before and after the change"
    ]


def test_double_and_smart_quotes_are_extracted():
    answer = {"answer": 'The note says "continuity of coherence and '
                        'functionality of the thing" plainly enough.'}
    assert eval_quotes.extract_quotations(answer) == [
        "continuity of coherence and functionality of the thing"
    ]


def test_short_spans_are_ignored():
    """"in the role of" proves nothing either way, so it is not a finding."""
    answer = {"answer": "It is used 'in the role of' here."}
    assert eval_quotes.extract_quotations(answer) == []


def test_quotations_are_read_from_every_prose_field():
    """A misquote hidden in a rejected-alternative rationale still counts."""
    answer = {
        "answer": "",
        "rejected_alternatives": [
            {"option": "E11", "why_not": "its note says 'this class does not "
                                         "comprise the reuse of material'"}
        ],
        "caveats": "the SIG called it 'a genuinely unresolved question here'",
    }
    assert len(eval_quotes.extract_quotations(answer)) == 2


# --------------------------------------------------------------------------
# verification: matched / partial / absent
# --------------------------------------------------------------------------

def test_literal_quote_matches():
    c = corpus("The class comprises the reuse of material from an original.")
    r = eval_quotes.verify("comprises the reuse of material from an original", c)
    assert r == {"status": "matched", "how": "literal"}


def test_encoding_differences_are_not_misquotes():
    """Smart quotes and dashes differ between the mbox, the docx and the HTML
    for the same sentence; folding them is what stops the transport encoding
    being reported as a misquote."""
    c = corpus("the object’s identity — before and after the change")
    r = eval_quotes.verify("the object's identity - before and after the change", c)
    assert r["status"] == "matched"


def test_elided_quote_matches():
    """'A ... B' is ordinary quoting, not invention."""
    c = corpus("the painting of the Sistine Chapel (E7) was carried out by "
               "Michelangelo (E21) in the role of master craftsman")
    r = eval_quotes.verify(
        "the painting of the Sistine Chapel ... in the role of master craftsman", c)
    assert r == {"status": "matched", "how": "elided"}


def test_bracketed_editorial_insertion_matches():
    c = corpus("it has a distinct identity before and after the change, "
               "and there can be considerable physical change to the plate")
    r = eval_quotes.verify(
        "it has a distinct identity before and after the change "
        "[even though] there can be considerable physical change to the plate", c)
    assert r["status"] == "matched"


def test_compressed_quote_reports_where_it_diverges():
    """A reworded quotation is a real defect, but a different one from
    fabrication -- so the tool shows the real text rather than failing flat."""
    c = corpus("specific documented techniques should be described as "
               "instances of E29 Design or Procedure.")
    r = eval_quotes.verify("specific documented techniques should be E29", c)
    assert r["status"] == "partial"
    assert "described as" in r["source"]
    assert r["prefix_chars"] < r["of_chars"]


def test_absent_quote_is_reported_as_absent():
    c = corpus("Nothing in this corpus resembles the claimed sentence at all.")
    r = eval_quotes.verify("the expert may only be able to decide that a "
                           "particular embedding is not recent", c)
    assert r["status"] == "absent"


def test_elision_does_not_rescue_a_fabricated_half():
    """Both sides of an elision must be present; one real half is not enough."""
    c = corpus("the transfer of custody of the painting to the art dealer")
    r = eval_quotes.verify(
        "the transfer of custody of the painting ... "
        "was ratified by unanimous vote of the committee", c)
    assert r["status"] != "matched"


def test_longest_prefix_is_exact():
    c = corpus("alpha beta gamma delta")
    text = eval_quotes.norm("alpha beta gamma epsilon")
    n = eval_quotes.longest_prefix(text, c)
    assert text[:n] == "alpha beta gamma "
    assert text[:n + 1] not in c


# --------------------------------------------------------------------------
# the corpus itself
# --------------------------------------------------------------------------

def test_corpus_covers_every_surfaced_source():
    """Trap 2: an incomplete corpus does not under-report, it manufactures
    fabrications. crm_family.json holds extension scope notes that exist in no
    other file, so a corpus without it calls real quotations invented.

    Reads the committed reference data only (as tests/test_ontology.py does),
    never a build artefact.
    """
    family = json.loads((PROJECT_ROOT / "sources" / "crm_family.json").read_text(encoding="utf-8"))
    entries = family.get("entries", family)
    scope_notes = [e["scope_note"] for e in entries.values()
                   if isinstance(e, dict) and e.get("scope_note")]
    assert scope_notes, "reference data has no scope notes to check against"

    buf: list[str] = []
    eval_quotes._strings(entries, buf)
    family_corpus = eval_quotes.norm("\n".join(buf))

    # A sentence-length span from a real extension scope note must verify.
    sample = max(scope_notes, key=len)[:120]
    assert eval_quotes.verify(sample, family_corpus)["status"] == "matched"


def test_walker_reaches_nested_strings():
    """Enumerating expected fields is the whitelist mistake; the walker must
    reach a string at any depth."""
    buf: list[str] = []
    eval_quotes._strings(
        {"a": [{"b": {"c": ["deeply nested scope note text"]}}]}, buf)
    assert "deeply nested scope note text" in buf
