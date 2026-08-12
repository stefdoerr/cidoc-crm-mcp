"""Tests for lib/minutes.py (SIG meeting minutes as a fourth corpus).

Two tiers, mirroring tests/test_issue_pages.py:
  * unit tests over synthetic paragraph lists exercise the heading, section
    and chunking rules precisely, and never touch the network or the cache;
  * a small number of tests read data/minutes/ when it happens to be
    populated, and skip when it is not. Those exist because two of this
    module's decisions cannot be justified against synthetic data -- the
    Word 97 piece-table reader has to be shown to produce ordered prose from
    a real file, and the duplicate-meeting rule has to be shown to keep two
    genuinely different meetings apart. data/minutes is a gitignored cache,
    same as data/issue_pages, so they are skipped rather than required.

Every guard is written so that removing what it protects breaks it:

  * `test_bare_number_heading_needs_the_register` fails if the bare-number
    form stops being validated against real issue ids;
  * `test_chunk_never_exceeds_the_limit` fails if the heading is prepended
    without being budgeted for;
  * `test_heading_only_section_yields_a_link_but_no_chunk` fails if the two
    concerns are merged again;
  * `test_page_furniture_is_only_stripped_when_it_repeats` fails if the
    running-head filter is made unconditional;
  * `test_same_meeting_number_different_meetings_do_not_collide` fails if
    duplicate detection is ever moved back onto filenames or numbers.
"""

import pytest

from lib.minutes import (
    MAX_CHUNK_CHARS,
    MINUTES_DIR,
    _split_to_size,
    _strip_page_furniture,
    build_minutes_chunks,
    content_key,
    duplicate_groups,
    extract_paragraphs,
    heading_issues,
    is_heading,
    issue_links,
    parse_header,
    sections,
)

KNOWN = {161, 164, 166, 172, 173, 204, 295, 332, 345}


def paras(*rows):
    """(style, text) pairs; a bare string means an unstyled paragraph."""
    return [r if isinstance(r, tuple) else (None, r) for r in rows]


# --------------------------------------------------------------------------
# headings
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("ISSUE 345: properties having domain or range deprecated classes", [345]),
    ("Issue 161:How to organize extensions", [161]),
    ("Issue 166", [166]),
    ("issue: 204", [204]),
    ("Issue 172, 173", [172, 173]),
])
def test_explicit_issue_headings(text, expected):
    assert heading_issues(text) == expected
    assert is_heading(None, text)


def test_bare_number_heading_needs_the_register():
    """The 2010-2013 minutes head items with a bare number. That form is far
    too weak to trust on shape, so it counts only for numbers the SIG really
    assigned -- the same collection-as-authority rule lib.issues applies."""
    text = "204: The issue is done"
    assert heading_issues(text, KNOWN) == [204]
    assert is_heading(None, text, KNOWN)
    # without the register the form is not recognised at all
    assert heading_issues(text) == []
    assert not is_heading(None, text)


def test_bare_number_heading_rejects_a_number_that_is_not_an_issue():
    """A numbered list item must not cut the document into sections."""
    assert heading_issues("9999: not an issue number", KNOWN) == []
    assert heading_issues("3) third bullet in a list", KNOWN) == []
    assert not is_heading(None, "9999: not an issue number", KNOWN)


def test_word_heading_style_is_a_heading_whatever_the_text():
    assert is_heading("Heading 2", "Any wording at all")
    assert is_heading("Heading 1", "27 November 2018 crm-sig issues discussed")
    assert not is_heading("Normal", "Any wording at all")
    assert not is_heading("List Paragraph", "The scope note seems to conflate")


# --------------------------------------------------------------------------
# sections and chunks
# --------------------------------------------------------------------------

def test_content_before_the_first_heading_is_kept_as_preamble():
    """Participants, venue and date live there; dropping it loses who
    attended."""
    out = sections(paras("42nd joint meeting", "Berlin, 27-30 November 2018",
                         "Present: Martin Doerr, Christian-Emil Ore",
                         ("Heading 2", "ISSUE 345: deprecated classes"),
                         "The crm-sig voted in favour."))
    assert out[0]["heading"] == "Preamble"
    assert "Present: Martin Doerr, Christian-Emil Ore" in out[0]["lines"]
    assert out[1]["issues"] == [345]


def test_heading_only_section_yields_a_link_but_no_chunk():
    """"ISSUE 380" with no discussion is a real record of the agenda and a
    useless retrieval unit. It must link the issue without being indexed."""
    out = sections(paras(("Heading 2", "ISSUE 332: properties of S10"),
                         ("Heading 2", "ISSUE 345: deprecated classes"),
                         "The crm-sig voted in favour of deprecating P58."))
    empty = next(s for s in out if s["issues"] == [332])
    assert empty["lines"] == []
    assert next(s for s in out if s["issues"] == [345])["lines"]


def test_chunk_never_exceeds_the_limit():
    """The heading is prepended to the body, so it has to be budgeted for --
    splitting first and prepending afterwards silently overran the cap."""
    heading = "ISSUE 345: " + "a long agenda item title " * 8
    body = "Sentence number one is here. " * 800
    chunks = _split_to_size(body, MAX_CHUNK_CHARS - len(heading) - 1)
    for piece in chunks:
        assert len(f"{heading}\n{piece}") <= MAX_CHUNK_CHARS


def test_split_handles_text_with_no_sentence_breaks():
    wall = "x" * (MAX_CHUNK_CHARS * 2 + 50)
    pieces = _split_to_size(wall, MAX_CHUNK_CHARS)
    assert all(len(p) <= MAX_CHUNK_CHARS for p in pieces)
    assert "".join(pieces) == wall


# --------------------------------------------------------------------------
# pdf page furniture
# --------------------------------------------------------------------------

def test_page_furniture_is_stripped_when_it_repeats():
    pages = [f"42nd joint meeting minutes\nreal content {i}\n{i}" for i in range(6)]
    out = _strip_page_furniture(pages)
    assert not any("42nd joint meeting minutes" in p for p in out)
    assert all(f"real content {i}" in out[i] for i in range(6))


def test_page_furniture_is_only_stripped_when_it_repeats():
    """A sentence that genuinely recurs in a short document is content, not a
    running head; an unconditional filter would delete it."""
    pages = ["The issue is closed.\nfirst", "The issue is closed.\nsecond"]
    assert _strip_page_furniture(pages) == pages       # under the 3-page floor


# --------------------------------------------------------------------------
# header
# --------------------------------------------------------------------------

@pytest.mark.parametrize("line,expected", [
    ("27 - 30 November, 2018", "27 - 30 November, 2018"),
    ("Athens, 15/9/2008", "15/9/2008"),
    ("Documentation Standards Group Report, Nuremberg 1997", "1997"),
])
def test_dates_parse_from_their_several_formats(line, expected):
    assert parse_header(paras("A meeting of the CIDOC CRM SIG", line))["date"] == expected


def test_date_spanning_a_line_break_is_found():
    """PDFs break "9-10th December\\n2004" across lines; searching line by
    line sees a month with no year and a year with no month."""
    header = parse_header(paras("10th CIDOC CRM Special Interest Group Meeting",
                                "Venue: Germanisches Nationalmuseum, Nuremberg, 9-10th December",
                                "2004"))
    assert header["date"] == "9-10th December 2004"


def test_missing_date_is_reported_as_none_not_guessed():
    assert parse_header(paras("A meeting of the CIDOC CRM SIG",
                              "no date anywhere here"))["date"] is None


# --------------------------------------------------------------------------
# duplicate meetings -- the trap that motivated content-based detection
# --------------------------------------------------------------------------

def test_identical_text_is_a_duplicate():
    body = paras("42nd joint meeting", "Present: Martin Doerr", "ISSUE 345 discussed")
    assert content_key(body) == content_key(body)
    assert duplicate_groups({"a": content_key(body), "b": content_key(body)}) == [["a", "b"]]


def test_same_meeting_number_different_meetings_do_not_collide():
    """The whole reason duplicates are decided on text.

    `Meeting10_Minutes.doc` is the 10th FRBR/CRM harmonisation meeting,
    Edinburgh 2007; `10th_crm_meeting_minutes.pdf` is the 10th CRM SIG,
    Nuremberg 2004. Two numbering series, one number. Merging on the number
    deletes a meeting.
    """
    a = paras("Tenth Meeting on FRBR/CRM Harmonization together with 15th CIDOC CRM SIG",
              "e-Science Institute, Edinburgh", "9-12 July 2007")
    b = paras("10th CIDOC CRM Special Interest Group Meeting",
              "Germanisches Nationalmuseum, Nuremberg", "9-10th December 2004")
    assert content_key(a) != content_key(b)
    assert duplicate_groups({"a": content_key(a), "b": content_key(b)}) == []


def test_content_key_ignores_formatting_and_case():
    """The same minutes as .docx and as .pdf differ in whitespace and styling
    but are the same meeting."""
    a = paras(("Heading 1", "42nd JOINT Meeting"), "Present:  Martin   Doerr")
    b = paras("42nd joint meeting", "Present: Martin Doerr")
    assert content_key(a) == content_key(b)


# --------------------------------------------------------------------------
# real files -- skipped unless the cache has been fetched
# --------------------------------------------------------------------------

def _cached(suffix: str):
    if not MINUTES_DIR.exists():
        return []
    return sorted(p for p in MINUTES_DIR.iterdir() if p.suffix.lower() == suffix)


@pytest.mark.skipif(not _cached(".doc"), reason="data/minutes/ not fetched")
def test_word97_piece_table_returns_ordered_prose():
    """A fastsaved .doc stores its text in fragments that are not in reading
    order on disk. Scanning for printable runs returns the paragraphs
    shuffled, which reads plausibly and is wrong; the piece table is what
    puts them back in order. Asserted on real files because no synthetic
    fixture would exercise the format.
    """
    path = _cached(".doc")[0]
    paragraphs = extract_paragraphs(path)
    assert paragraphs, f"{path.name} produced no text"
    text = " ".join(t for _, t in paragraphs)
    assert len(text) > 2000
    # Real prose, not a soup of fragments: ordinary words, sane spacing.
    assert text.count(" ") > len(text) / 12


@pytest.mark.skipif(not _cached(".docx"), reason="data/minutes/ not fetched")
def test_real_meeting_chunks_are_within_the_limit_and_carry_issues():
    for path in _cached(".docx")[:4]:
        for chunk in build_minutes_chunks(path, known_issues=KNOWN | set(range(1, 730))):
            assert len(chunk["text"]) <= MAX_CHUNK_CHARS, chunk["chunk_id"]
            assert chunk["kind"] == "minutes"
            assert chunk["text"].strip()


@pytest.mark.skipif(not _cached(".docx"), reason="data/minutes/ not fetched")
def test_issue_links_cover_headings_that_have_no_body():
    known = set(range(1, 730))
    for path in _cached(".docx")[:6]:
        links = issue_links(path, known_issues=known)
        chunk_issues = {i for c in build_minutes_chunks(path, known_issues=known)
                        for i in c["issues"]}
        assert {ln["issue"] for ln in links} >= chunk_issues


@pytest.mark.skipif(not MINUTES_DIR.exists(), reason="data/minutes/ not fetched")
def test_no_two_cached_meetings_share_their_text():
    """The fetcher takes one format per meeting; if that ever regresses, or a
    meeting is published twice under different names, this catches it."""
    keys = {}
    for path in sorted(MINUTES_DIR.iterdir()):
        if path.suffix.lower() in (".docx", ".pdf", ".doc"):
            keys[path.stem] = content_key(extract_paragraphs(path))
    assert duplicate_groups(keys) == []
