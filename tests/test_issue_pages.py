"""Tests for lib/issue_pages.py (Task 20: issue-page content).

Two tiers, mirroring tests/test_documents.py:
  * unit tests build small synthetic HTML fragments that reproduce the
    measured Drupal markup (field--name-field-* divs, field__items /
    field__item wrappers, the "References Issues:" view block) closely
    enough to exercise the field-by-field parsing precisely;
  * dedup tests pin down the paragraph-level guard against the mailing
    list -- the thing the design note says must actually bite.

Deliberately never fetches over the network: tools/fetch_issue_pages.py is
the network-touching maintenance script (mirroring tools/fetch_crm_issues.py,
which also has no direct tests), and this module only parses HTML it is
handed.
"""

from lib.issue_pages import (
    _normalize_for_match,
    build_issue_chunks,
    build_mailing_list_paragraphs,
    dedupe_paragraphs,
    load_cached_pages,
    parse_issue_page,
    parse_issue_pages,
)

FAKE_ONTO = {
    "classes": {"E1": {}, "E55": {}},
    "properties": {"P2": {}, "P49": {}, "P109": {}},
}
ID_PATTERN = r"\b([EP]\d+)\b"


def _field(slug: str, *items: str, wrap_items: bool = True) -> str:
    """One Drupal field div, with one `field__item` per positional arg --
    the real markup for a multi-item field (current-proposal, old-proposal)
    wraps its items in a `field__items` div; a single-item field (outcome,
    background) sometimes skips that wrapper. Both shapes must parse the
    same way, so tests exercise both via `wrap_items`.
    """
    inner = "".join(f'<div class="field__item">{item}</div>' for item in items)
    if wrap_items:
        inner = f'<div class="field__items">{inner}</div>'
    label = slug.replace("-", " ").title()
    return (
        f'<div class="field field--name-field-{slug} field--type-text-with-summary '
        f'field--label-above"><label class="field__label">{label}</label>'
        f"{inner}</div>"
    )


def _references_block(*rows: tuple[int, str]) -> str:
    row_html = "".join(
        f'<div class="views-row"><span class="views-field views-field-field-id">'
        f'<span class="field-content">{rid}</span></span>&nbsp;'
        f'<span class="views-field views-field-title"><span class="field-content">'
        f'<a href="/Issue/ID-{rid}-x" hreflang="und">{title}</a></span></span></div>'
        for rid, title in rows
    )
    return (
        '<section class="views-element-container block-views-blockissue-references-block-1">'
        '<div class="view view-issue-references">'
        '<header class="view-header"><p><label class="field__label">'
        "References Issues:</label></p></header>"
        f'<div class="view-content">{row_html}</div>'
        "</div></section>"
    )


def _page(*parts: str) -> str:
    return "<html><body><article>" + "".join(parts) + "</article></body></html>"


# ---------------------------------------------------------------------------
# parse_issue_page -- field extraction
# ---------------------------------------------------------------------------


def test_outcome_extracted_when_present():
    page = _page(_field("outcome", "<p>The CRM-SIG decided that P109 is subproperty of P49.</p>"))
    parsed = parse_issue_page(page)
    assert parsed["outcome"] == "The CRM-SIG decided that P109 is subproperty of P49."


def test_outcome_is_none_when_the_field_is_absent():
    """An Open issue's page simply has no outcome div at all -- absence must
    read as None, never as an empty-but-present resolution."""
    page = _page(_field("background", "<p>Some framing text.</p>"))
    parsed = parse_issue_page(page)
    assert parsed["outcome"] is None


def test_background_kept_whole_across_multiple_paragraphs():
    page = _page(_field("background", "<p>First paragraph.</p><p>Second paragraph.</p>"))
    parsed = parse_issue_page(page)
    assert parsed["background"] == "First paragraph.\n\nSecond paragraph."


def test_current_proposal_flattens_every_field_item_in_order():
    """current-proposal accumulates one field__item per pasted mailing-list
    message; all of them must come back as one ordered paragraph stream."""
    page = _page(
        _field(
            "current-proposal",
            "<p>Posted by Martin on 1/1/2020</p><p>First message body.</p>",
            "<p>Posted by Chryssoula on 2/1/2020</p><p>Second message body.</p>",
        )
    )
    parsed = parse_issue_page(page)
    assert parsed["current_proposal_paragraphs"] == [
        "Posted by Martin on 1/1/2020",
        "First message body.",
        "Posted by Chryssoula on 2/1/2020",
        "Second message body.",
    ]


def test_current_proposal_is_empty_list_when_absent():
    page = _page(_field("background", "<p>x</p>"))
    assert parse_issue_page(page)["current_proposal_paragraphs"] == []


def test_old_proposal_parses_the_same_way_as_current_proposal():
    page = _page(_field("old-proposal", "<p>An earlier draft.</p>"))
    parsed = parse_issue_page(page)
    assert parsed["old_proposal_paragraphs"] == ["An earlier draft."]


def test_single_item_field_without_the_items_wrapper_still_parses():
    """Some single-item fields (status, and occasionally outcome) render
    their one field__item directly, without the field__items wrapper the
    multi-item fields use. Both shapes must parse identically."""
    page = _page(_field("outcome", "<p>Closed.</p>", wrap_items=False))
    assert parse_issue_page(page)["outcome"] == "Closed."


def test_list_items_become_separate_paragraphs():
    page = _page(
        _field("current-proposal", "<ul><li>Redraft the scope note.</li><li>Add O29.</li></ul>")
    )
    parsed = parse_issue_page(page)
    assert parsed["current_proposal_paragraphs"] == [
        "Redraft the scope note.",
        "Add O29.",
    ]


def test_table_is_flattened_to_pipe_joined_rows_not_dropped():
    page = _page(
        _field(
            "background",
            "<table><tr><td>class</td><td>A category.</td></tr>"
            "<tr><td>property</td><td>A relation.</td></tr></table>",
        )
    )
    parsed = parse_issue_page(page)
    assert "class | A category." in parsed["background"]
    assert "property | A relation." in parsed["background"]


def test_html_entities_and_tags_are_unescaped_and_stripped():
    page = _page(_field("background", "<p>P2 &amp; P3 &mdash; scope &lt;note&gt;.</p>"))
    parsed = parse_issue_page(page)
    assert parsed["background"] == "P2 & P3 — scope <note>."


# ---------------------------------------------------------------------------
# References Issues: -- the curated cross-reference graph
# ---------------------------------------------------------------------------


def test_references_extracted_as_id_title_pairs_in_page_order():
    page = _page(
        _field("background", "<p>x</p>"),
        _references_block((449, "How to write examples"), (347, "Dimension and Data sets")),
    )
    parsed = parse_issue_page(page)
    assert parsed["references"] == [
        {"id": 449, "title": "How to write examples"},
        {"id": 347, "title": "Dimension and Data sets"},
    ]


def test_references_is_empty_list_when_the_page_has_no_block():
    page = _page(_field("background", "<p>x</p>"))
    assert parse_issue_page(page)["references"] == []


def test_parse_issue_pages_applies_to_every_cached_page():
    pages_html = {
        332: _page(_field("outcome", "<p>Decided.</p>")),
        482: _page(_field("background", "<p>Framing.</p>")),
    }
    parsed = parse_issue_pages(pages_html)
    assert parsed[332]["outcome"] == "Decided."
    assert parsed[482]["outcome"] is None


# ---------------------------------------------------------------------------
# load_cached_pages
# ---------------------------------------------------------------------------


def test_load_cached_pages_reads_every_html_file_keyed_by_id(tmp_path):
    (tmp_path / "332.html").write_text("<p>a</p>", encoding="utf-8")
    (tmp_path / "482.html").write_text("<p>b</p>", encoding="utf-8")
    pages = load_cached_pages(tmp_path)
    assert set(pages) == {332, 482}
    assert pages[332] == "<p>a</p>"


def test_load_cached_pages_returns_empty_dict_when_dir_absent(tmp_path):
    assert load_cached_pages(tmp_path / "does-not-exist") == {}


def test_load_cached_pages_ignores_non_numeric_filenames(tmp_path):
    (tmp_path / "332.html").write_text("<p>a</p>", encoding="utf-8")
    (tmp_path / "readme.html").write_text("<p>ignore me</p>", encoding="utf-8")
    assert set(load_cached_pages(tmp_path)) == {332}


# ---------------------------------------------------------------------------
# Paragraph-level dedup against the mailing list (deliverable #3) -- the
# guard the design note says must actually bite.
# ---------------------------------------------------------------------------


def test_build_mailing_list_paragraphs_splits_on_blank_lines():
    records = [{"body": "First paragraph,\nhard-wrapped.\n\nSecond paragraph."}]
    seen = build_mailing_list_paragraphs(records)
    assert "first paragraph, hard-wrapped." in seen
    assert "second paragraph." in seen


def test_build_mailing_list_paragraphs_strips_quote_markers_per_line():
    # lib.quotes marks a retained quoted line with "| "; the same content
    # posted as an ORIGINAL (unquoted) paragraph on an issue page must still
    # compare equal to it.
    records = [{"body": "| Dear All,\n| this is the original text."}]
    seen = build_mailing_list_paragraphs(records)
    assert "dear all, this is the original text." in seen


def test_dedupe_paragraphs_drops_exact_normalized_matches():
    seen = {"dear all, this is old news."}
    result = dedupe_paragraphs(["Dear All,\nthis is old news.", "This is genuinely new."], seen)
    assert result["kept"] == ["This is genuinely new."]
    assert result["dropped_count"] == 1
    assert result["kept_count"] == 1
    assert result["dropped_chars"] == len("Dear All,\nthis is old news.")
    assert result["kept_chars"] == len("This is genuinely new.")


def test_dedupe_paragraphs_is_whitespace_and_quote_insensitive():
    """The measured failure mode: the same text differs byte-for-byte
    between an email (hard-wrapped, typographic quotes) and a web page
    (reflowed HTML). Normalisation must still recognise it as one thing."""
    # seen holds an already-normalised key (as build_mailing_list_paragraphs
    # would produce it): straight quote, casefolded, single-spaced.
    seen = {"it's the same sentence, reflowed."}
    result = dedupe_paragraphs(["It’s the\nsame   sentence,\nreflowed."], seen)
    assert result["kept"] == []
    assert result["dropped_count"] == 1


def test_dedupe_paragraphs_keeps_everything_when_nothing_matches():
    result = dedupe_paragraphs(["Unique text one.", "Unique text two."], set())
    assert result["kept"] == ["Unique text one.", "Unique text two."]
    assert result["dropped_count"] == 0


def test_dedupe_paragraphs_bites_the_full_pipeline():
    """The guard this task's design note is built around: a proposal-log
    paragraph that is a byte-for-byte (once normalised) copy of a message
    already in the mailing-list corpus must not survive into the kept pile
    -- disabling this check is exactly the 3x-duplicated-store failure the
    module docstring describes.
    """
    records = [{"body": "Posted by Martin on 1/1/2020\n\nI propose the following property."}]
    seen = build_mailing_list_paragraphs(records)
    proposal_paragraphs = ["Posted by Martin on 1/1/2020", "I propose the following property."]
    result = dedupe_paragraphs(proposal_paragraphs, seen)
    assert result["kept"] == []
    assert result["dropped_count"] == 2


# ---------------------------------------------------------------------------
# build_issue_chunks -- the data/documents.jsonl record shape
# ---------------------------------------------------------------------------


def test_build_issue_chunks_emits_the_outcome_whole():
    """`outcome` is the one field kept intact: median 291 chars, never a
    pasted discussion, and the thing a reader most needs to see in one piece."""
    parsed = {
        332: {
            "outcome": "The SIG decided to close the issue.",
            "background": "Framing text.",
            "current_proposal_paragraphs": [],
            "old_proposal_paragraphs": [],
            "references": [],
        }
    }
    registry = {332: {"title": "Properties of S10", "status": "Done"}}
    records, stats = build_issue_chunks(parsed, registry, set(), ID_PATTERN, FAKE_ONTO, 2000, 200)
    by_chunk = {r["chunk_id"]: r for r in records}
    assert by_chunk["issue332#outcome"]["text"] == "The SIG decided to close the issue."
    assert by_chunk["issue332#outcome"]["kind"] == "issue"
    # background is chunked like the proposals now, so it is not at #background
    assert by_chunk["issue332#background-s0000"]["text"] == "Framing text."
    assert stats["with_outcome"] == 1
    assert stats["pages"] == 1


def test_background_is_deduplicated_against_the_mailing_list():
    """A median of 1,206 chars hid a tail that behaves like the proposal
    logs: issue 327's background is 48,101 chars and 68% of its paragraphs
    are already in the mailing list. Exempting it produced 15 chunks over
    20k, enough to OOM the embedder and useless as retrieval units."""
    pasted = "Posted by Martin on 20/7/2017 the scope note should be redrafted."
    parsed = {
        327: {
            "outcome": None,
            "background": pasted + "\n\nAn editorial note that never went to the list.",
            "current_proposal_paragraphs": [],
            "old_proposal_paragraphs": [],
            "references": [],
        }
    }
    registry = {327: {"title": "x", "status": "Open"}}
    records, _ = build_issue_chunks(
        parsed, registry, {_normalize_for_match(pasted)}, ID_PATTERN, FAKE_ONTO, 2000, 200
    )
    text = " ".join(r["text"] for r in records)
    assert "never went to the list" in text, "unique background must survive"
    assert "Posted by Martin" not in text, "duplicated background must be dropped"


def test_no_issue_chunk_is_an_unsplittable_wall_of_text():
    """The oversized-chunk guard: 20k+ chunks OOM'd the embedder at batch 16
    and rank diffusely, because BM25 normalises hard by length."""
    parsed = {
        1: {
            "outcome": None,
            "background": "\n\n".join(f"Paragraph {i} of a very long pasted thread." * 20
                                       for i in range(60)),
            "current_proposal_paragraphs": [],
            "old_proposal_paragraphs": [],
            "references": [],
        }
    }
    records, _ = build_issue_chunks(
        parsed, {1: {"title": "x", "status": "Open"}}, set(), ID_PATTERN, FAKE_ONTO, 2000, 200
    )
    assert records, "expected chunks"
    assert max(len(r["text"]) for r in records) < 4000, \
        [len(r["text"]) for r in records]


def test_build_issue_chunks_cite_names_the_issue_and_its_status():
    """Deliverable #4's explicit requirement: a reader must see at a glance
    whether they're reading a settled decision."""
    parsed = {332: {"outcome": "Decided.", "background": None,
                     "current_proposal_paragraphs": [], "old_proposal_paragraphs": [],
                     "references": []}}
    registry = {332: {"title": "Properties of S10", "status": "Done"}}
    records, _ = build_issue_chunks(parsed, registry, set(), ID_PATTERN, FAKE_ONTO, 2000, 200)
    cite = records[0]["cite"]
    assert "332" in cite and "Done" in cite and "Properties of S10" in cite


def test_build_issue_chunks_deduplicates_proposal_text_against_the_mailing_list():
    seen = {"this paragraph is already on the mailing list."}
    parsed = {
        332: {
            "outcome": None,
            "background": None,
            "current_proposal_paragraphs": [
                "This paragraph is already on the mailing list.",
                "This one is genuinely new to the web page.",
            ],
            "old_proposal_paragraphs": [],
            "references": [],
        }
    }
    registry = {332: {"title": "x", "status": "Open"}}
    records, stats = build_issue_chunks(parsed, registry, seen, ID_PATTERN, FAKE_ONTO, 2000, 200)
    texts = " ".join(r["text"] for r in records)
    assert "already on the mailing list" not in texts
    assert "genuinely new to the web page" in texts
    assert stats["proposal_dropped_paragraphs"] == 1
    assert stats["proposal_kept_paragraphs"] == 1


def test_build_issue_chunks_emits_nothing_when_proposal_fully_duplicated():
    seen = {"entirely duplicated text."}
    parsed = {332: {"outcome": None, "background": None,
                     "current_proposal_paragraphs": ["Entirely duplicated text."],
                     "old_proposal_paragraphs": [], "references": []}}
    registry = {332: {"title": "x", "status": "Open"}}
    records, stats = build_issue_chunks(parsed, registry, seen, ID_PATTERN, FAKE_ONTO, 2000, 200)
    assert records == []
    assert stats["proposal_dropped_paragraphs"] == 1


def test_build_issue_chunks_extracts_entities_via_extract_entities():
    parsed = {193: {"outcome": "P109 is subproperty of P49.", "background": None,
                     "current_proposal_paragraphs": [], "old_proposal_paragraphs": [],
                     "references": []}}
    registry = {193: {"title": "x", "status": "Done"}}
    records, _ = build_issue_chunks(parsed, registry, set(), ID_PATTERN, FAKE_ONTO, 2000, 200)
    outcome = next(r for r in records if r["chunk_id"] == "issue193#outcome")
    assert "P109" in outcome["entities"]
    assert "P49" in outcome["entities"]


def test_build_issue_chunks_reference_edge_count():
    parsed = {
        332: {"outcome": None, "background": None, "current_proposal_paragraphs": [],
              "old_proposal_paragraphs": [], "references": [{"id": 449, "title": "x"}]},
        482: {"outcome": None, "background": None, "current_proposal_paragraphs": [],
              "old_proposal_paragraphs": [],
              "references": [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}]},
    }
    registry = {332: {"title": "x", "status": "Done"}, 482: {"title": "y", "status": "Open"}}
    _, stats = build_issue_chunks(parsed, registry, set(), ID_PATTERN, FAKE_ONTO, 2000, 200)
    assert stats["reference_edges"] == 3


def test_build_issue_chunks_splits_long_proposal_remainder():
    parsed = {332: {"outcome": None, "background": None,
                     "current_proposal_paragraphs": [("word " * 1000).strip()],
                     "old_proposal_paragraphs": [], "references": []}}
    registry = {332: {"title": "x", "status": "Open"}}
    records, _ = build_issue_chunks(parsed, registry, set(), ID_PATTERN, FAKE_ONTO, 200, 20)
    current = [r for r in records if r["heading"] == "Current Proposal"]
    assert len(current) > 1
    assert all(len(r["text"]) <= 200 * 1.1 for r in current)
