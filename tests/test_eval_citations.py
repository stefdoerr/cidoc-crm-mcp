"""tools/eval_citations.py's containment check: a citation can now carry an
optional quoted span, verified against the real source via
Retriever.find_quote, on top of the existing existence check.

Existence answers "is t1022 a real thread"; containment answers "does t1022
actually say this" -- the question existence-only checking could not ask, and
the reason a reviewer with full archive access still confirmed one of the two
known-bad quotes the modelling-advice evaluation produced.
"""

from tools.eval_citations import check, citation_entries
from lib.retrieve import Retriever


def _fake_retriever():
    r = Retriever()
    r.__dict__["threads"] = {"t9001": {"message_ids": ["h1"], "root": "h1", "subjects": []}}
    r.__dict__["by_hash"] = {
        "h1": {"message_id": "<m1@x>", "from_name": "Alice", "date": "2020-01-01",
               "body": "The committee decided to keep P107.1 as a shortcut."},
    }
    r.__dict__["messages"] = {}
    r.__dict__["episodes"] = []
    r.__dict__["documents"] = {}
    return r


KNOWN = (
    {"E55", "P107.1"},                 # known_ids
    {"t9001"},                         # threads
    set(),                             # episodes
    set(),                             # sections
)


# ---- citation_entries: splitting strings from {"id", "quote"} dicts -------


def test_citation_entries_passes_plain_strings_through_unchanged():
    tokens, quote_checks = citation_entries(["E55", "t9001"])
    assert tokens == ["E55", "t9001"]
    assert quote_checks == []


def test_citation_entries_extracts_quote_pairs_from_dict_citations():
    tokens, quote_checks = citation_entries([
        "E55",
        {"id": "t9001", "quote": "keep P107.1 as a shortcut"},
    ])
    assert tokens == ["E55", "t9001"]  # the id still existence-checks normally
    assert quote_checks == [("t9001", "keep P107.1 as a shortcut")]


def test_citation_entries_dict_without_quote_has_no_quote_check():
    tokens, quote_checks = citation_entries([{"id": "t9001"}])
    assert tokens == ["t9001"]
    assert quote_checks == []


def test_citation_entries_empty_or_none_is_empty():
    assert citation_entries(None) == ([], [])
    assert citation_entries([]) == ([], [])


# ---- check(): containment on top of existence ------------------------------


def test_check_passes_a_quote_that_is_actually_there():
    known_ids, threads, episodes, sections = KNOWN
    result = check("t9001", known_ids, threads, episodes, sections,
                    quote_checks=[("t9001", "keep P107.1 as a shortcut")],
                    retriever=_fake_retriever())
    assert result["grounded"] is True
    assert "quotes" not in result["detail"]


def test_check_flags_a_quote_that_is_not_there():
    known_ids, threads, episodes, sections = KNOWN
    result = check("t9001", known_ids, threads, episodes, sections,
                    quote_checks=[("t9001", "no property for transferring a right")],
                    retriever=_fake_retriever())
    assert result["grounded"] is False
    assert result["detail"]["quotes"]
    assert result["unresolvable"] >= 1


def test_check_existence_only_path_is_unchanged_with_no_quote_checks():
    """The exact call shape every existing answer file relies on -- no
    quote_checks, no retriever -- must behave exactly as before."""
    known_ids, threads, episodes, sections = KNOWN
    result = check("t9001 E55", known_ids, threads, episodes, sections)
    assert result["grounded"] is True
    assert result["cited"] == 2
    assert result["unresolvable"] == 0


def test_check_existence_only_path_still_catches_fabricated_ids():
    known_ids, threads, episodes, sections = KNOWN
    result = check("t9001 E999", known_ids, threads, episodes, sections)
    assert result["grounded"] is False
    assert "E999" in result["detail"]["crm_ids"]
