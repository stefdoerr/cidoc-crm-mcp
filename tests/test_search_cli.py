from search import format_hits, format_message, format_quote_result, format_thread

HIT = {
    "chunk_id": "abc123#0", "score": 0.031, "message_id": "<m1@x>",
    "thread_id": "t0042", "date": "2011-03-02T09:14:00",
    "from_name": "Martin Doerr", "subject": "scope note of E55",
    "snippet": "The scope note should be revised.", "entities": ["E55", "E28"],
}


def test_format_hits_includes_ids_needed_to_expand():
    out = format_hits([HIT])
    assert "<m1@x>" in out       # for `show`
    assert "t0042" in out        # for `thread`
    assert "Martin Doerr" in out
    assert "2011-03-02" in out
    assert "scope note of E55" in out


def test_format_hits_empty():
    assert "No results" in format_hits([])


def test_format_message_shows_headers_and_clean_body():
    rec = {
        "message_id": "<m1@x>", "date": "2011-03-02T09:14:00",
        "from_name": "Martin Doerr", "from_email": "martin@ics.forth.gr",
        "subject": "scope note", "body": "CLEAN BODY", "body_raw": "RAW BODY",
        "entities": ["E55"], "entities_historical": ["E84"], "attachments": [],
    }
    out = format_message(rec)
    assert "CLEAN BODY" in out
    assert "RAW BODY" not in out
    assert "E55" in out
    assert "E84" in out


def test_format_message_raw_flag_shows_original():
    rec = {
        "message_id": "<m@x>", "date": None, "from_name": "n", "from_email": "e",
        "subject": "s", "body": "CLEAN", "body_raw": "RAW", "entities": [],
        "entities_historical": [], "attachments": [],
    }
    assert "RAW" in format_message(rec, raw=True)


def test_format_message_lists_attachments():
    rec = {
        "message_id": "<m@x>", "date": None, "from_name": "n", "from_email": "e",
        "subject": "s", "body": "b", "body_raw": "b", "entities": [],
        "entities_historical": [],
        "attachments": [{"filename": "issue.doc",
                         "content_type": "application/msword", "size": 1024}],
    }
    assert "issue.doc" in format_message(rec)


def test_format_thread_is_chronological_and_numbered():
    records = [
        {"message_id": "<a>", "date": "2011-03-02T09:14:00", "from_name": "A",
         "subject": "s", "body": "first"},
        {"message_id": "<b>", "date": "2011-03-03T09:14:00", "from_name": "B",
         "subject": "s", "body": "second"},
    ]
    out = format_thread(records)
    assert out.index("first") < out.index("second")
    assert "[1]" in out and "[2]" in out


def test_format_thread_empty():
    assert "No such thread" in format_thread([])


# ---- format_quote_result: the `search.py quote` rendering -----------------
#
# These format hand-built Retriever.find_quote() output, so they exercise the
# CLI rendering in isolation from the matching logic (covered in
# tests/test_quote_verification.py).


def test_format_quote_result_found_in_thread_names_message_and_author():
    result = {
        "source_id": "t1022", "source_kind": "thread", "found": True,
        "match": "personal property is abolished",
        "context": "…political revolution, **personal property is abolished** B6…",
        "message_id": "<x@y>", "message_index": 2, "author": "Francesco Beretta",
        "date": "2017-08-22",
    }
    out = format_quote_result(result)
    assert "FOUND" in out
    assert "[2]" in out
    assert "Francesco Beretta" in out
    assert "personal property is abolished" in out


def test_format_quote_result_not_found_shows_closest():
    result = {
        "source_id": "t1022", "source_kind": "thread", "found": False,
        "closest": {
            "score": 0.28, "excerpt": "…personal **property** is abolished…",
            "message_id": "<x@y>", "message_index": 2, "author": "Francesco Beretta",
        },
    }
    out = format_quote_result(result)
    assert "NOT FOUND" in out
    assert "Francesco Beretta" in out
    assert "28%" in out


def test_format_quote_result_not_found_with_no_closest_match_at_all():
    result = {"source_id": "t1022", "source_kind": "thread", "found": False, "closest": None}
    out = format_quote_result(result)
    assert "NOT FOUND" in out
    assert "no similar text" in out.lower()


def test_format_quote_result_unknown_source():
    result = {
        "source_id": "t9999", "source_kind": None, "found": False,
        "error": "unknown source id 't9999': not a thread, episode, message or document chunk id in this archive",
    }
    out = format_quote_result(result)
    assert "UNKNOWN SOURCE" in out
    assert "t9999" in out


def test_format_quote_result_found_in_document_shows_section_path():
    result = {
        "source_id": "crm732#E55", "source_kind": "document", "found": True,
        "match": "denoted by terms from thesauri",
        "context": "…concepts **denoted by terms from thesauri** and controlled…",
        "heading": "E55 Type", "section_path": ["CIDOC CRM Class Declarations"],
        "cite": "CIDOC CRM v7.3.2",
    }
    out = format_quote_result(result)
    assert "FOUND" in out
    assert "CIDOC CRM Class Declarations" in out
    assert "CIDOC CRM v7.3.2" in out


def test_format_concept_renders_a_property_of_property():
    from search import format_concept

    entry = {
        "id": "P14.1", "of_property": "P14", "label": "in the role of",
        "range": "E55", "status": "current", "bucket": "property_of_property",
    }
    out = format_concept(entry, [], 0)
    assert "P14.1" in out
    assert "in the role of" in out
    assert "E55" in out
    assert "P14" in out                       # names its parent property
    assert "search.py concept P14" in out     # and points at it
    # The archive's entity index keys on the base property, so a mention
    # count here would always read 0 and mislead. Say so instead.
    assert "Mentions in the archive" not in out


def test_property_of_property_gets_no_applicable_property_table():
    """_is_class_like falls through to `"domain" not in entry`, which a
    property-of-property satisfies. Without an explicit guard the dossier
    prints an applicable-properties table for P14.1."""
    from search import _is_class_like

    assert not _is_class_like({"bucket": "property_of_property", "id": "P14.1"})


def test_format_connect_shows_a_declared_full_path():
    from search import format_connect

    # P43 is declared E70 Thing -> E54 Dimension (not E18, though its full
    # path text begins there).
    forward = [{"id": "P43", "name": "has dimension", "domain": "E70",
                "range": "E54", "required": False, "exact": False}]
    full_paths = {"P43": [
        "E18 Physical Thing. P39i was measured by (measured): E16 Measurement. "
        "P80 observed dimension (was observed in): E54 Dimension"
    ]}
    out = format_connect("E18", "E54", forward, [], full_paths=full_paths)
    assert "P43" in out
    assert "E16 Measurement" in out          # the mediating class is named
    assert "Full path" in out


def test_full_path_is_rendered_verbatim_including_the_spec_typo():
    """The published v7.3.2 P43 full path names "P80 observed dimension".
    P80 is "end is qualified by" (E52 -> E62); the property joining E16
    Measurement to E54 Dimension is P40. The error is the specification's
    and our parse of it is faithful. This corpus reports what the sources
    say, so the string is passed through unaltered -- pinned here so nobody
    silently "corrects" the source.
    """
    from search import format_connect

    forward = [{"id": "P43", "name": "has dimension", "domain": "E70",
                "range": "E54", "required": False, "exact": False}]
    declared = ("E18 Physical Thing. P39i was measured by (measured): "
                "E16 Measurement. P80 observed dimension (was observed in): "
                "E54 Dimension")
    out = format_connect("E18", "E54", forward, [], full_paths={"P43": [declared]})
    assert declared in out
    assert "P40" not in out


def test_format_connect_without_full_paths_is_unchanged():
    from search import format_connect

    forward = [{"id": "P14", "name": "carried out by", "domain": "E7",
                "range": "E39", "required": False, "exact": True}]
    plain = format_connect("E7", "E39", forward, [])
    assert "Full path" not in plain
    # and passing an empty mapping must behave identically
    assert format_connect("E7", "E39", forward, [], full_paths={}) == plain


def test_format_documents_prints_the_chunk_id_needed_to_quote():
    """A reader who can see a passage must be able to name it.

    `quote` takes `crm732#E12`; this block used to show only "E12 Production"
    and the cite string, so the id had to be guessed. Measured over 433 quote
    calls in one evaluation run, 64 passed an invented id (`E12`, `decl:E12`,
    `crm:E12`, `E12_Production`) and all 64 failed -- while minutes ids in the
    same run were almost all well-formed, because format_issue already prints
    them as a runnable command.
    """
    from search import format_documents

    out = format_documents([{
        "chunk_id": "crm732#E12", "kind": "declaration",
        "heading": "E12 Production", "cite": "CIDOC CRM v7.3.2",
        "text": "This class comprises activities that ...",
        "entities": ["E12"], "entities_historical": [],
    }])
    assert "crm732#E12" in out
    assert 'search.py quote crm732#E12 "..."' in out


def test_format_documents_chunk_id_line_survives_a_missing_id():
    """Never crash the whole listing over one malformed record."""
    from search import format_documents

    out = format_documents([{
        "kind": "narrative", "heading": "Modelling principles",
        "section_path": ["Modelling principles"], "cite": "CIDOC CRM v7.3.2",
        "text": "Minimality ...", "entities": [],
    }])
    assert "verify a quote" in out


def test_format_concept_warns_when_a_label_matched_several_concepts():
    """`concept "consists of"` returns P5 but P45 is usually what was meant.
    Silently showing one of three is the failure this note exists to stop."""
    from search import format_concept

    entry = {"id": "P5", "bucket": "properties", "full_name": "P5 consists of",
             "domain": "E3", "range": "E3", "scope_note": "x",
             "also_matches": ["P9", "P45"], "matched_label": "consists of"}
    out = format_concept(entry, [], 0)
    assert "P9 P45" in out
    assert "does not identify" in out


def test_format_validation_shows_every_reading_not_just_the_winner():
    from search import format_validation

    out = format_validation({
        "subject": "E22", "property": "consists of", "object": "E57",
        "legal": True, "resolved": "P45",
        "candidates": [
            {"id": "P5", "name": "consists of", "direction": "E3 -> E3",
             "legal": False, "reason": "E22 is not a E3"},
            {"id": "P45", "name": "consists of", "direction": "E18 -> E57",
             "legal": True, "reason": "ok", "required": True},
        ]})
    assert "P5" in out and "P45" in out and "Use P45." in out


def test_format_validation_reports_no_legal_reading_with_a_next_step():
    """The Clayton example nests took_place_at under an E39 Actor; P7's
    domain is E4 Period. A validator that only says "no" leaves the reader
    where they started."""
    from search import format_validation

    out = format_validation({
        "subject": "E39", "property": "P7", "object": "E53",
        "legal": False, "resolved": None,
        "candidates": [{"id": "P7", "name": "took place at",
                        "direction": "E4 -> E53", "legal": False,
                        "reason": "E39 is not a E4"}]})
    assert "No reading of this link is legal" in out
    assert "connect" in out


def test_show_renders_a_document_chunk_in_full():
    """`docs` prints ~300 characters of chunks that run past 2,000, and
    nothing else printed the rest -- so the snippet was the ceiling, not a
    preview. An agent reconstructed a modelling principle by guessing
    phrases for `quote` because of it."""
    from search import format_document_chunk

    out = format_document_chunk({
        "chunk_id": "crm732#s0071", "kind": "narrative",
        "cite": "CIDOC CRM v7.3.2", "section_path": ["Introduction", "Events"],
        "heading": "Relations with Events", "entities": ["E5", "E7"],
        "text": "x" * 1997})
    assert out.count("x") == 1997
    assert "crm732#s0071" in out
    assert "Introduction > Events" in out
