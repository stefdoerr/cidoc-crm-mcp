"""Tests for the pure functions behind Task 18's document index:
lib.index.document_chunks (indexing-time reshaping) and search.format_documents
(the docs verb's rendering). Neither constructs a Retriever nor loads the
embedding model -- both take plain dicts/lists in and strings/dicts out.
"""

from lib.index import document_chunks
from search import format_documents

DECL = {
    "chunk_id": "crm732#E55", "doc_id": "crm732",
    "doc_title": "Definition of the CIDOC Conceptual Reference Model, version 7.3.2",
    "cite": "CIDOC CRM v7.3.2", "kind": "declaration", "concept_id": "E55",
    "section_path": ["CIDOC CRM Class Declarations"], "heading": "E55 Type",
    "text": "E55 Type comprises concepts denoted by terms from thesauri.",
    "entities": ["E28"], "entities_historical": [],
}

NARR = {
    "chunk_id": "crm732#s0012", "doc_id": "crm732",
    "doc_title": "Definition of the CIDOC Conceptual Reference Model, version 7.3.2",
    "cite": "CIDOC CRM v7.3.2", "kind": "narrative", "concept_id": None,
    "section_path": ["Modelling principles", "Minimality"], "heading": "Minimality",
    "text": "...the CRM is designed to be as small as possible while still "
            "covering the semantics of the source data completely...",
    "entities": ["E55", "E1", "P2"], "entities_historical": [],
}


# ---- document_chunks -------------------------------------------------------


def test_document_chunks_carries_the_indexing_fields():
    chunk = document_chunks([DECL])[0]
    assert chunk["chunk_id"] == "crm732#E55"
    assert chunk["doc_id"] == "crm732"
    assert chunk["cite"] == "CIDOC CRM v7.3.2"
    assert chunk["kind"] == "declaration"
    assert chunk["heading"] == "E55 Type"
    assert chunk["text"] == DECL["text"]


def test_document_chunks_joins_section_path_with_arrows():
    chunk = document_chunks([NARR])[0]
    assert chunk["section_path"] == "Modelling principles > Minimality"


def test_document_chunks_narrative_concept_id_is_empty_string_not_none():
    # Chroma metadata rejects None outright -- this is the guard against it.
    chunk = document_chunks([NARR])[0]
    assert chunk["concept_id"] == ""


def test_document_chunks_declaration_keeps_its_concept_id():
    chunk = document_chunks([DECL])[0]
    assert chunk["concept_id"] == "E55"


def test_document_chunks_merges_entities_and_historical_into_one_string():
    rec = dict(NARR, entities=["E55"], entities_historical=["E52"])
    chunk = document_chunks([rec])[0]
    assert chunk["entities"] == "E55 E52"


def test_document_chunks_skips_blank_text():
    rec = dict(NARR, text="   ")
    assert document_chunks([rec]) == []


def test_document_chunks_preserves_record_count_when_all_nonblank():
    assert len(document_chunks([DECL, NARR])) == 2


def test_document_chunks_missing_section_path_does_not_crash():
    rec = dict(DECL, section_path=[])
    chunk = document_chunks([rec])[0]
    assert chunk["section_path"] == ""


# ---- format_documents -------------------------------------------------------


def test_format_documents_empty():
    assert "No results" in format_documents([])


def test_format_documents_narrative_shows_bracketed_section_path_and_cite():
    out = format_documents([NARR])
    assert "[Modelling principles > Minimality]" in out
    assert "CIDOC CRM v7.3.2" in out


def test_format_documents_declaration_leads_with_heading_not_brackets():
    out = format_documents([DECL])
    label_line = out.splitlines()[0]
    assert "E55 Type" in label_line
    assert "[" not in label_line


def test_format_documents_shows_concepts_for_pivoting():
    out = format_documents([NARR])
    assert "concepts:" in out
    assert "E55" in out and "E1" in out and "P2" in out


def test_format_documents_declaration_concepts_come_from_its_own_entities():
    out = format_documents([DECL])
    assert "E28" in out


def test_format_documents_snippet_is_substantial_not_email_sized():
    # ~300 chars, not the message formatter's ~160 -- these are definitions
    # and modelling rules, and 160 chars is not enough to judge relevance.
    long_text = "word " * 200  # 1000 chars
    rec = dict(NARR, text=long_text)
    out = format_documents([rec])
    quoted = next(line for line in out.splitlines() if line.strip().startswith('"'))
    assert len(quoted.strip()) > 200


def test_format_documents_dedupes_concepts_preserving_order():
    rec = dict(NARR, entities=["E55", "E1"], entities_historical=["E55"])
    out = format_documents([rec])
    concepts_line = next(line for line in out.splitlines() if "concepts:" in line)
    assert concepts_line.count("E55") == 1


def test_format_documents_numbers_multiple_hits():
    out = format_documents([NARR, DECL])
    assert " 1. " in out
    assert " 2. " in out


def test_format_documents_handles_missing_entities_gracefully():
    rec = dict(NARR, entities=[], entities_historical=[])
    out = format_documents([rec])
    assert "concepts:" not in out
