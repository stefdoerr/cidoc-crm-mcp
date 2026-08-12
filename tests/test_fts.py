import pytest

from lib.fts import build_fts, fts_escape, search_fts


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "fts.sqlite3"
    build_fts(path, [
        {"chunk_id": "c1", "message_id": "m1", "thread_id": "t0",
         "subject": "scope note of E55", "from_name": "Martin Doerr",
         "body": "The scope note of E55 Type should be revised.", "entities": "E55"},
        {"chunk_id": "c2", "message_id": "m2", "thread_id": "t0",
         "subject": "time spans", "from_name": "Christian-Emil Ore",
         "body": "E52 Time-Span is unrelated to typing.", "entities": "E52"},
        {"chunk_id": "c3", "message_id": "m3", "thread_id": "t1",
         "subject": "vocabularies", "from_name": "Richard Light",
         "body": "Controlled vocabularies and thesauri in museums.", "entities": ""},
        # Additional rows for ranking tests with multiple hits
        {"chunk_id": "c4", "message_id": "m4", "thread_id": "t1",
         "subject": "thesaurus", "from_name": "Alice",
         "body": "A thesaurus is useful.", "entities": ""},
        {"chunk_id": "c5", "message_id": "m5", "thread_id": "t2",
         "subject": "taxonomy", "from_name": "Bob",
         "body": "Thesaurus and taxonomy together.", "entities": ""},
        {"chunk_id": "c6", "message_id": "m6", "thread_id": "t2",
         "subject": "ontology", "from_name": "Charlie",
         "body": "The thesaurus follows ontology principles.", "entities": ""},
    ])
    return path


def test_fts_escape_wraps_and_doubles_quotes():
    assert fts_escape("E55") == '"E55"'
    assert fts_escape('say "hi"') == '"say ""hi"""'
    # Characters that are FTS5 operators must not leak through unquoted
    assert fts_escape("man-made") == '"man-made"'
    assert fts_escape("a*b") == '"a*b"'


def test_identifier_matches_exactly_and_does_not_bleed_to_neighbours(db):
    hits = search_fts(db, ["E55"], limit=10)
    ids = [cid for cid, _ in hits]
    assert "c1" in ids
    assert "c2" not in ids, "E55 must not match E52 — the whole reason BM25 is here"


def test_multiple_terms_are_ord_together(db):
    ids = [cid for cid, _ in search_fts(db, ["E55", "vocabularies"], limit=10)]
    assert "c1" in ids and "c3" in ids


def test_results_are_ranked_best_first(db):
    # bm25() is negative in SQLite; ascending rank is best-first.
    # Query for a term that appears in multiple rows with different frequencies.
    hits = search_fts(db, ["thesaurus"], limit=10)
    # Require at least 3 hits to verify ordering is meaningful (not trivially sorted)
    assert len(hits) >= 3, f"Need at least 3 hits to verify ranking, got {len(hits)}"
    # Verify results are in ascending order (more negative = better)
    assert hits == sorted(hits, key=lambda h: h[1]), "Results must be sorted ascending by rank"


def test_limit_is_respected(db):
    assert len(search_fts(db, ["E55", "E52", "vocabularies"], limit=2)) == 2


def test_query_with_fts_operators_does_not_raise(db):
    # Unescaped, these are FTS5 syntax and would raise OperationalError
    for hostile in ["man-made", 'quote"inside', "AND", "*", "NEAR(", "a OR b"]:
        search_fts(db, [hostile], limit=5)


def test_empty_terms_returns_empty(db):
    assert search_fts(db, [], limit=10) == []


def test_rebuild_replaces_rather_than_appends(tmp_path):
    path = tmp_path / "f.sqlite3"
    row = {"chunk_id": "x", "message_id": "m", "thread_id": "t",
           "subject": "s", "from_name": "n", "body": "hello world", "entities": ""}
    build_fts(path, [row])
    assert build_fts(path, [row]) == 1
    assert len(search_fts(path, ["hello"], limit=10)) == 1


def test_nul_byte_does_not_raise(db):
    # NUL bytes should be stripped, not cause unterminated string errors
    search_fts(db, ["foo\x00bar"], limit=5)
    search_fts(db, ["normal", "with\x00nul"], limit=5)


def test_entities_weight_outranks_body(tmp_path):
    # A message matching only in entities should rank higher than one
    # matching only in body, for the same term.
    path = tmp_path / "f.sqlite3"
    build_fts(path, [
        {"chunk_id": "e1", "message_id": "m1", "thread_id": "t",
         "subject": "", "from_name": "A",
         "body": "Some content here.", "entities": "rdf"},
        {"chunk_id": "e2", "message_id": "m2", "thread_id": "t",
         "subject": "", "from_name": "B",
         "body": "The RDF standard is widely used.", "entities": ""},
    ])
    hits = search_fts(path, ["rdf"], limit=10)
    # e1 matches in entities (weight 4.0), e2 matches in body (weight 1.0)
    # e1 should rank better (more negative = better)
    ids = [cid for cid, _ in hits]
    assert ids[0] == "e1", "Entities match should outrank body match"


def test_chunk_id_deduplication(tmp_path):
    # Duplicate chunk_ids should be deduplicated, keeping first.
    path = tmp_path / "d.sqlite3"
    rows = [
        {"chunk_id": "dup", "message_id": "m1", "thread_id": "t",
         "subject": "first", "from_name": "A", "body": "first content", "entities": ""},
        {"chunk_id": "dup", "message_id": "m2", "thread_id": "t",
         "subject": "second", "from_name": "B", "body": "second content", "entities": ""},
        {"chunk_id": "unique", "message_id": "m3", "thread_id": "t",
         "subject": "unique", "from_name": "C", "body": "unique content", "entities": ""},
    ]
    count = build_fts(path, rows)
    # Should be 2 rows (one dup, one unique), not 3
    assert count == 2, f"Expected 2 rows after dedup, got {count}"
    # Verify the first occurrence was kept by searching for its content
    hits = search_fts(path, ["first"], limit=10)
    assert len(hits) == 1, "First occurrence of duplicate should be present"
