# tests/test_smoke_retrieval.py
"""Retrieval regression gate. Requires a fully built stores/crm-sig/."""

import pytest
import yaml

from lib.config import PROJECT_ROOT, STORES_DIR
from lib.retrieve import Retriever

CASES = yaml.safe_load(
    (PROJECT_ROOT / "tests" / "smoke_queries.yaml").read_text(encoding="utf-8")
)

pytestmark = pytest.mark.skipif(
    not (STORES_DIR / "crm-sig" / "meta.json").exists(),
    reason="index not built; run `uv run python build.py index` first",
)


@pytest.fixture(scope="module")
def retriever():
    return Retriever("crm-sig")


def _subjects(hits):
    return " || ".join((h.get("subject") or "").lower() for h in hits)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["query"][:40])
def test_expected_thread_in_top_10(retriever, case):
    hits = retriever.search(case["query"], top_k=10)
    assert case["expect_subject"] in _subjects(hits), (
        f"{case['why']}\nquery: {case['query']}\n"
        f"wanted subject containing: {case['expect_subject']}\n"
        f"got: {_subjects(hits)}"
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["query"][:40])
def test_expansion_does_not_hurt(retriever, case):
    """Expansion may add hits; it must never remove a case that already passed
    without it. This is the guard against a bad stop-label list."""
    without = retriever.search(case["query"], top_k=10, expand=False)
    if case["expect_subject"] not in _subjects(without):
        pytest.skip("case does not pass unexpanded; nothing to regress")
    with_expansion = retriever.search(case["query"], top_k=10, expand=True)
    assert case["expect_subject"] in _subjects(with_expansion), (
        "expansion REMOVED a hit that plain search found -- the stop-label "
        f"guard is likely wrong.\nquery: {case['query']}"
    )


def test_bare_stop_word_query_is_not_flooded(retriever):
    """A bare 'type' must not behave as though the user typed E55."""
    hits = retriever.search("type", top_k=10)
    tagged = sum(1 for h in hits if "E55" in (h.get("entities") or []))
    assert tagged < 8, (
        f"{tagged}/10 hits carry E55 -- the stop-label guard is not holding"
    )


docs_built = pytest.mark.skipif(
    not (STORES_DIR / "crm-sig-docs" / "meta.json").exists(),
    reason="document index not built; run `uv run python build.py docs && build.py index`",
)


@docs_built
@pytest.mark.parametrize("ident", ["P2", "E55", "P125"])
def test_a_declaration_wins_on_its_own_identifier(retriever, ident):
    """BM25 length-normalisation ranked P125 and P3 above P2 for the query
    "P2 has type", because their shorter fields score the token higher than
    P2's own longer ones. Naming an id is a lookup, not a similarity match."""
    hits = retriever.search_documents(ident, top_k=3, kind="declaration")
    assert hits, f"no declaration hits for {ident}"
    assert hits[0].get("concept_id") == ident, (
        f"{ident} should be its own top declaration, got "
        f"{[h.get('concept_id') for h in hits]}"
    )


@docs_built
def test_narrative_search_still_ranks_by_relevance(retriever):
    """The promotion must not fire when no identifier is named, or every
    conceptual query would be hijacked by whatever id happens to appear."""
    hits = retriever.search_documents("minimality principle", top_k=5, kind="narrative")
    assert hits
    paths = " | ".join(" > ".join(h.get("section_path") or []) for h in hits)
    assert "Minimality" in paths, paths


@docs_built
def test_modelling_guidance_is_reachable_from_a_plain_question(retriever):
    """The reason the document corpus exists: guidance the XML cannot give."""
    hits = retriever.search_documents("when should I declare a new class", top_k=8)
    paths = " | ".join(" > ".join(h.get("section_path") or []) for h in hits)
    assert "Modelling principles" in paths, paths


@docs_built
def test_declarations_are_not_buried_by_short_discursive_sections(retriever):
    """Guards the fusion weighting, not the answering of modelling questions.

    The spec is deliberately abstract and will never contain "photograph" --
    enumerating concrete cases is exactly what its Minimality principle
    forbids. Mapping a real case onto E36 or P62 is the reading model's job,
    and this retrieval layer only has to put the substantive material in
    front of it.

    What it must not do is bury that material. Declarations run to 7,405
    chars and BM25 normalises hard by length, so on a query naming no
    identifier the short discursive sections outranked the declarations
    entirely: this one put Modelling principles > Minimality above both E36
    Visual Item and P62 depicts.

    E36 rather than E38 Image: E38 is deprecated, absent from 7.3.2 and in
    the ontology's historical bucket. An earlier version of this check called
    E38 correct and scored the right answer as a miss.
    """
    hits = retriever.search_documents(
        "how do I model a photograph of a building", top_k=3
    )
    ids = [h.get("concept_id") for h in hits]
    assert "E36" in ids or "P62" in ids, ids
    paths = [" > ".join(h.get("section_path") or []) for h in hits]
    assert "Modelling principles > Minimality" not in paths[:1], paths


episodes_built = pytest.mark.skipif(
    not (STORES_DIR / "crm-sig-episodes" / "meta.json").exists(),
    reason="episode index not built; run `uv run python build.py index`",
)


@episodes_built
def test_the_weighted_episode_column_holds_titles_not_an_enum(retriever):
    """build_episode_index put `outcome` in the FTS `subject` column, which
    carries weight 2.0 -- so the index scored a three-valued enum as though it
    were a title, and a query containing "decided" matched on it by accident.
    The column now holds `topic`.

    Asserted on the built index rather than through search, because it is a
    property of the data: three distinct values means the bug is back.
    """
    import sqlite3

    conn = sqlite3.connect(STORES_DIR / "crm-sig-episodes" / "fts.sqlite3")
    try:
        distinct = conn.execute(
            "SELECT count(DISTINCT subject) FROM messages_fts"
        ).fetchone()[0]
    finally:
        conn.close()
    assert distinct > 100, (
        f"only {distinct} distinct values in the weighted subject column -- "
        "that is an enum, not a set of titles"
    )


@episodes_built
def test_an_outcome_word_does_not_score_as_a_title(retriever):
    """build_episode_index put `outcome` in the FTS subject column, which
    carries weight 2.0, so querying "decided" scored against an enum value
    rather than any real subject matter. The column now holds `topic`."""
    hits = retriever.search_episodes("decided", top_k=10)
    if not hits:
        pytest.skip("no hits to judge")
    decided = sum(1 for h in hits if h.get("outcome") == "decided")
    assert decided < len(hits), (
        "every hit for the bare word 'decided' has outcome=decided, which "
        "means the enum is still being scored as a title"
    )


@docs_built
def test_the_spec_is_not_outranked_by_the_decision_record(retriever):
    """3,002 issue chunks share a store with 374 spec chunks. Searched
    together they took every top-5 slot for both of the queries below, which
    is the same blurring that made documents a separate corpus from the
    mailing list. `docs` therefore defaults to the reference model; the issue
    pages are reached through `issues`."""
    from lib.retrieve import SPEC_KINDS

    for query in ("how do I model a photograph of a building",
                  "when should I declare a new class"):
        hits = retriever.search_documents(query, top_k=5, kind=SPEC_KINDS)
        assert hits, query
        kinds = {h["kind"] for h in hits}
        assert kinds <= SPEC_KINDS, f"{query}: leaked {kinds - SPEC_KINDS}"


@docs_built
def test_the_issue_record_is_still_reachable(retriever):
    """Defaulting `docs` to the spec must not strand 3,002 chunks."""
    hits = retriever.search_documents("what did the SIG decide", top_k=5, kind="issue")
    assert hits
    assert all(h["kind"] == "issue" for h in hits)


@docs_built
def test_an_unknown_document_kind_is_rejected(retriever):
    import pytest as _pytest

    with _pytest.raises(ValueError, match="Unknown document kind"):
        retriever.search_documents("x", kind="nonsense")


def test_no_thread_takes_more_than_its_share(retriever):
    """A result page is a budget. Before the per-thread cap, "teacher student
    relationship" returned ten hits spanning six threads -- four slots spent on
    repeats of threads already listed, which is what pushed the answer off the
    page. Fails if MAX_HITS_PER_THREAD stops being applied."""
    from lib.retrieve import MAX_HITS_PER_THREAD
    from collections import Counter
    for query in ("teacher student relationship", "non-human actors", "E22 scope note"):
        hits = retriever.search(query, top_k=10)
        counts = Counter(h["thread_id"] for h in hits)
        worst = counts.most_common(1)[0]
        assert worst[1] <= MAX_HITS_PER_THREAD, (
            f"{query!r}: thread {worst[0]} took {worst[1]} of {len(hits)} slots")


def test_a_message_never_appears_twice(retriever):
    """Results are chunk-level; two chunks of one long message are one hit."""
    for query in ("teacher student relationship", "shortcuts and full paths"):
        hits = retriever.search(query, top_k=10)
        ids = [h["message_id"] for h in hits]
        assert len(ids) == len(set(ids)), f"{query!r} repeated a message"
