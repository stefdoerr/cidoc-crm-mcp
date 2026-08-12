"""Issue-page content -> `kind: "issue"` document chunks, plus register
enrichment (Task 20).

Every issue in crm_issues.json carries a live page on cidoc-crm.org
(tools/fetch_crm_issues.py already recorded the real URL for each of the 715
-- never construct one from a title, the slugs are not derivable and a
guessed one 404s). tools/fetch_issue_pages.py caches each page's raw HTML
under data/issue_pages/{id}.html; this module is what turns that cache into
something retrievable.

Drupal renders each page field-by-field, and sampling ten pages measured
exactly what matters here:

  * `field--name-field-outcome` -- median 138 chars, and present precisely
    when the register's Status is "Done". It is the SIG's own statement of
    the resolution ("The CRM-SIG decided that P109 is subproperty of P49..."),
    naming the meeting that closed it. This is the whole point of the task:
    a blind evaluation scored 1/8 on "was this ever resolved?" with nothing
    but mailing-list prose to read.
  * `field--name-field-background` -- median 1,206 chars, the framing. Kept
    whole alongside outcome: both are small and not duplicated elsewhere.
  * `field--name-field-current-proposal` / `-old-proposal` -- not a proposal,
    an accumulated discussion log: issue 332's runs to 44,101 chars across 37
    pasted mailing-list messages (each its own `field__item` div -- Drupal's
    "add another item" widget), and 57% of its sentences appear verbatim in
    data/clean.jsonl. Indexed wholesale, this would be exactly the failure
    already fixed once here (a 3x-duplicated Chroma store that silently
    degraded ranking): the same text in two indexes, competing for the same
    result slots. `dedupe_paragraphs` is the guard -- paragraph by paragraph
    against the mailing list, keeping only the remainder (meeting minutes,
    editorial notes, decisions that never went to the list).
  * The "References Issues:" block -- a curated cross-reference list the SIG
    itself maintains on the page, distinct from lib.issues' regex-sieve
    mention detection (a number found near the word "issue" in prose). This
    needs neither of that module's guards: it is already a citation the SIG
    curated, not a candidate to validate.

Every field is located by its Drupal field-name class
(`field--name-field-outcome` etc.), never by regexing over the rendered
prose -- the same discipline lib.documents.parse_docx applies to paragraph
*styles* in the .docx.
"""

import html
import re
from pathlib import Path

from bs4 import BeautifulSoup

from lib.config import DATA_DIR

ISSUE_PAGES_DIR = DATA_DIR / "issue_pages"

# ---------------------------------------------------------------------------
# Locating one Drupal field's HTML by its field-name class, not by regex over
# the rendered prose.
# ---------------------------------------------------------------------------

_DIV_TAG = re.compile(r"<(/?)div\b[^>]*>", re.I)


def _balanced_div(page_html: str, start: int) -> str | None:
    """The full `<div ...> ... </div>` opened at `start` (the index of that
    opening tag), matching nested divs by count rather than the first
    `</div>` found -- a Drupal field wrapper and its `field__items` /
    `field__item` children are themselves divs, so a naive
    `.find("</div>")` would return only the first child's closing tag.
    """
    depth = 0
    for m in _DIV_TAG.finditer(page_html, start):
        depth += 1 if not m.group(1) else -1
        if depth == 0:
            return page_html[start : m.end()]
    return None


_FIELD_MARKER = {
    slug: re.compile(rf"field--name-field-{slug}\b")
    for slug in ("outcome", "background", "current-proposal", "old-proposal")
}


def _field_html(page_html: str, slug: str) -> str | None:
    """The whole `<div class="field field--name-field-{slug} ...">...</div>`
    for one of the four known slugs, or None if the page has no such field
    at all -- absence is the normal case for outcome/current-proposal on an
    Open issue, not an error.
    """
    m = _FIELD_MARKER[slug].search(page_html)
    if not m:
        return None
    div_start = page_html.rfind("<div", 0, m.start())
    if div_start == -1:
        return None
    return _balanced_div(page_html, div_start)


_ITEM_MARKER = re.compile(r'<div class="field__item">')

_BLOCK_TAGS = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote")


def _flatten_table(table) -> str:
    """A <table> (a handful of pages compare options side by side) to one
    "cell | cell" line per row -- the same flattening lib.documents._table_text
    applies to the .docx's own tables, so a comparison table reads as text
    rather than vanishing silently.
    """
    rows = []
    for row in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _html_to_paragraphs(fragment_html: str) -> list[str]:
    """One paragraph per block-level element (p, li, heading, blockquote) in
    a Drupal rich-text fragment, in document order, tags stripped and inner
    whitespace collapsed.

    Only LEAF block elements are collected -- a `<div>` or `<p>` wrapping
    other block tags contributes nothing itself; its children are what get
    collected, via the `tag.find(_BLOCK_TAGS)` check below. Without it, a
    `<li><p>text</p></li>` list item would double-count.

    A `<table>` is flattened via `_flatten_table` and spliced in as a `<p>`
    in its place before the main pass runs, so it participates in ordering
    and in the paragraph-level dedup exactly like everything else -- neither
    double-counted (its own `<td>`/`<tr>` are gone once replaced) nor
    dropped.

    Falls back to the whole fragment's text only when no block tag matched
    at all (a field__item that is bare inline text with no wrapping `<p>`,
    seen occasionally): dropping it entirely would silently lose content
    that the caller (a proposal-log paragraph, a background write-up) is
    supposed to see.
    """
    soup = BeautifulSoup(fragment_html, "html.parser")
    for table in soup.find_all("table"):
        replacement = soup.new_tag("p")
        replacement.string = _flatten_table(table)
        table.replace_with(replacement)

    paragraphs = []
    for tag in soup.find_all(_BLOCK_TAGS):
        if tag.find(_BLOCK_TAGS):
            continue
        text = " ".join(tag.get_text(" ", strip=True).split())
        if text:
            paragraphs.append(text)
    if not paragraphs:
        text = " ".join(soup.get_text(" ", strip=True).split())
        if text:
            paragraphs.append(text)
    return paragraphs


def _field_item_paragraphs(field_html: str) -> list[str]:
    """Every paragraph across every `field__item` in one field's HTML, in
    document order. A field with more than one item (current-proposal/
    old-proposal accumulate one item per pasted mailing-list message,
    sometimes dozens; background/outcome are normally a single item) is
    flattened into one ordered paragraph stream -- nothing downstream needs
    per-item structure, and this is what both `_field_text` (joins them back
    into one blob) and the proposal-log dedup (wants a flat paragraph list)
    are after.
    """
    paragraphs = []
    for m in _ITEM_MARKER.finditer(field_html):
        item_html = _balanced_div(field_html, m.start())
        if item_html:
            paragraphs.extend(_html_to_paragraphs(item_html))
    return paragraphs


def _field_text(page_html: str, slug: str) -> str | None:
    """outcome/background: kept whole, as a `\\n\\n`-joined blob rather than a
    paragraph list -- both fields are small (median 138 / 1,206 chars) and,
    per the module docstring, not duplicated against the mailing list, so
    there is nothing to deduplicate before indexing them.
    """
    field_html = _field_html(page_html, slug)
    if field_html is None:
        return None
    paragraphs = _field_item_paragraphs(field_html)
    return "\n\n".join(paragraphs) if paragraphs else None


def _field_paragraphs(page_html: str, slug: str) -> list[str]:
    """current-proposal/old-proposal: the raw paragraph list, undeduplicated
    -- the caller (build_issue_chunks) runs dedupe_paragraphs before this
    ever reaches an index."""
    field_html = _field_html(page_html, slug)
    if field_html is None:
        return []
    return _field_item_paragraphs(field_html)


# ---------------------------------------------------------------------------
# The "References Issues:" block -- a curated cross-reference list, not a
# regex sieve over prose (see module docstring).
# ---------------------------------------------------------------------------

_REFERENCES_LABEL = re.compile(r"References Issues:?", re.I)
_REFERENCE_ROW = re.compile(r'field-content">(\d+)</span></span>.*?<a[^>]*>([^<]*)</a>', re.S)


def _parse_references(page_html: str) -> list[dict]:
    """[{"id": int, "title": str}, ...] for every issue this page's own
    "References Issues:" block names, in the order the page lists them, or
    [] if the page has no such block (most issues don't).
    """
    label = _REFERENCES_LABEL.search(page_html)
    if not label:
        return []
    content_marker = page_html.find('class="view-content"', label.end())
    if content_marker == -1:
        return []
    div_start = page_html.rfind("<div", 0, content_marker)
    block = _balanced_div(page_html, div_start) if div_start != -1 else None
    if not block:
        return []
    return [
        {"id": int(m.group(1)), "title": html.unescape(m.group(2)).strip()}
        for m in _REFERENCE_ROW.finditer(block)
    ]


# ---------------------------------------------------------------------------
# Whole-page parsing
# ---------------------------------------------------------------------------


def parse_issue_page(page_html: str) -> dict:
    """Every structured field this task cares about, from one issue page's
    raw HTML: outcome and background kept whole (`str | None`), the two
    proposal fields as undeduplicated paragraph lists, and the reference
    graph. See the module docstring for what each means and why they're
    shaped this way.
    """
    return {
        "outcome": _field_text(page_html, "outcome"),
        "background": _field_text(page_html, "background"),
        "current_proposal_paragraphs": _field_paragraphs(page_html, "current-proposal"),
        "old_proposal_paragraphs": _field_paragraphs(page_html, "old-proposal"),
        "references": _parse_references(page_html),
    }


def parse_issue_pages(pages_html: dict[int, str]) -> dict[int, dict]:
    """`parse_issue_page` over every cached page, keyed by issue id."""
    return {iid: parse_issue_page(page_html) for iid, page_html in pages_html.items()}


def load_cached_pages(cache_dir: str | Path = ISSUE_PAGES_DIR) -> dict[int, str]:
    """{issue id: raw cached HTML} for every `<id>.html`
    tools/fetch_issue_pages.py has written to `cache_dir`.

    Returns {} if the cache directory doesn't exist yet -- the docs/issues
    build stages must run fine without it (no issue-page content is added,
    nothing else in the pipeline is affected), never raise.
    """
    cache_dir = Path(cache_dir)
    out: dict[int, str] = {}
    if not cache_dir.exists():
        return out
    for path in sorted(cache_dir.glob("*.html")):
        try:
            iid = int(path.stem)
        except ValueError:
            continue
        out[iid] = path.read_text(encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Paragraph-level deduplication against the mailing list (deliverable #3).
# ---------------------------------------------------------------------------
#
# The same text differs byte-for-byte between an email (hard-wrapped,
# ASCII/typographic quotes depending on the client, "| "-marked when this
# archive's own quote rules retained it as a quoted block -- see
# lib.quotes._MARK) and a web page (reflowed HTML, its own entity encoding).
# Comparison must normalise all of that away, or genuinely-duplicated text
# would be kept simply because it renders differently. It must NOT fuzzy
# match past that: two similar-but-different paragraphs are not the same
# content, and treating them as such would drop material that never
# actually went to the list.

_QUOTE_TRANS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "′": "'",  # single quotes, prime
    "“": '"', "”": '"', "„": '"', "″": '"',  # double quotes, prime
})
# Deliberately a small local copy rather than importing lib.retrieve's
# _QUOTE_TRANS: that name is private to that module, and this module has no
# other reason to depend on the query-serving layer.
_QUOTE_MARK_LINE = re.compile(r"^\s*[|>]+\s*")


def _normalize_for_match(text: str) -> str:
    """A comparison key, not display text: strips a leading quote marker
    (`| ` -- lib.quotes' own mark for a retained quoted line -- or `> `)
    from each line, joins lines with a single space (undoing hard-wrap and
    Drupal's own reflow alike), normalises typographic quotes to ASCII, and
    casefolds. Two paragraphs that are "the same words" through all of that
    compare equal; anything else does not.
    """
    lines = (_QUOTE_MARK_LINE.sub("", ln).strip() for ln in text.splitlines())
    joined = " ".join(ln for ln in lines if ln)
    joined = joined.translate(_QUOTE_TRANS)
    joined = re.sub(r"\s+", " ", joined).strip()
    return joined.casefold()


def build_mailing_list_paragraphs(records: list[dict]) -> set[str]:
    """Every paragraph of every cleaned message body, normalised -- the set
    `dedupe_paragraphs` checks a proposal-log paragraph against.

    Reads `body` (not `body_raw`): that is what the message index actually
    contains, so it is the right target for "is this already searchable
    elsewhere" -- a paragraph the archive's own cleaning stripped out (a
    footer, a redundant quote) is not actually duplicated in the index even
    if it is still visible in body_raw, and matching against body_raw would
    make this guard over-drop text that is unique in every index that
    exists.
    """
    seen: set[str] = set()
    for rec in records:
        body = rec.get("body") or ""
        for para in re.split(r"\n\s*\n", body):
            key = _normalize_for_match(para)
            if key:
                seen.add(key)
    return seen


def dedupe_paragraphs(paragraphs: list[str], mailing_list_paragraphs: set[str]) -> dict:
    """Keep every paragraph NOT already in `mailing_list_paragraphs`; drop
    the rest. Returns the kept paragraphs (original text, order preserved)
    plus char/paragraph counts for both piles, so a caller can report how
    much survived without a second pass over the same data.
    """
    kept: list[str] = []
    kept_chars = dropped_chars = kept_count = dropped_count = 0
    for para in paragraphs:
        key = _normalize_for_match(para)
        if key and key in mailing_list_paragraphs:
            dropped_chars += len(para)
            dropped_count += 1
        else:
            kept.append(para)
            kept_chars += len(para)
            kept_count += 1
    return {
        "kept": kept,
        "kept_chars": kept_chars,
        "dropped_chars": dropped_chars,
        "kept_count": kept_count,
        "dropped_count": dropped_count,
    }


# ---------------------------------------------------------------------------
# Chunk emission (deliverable #4)
# ---------------------------------------------------------------------------


def build_issue_chunks(
    parsed_by_id: dict[int, dict],
    registry: dict[int, dict],
    mailing_list_paragraphs: set[str],
    id_pattern: str,
    onto: dict,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[list[dict], dict]:
    """Turn parsed issue pages into `kind: "issue"` records for
    data/documents.jsonl, and report exactly how much of the accumulated
    proposal logs was kept versus dropped.

    Mirrors lib.documents.chunk_document's record shape (chunk_id/doc_id/
    cite/section_path/heading/text/entities) so these join the existing
    document index with no further work. `outcome` and `background` are
    indexed whole, one chunk each; `current-proposal`/`old-proposal` are
    deduplicated first via `dedupe_paragraphs` and only the remainder is
    split with the same RecursiveCharacterTextSplitter lib.documents uses
    for narrative text, so a pasted mailing-list message never ends up
    competing against its own original in a different index.

    `cite` names the issue AND its register status in the same string ("...
    Issue 332 (Done): ...") -- a reader must be able to tell a settled
    decision from an open debate without opening a thread, per the design
    note's whole complaint about blind evaluation reading "trails off" where
    a debate was in fact resolved.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    from lib.clean import extract_entities

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    records: list[dict] = []
    stats = {
        "pages": 0,
        "with_outcome": 0,
        "reference_edges": 0,
        "proposal_kept_chars": 0,
        "proposal_dropped_chars": 0,
        "proposal_kept_paragraphs": 0,
        "proposal_dropped_paragraphs": 0,
    }

    for iid in sorted(parsed_by_id):
        page = parsed_by_id[iid]
        stats["pages"] += 1
        if page.get("outcome"):
            stats["with_outcome"] += 1
        stats["reference_edges"] += len(page.get("references") or [])

        reg = registry.get(iid, {})
        title = reg.get("title") or f"Issue {iid}"
        status = reg.get("status") or "?"
        doc_id = f"issue{iid}"
        cite = f"CIDOC CRM SIG Issue {iid} ({status}): {title}"

        def make(chunk_id: str, heading: str, text: str) -> dict:
            entities, entities_hist = extract_entities(text, id_pattern, onto)
            return {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "doc_title": title,
                "cite": cite,
                "kind": "issue",
                "concept_id": None,
                "section_path": [f"Issue {iid}", heading],
                "heading": heading,
                "text": text,
                "entities": entities,
                "entities_historical": entities_hist,
            }

        # `outcome` alone is emitted whole: median 291 chars, p95 1,680, and
        # it is the SIG's own statement of the resolution -- the one field
        # that is never a pasted discussion, and the thing a reader most
        # needs to see intact rather than in pieces.
        if page.get("outcome"):
            records.append(make(f"{doc_id}#outcome", "Outcome", page["outcome"]))

        # `background` gets the same treatment as the proposals, not the
        # exemption its median suggests. A median of 1,206 chars hides a tail
        # that behaves exactly like the proposal logs: issue 327's background
        # is 48,101 chars and 68% of its paragraphs are already in the
        # mailing list; 286 is 46k at 62%; 266 is 22k at 72%. Left whole and
        # undeduplicated it produced 15 chunks over 20k -- big enough to OOM
        # the embedder at batch 16, and a poor retrieval unit besides, since
        # BM25 normalises hard by length and a 48k chunk answers everything
        # diffusely and nothing precisely.
        for slug, heading, tag in (
            ("background", "Background", "background"),
            ("current_proposal_paragraphs", "Current Proposal", "current"),
            ("old_proposal_paragraphs", "Old Proposal", "old"),
        ):
            source = page.get(slug) or []
            # `background` is stored as a joined blob (it is also served
            # whole elsewhere); the proposals are already paragraph lists.
            if isinstance(source, str):
                source = [p for p in re.split(r"\n\n+", source) if p.strip()]
            result = dedupe_paragraphs(source, mailing_list_paragraphs)
            stats["proposal_kept_chars"] += result["kept_chars"]
            stats["proposal_dropped_chars"] += result["dropped_chars"]
            stats["proposal_kept_paragraphs"] += result["kept_count"]
            stats["proposal_dropped_paragraphs"] += result["dropped_count"]
            kept = result["kept"]
            if not kept:
                continue
            blob = "\n\n".join(kept)
            for seq, piece in enumerate(splitter.split_text(blob)):
                if not piece.strip():
                    continue
                records.append(make(f"{doc_id}#{tag}-s{seq:04d}", heading, piece))

    return records, stats
