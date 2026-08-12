"""Stage: reference documents -> data/documents.jsonl (Task 17).

Extends the email-archive pipeline with the normative source: the CIDOC CRM
reference document itself, not just the mailing list arguing about it. See
docs/superpowers/specs/2026-08-06-document-corpus.md for the why.

Two block kinds come out of a .docx: `declaration` -- one per class or
property, keyed by its `concept_id`, kept whole so the concept dossier can
enrich a lookup with the FOL and full-path lines the XML does not carry --
and `narrative` -- everything else, carrying a heading path, which is the
modelling-guidance material that makes the document worth indexing at all.

This module does NOT index anything; it only produces the chunk records that
build.py's `docs` stage writes to data/documents.jsonl. Indexing is Task 18.

The docx specifics live entirely in `parse_docx`. `load_document` is the
general seam: a future PDF or HTML publication gets its own parser and slots
in beside `parse_docx` there, never through it.
"""

import re
from pathlib import Path

_HEADING_STYLES = {"Heading 1": 1, "Heading 2": 2, "Heading 3": 3, "Heading 4": 4}
_LABEL_STYLES = {"CRM Class Label", "CRM Property Label"}
_CONCEPT_ID_RE = re.compile(r"^([EP]\d+)\b")

# These three tables (Class Hierarchy, Property Hierarchy, ".1 Properties"
# Hierarchy) are the docx's own tabular rendering of exactly what
# cidoc_crm_v7.1.3.xml already encodes structurally. The design note is
# explicit that the XML stays the single structured source, so pulling them
# in here would be re-deriving the ontology from the docx, not adding new
# information -- the one thing this task is told not to do. Every other
# table in the document (glossary, FOL symbol key, quantification meanings,
# deprecation migration instructions) is genuine narrative and folds into
# whichever block is open when it's encountered.
_SKIP_TABLE_UNDER_H1 = {"Class & Property Hierarchies"}


def _table_text(table) -> str:
    """Flatten a docx table to text, one row per line.

    Deduplicates consecutive repeats within a row: python-docx reports the
    same `cell.text` for every cell a horizontal merge spans, so a naive join
    would repeat a merged header several times over.
    """
    lines = []
    for row in table.rows:
        cells: list[str] = []
        prev = None
        for cell in row.cells:
            text = cell.text.strip()
            if text and text != prev:
                cells.append(text)
            prev = text
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def parse_docx(path: str | Path) -> list[dict]:
    """Parse a CIDOC-CRM-style .docx into declaration/narrative blocks.

    Parses by paragraph *style*, never by regex over the prose -- the docx's
    styles (`CRM Class Label`, `CRM Property Label`, `CRM Scope Note Text`,
    `CRM First Order Logic`, `CRM Full Path`, `CRM Dot One Property`, and
    friends) are consistent even where the text is not.

    A block boundary is one of two things:
      * a `Heading 1`..`Heading 4` paragraph -- starts a new `narrative`
        block and updates the heading-path stack (truncating deeper levels,
        the usual nested-heading rule);
      * a `CRM Class Label` / `CRM Property Label` paragraph -- starts a new
        `declaration` block, keyed by the id at the front of its text
        (`E55 Type` -> `E55`, `P2 has type (is type of)` -> `P2`).

    Everything else -- `CRM Description Label` field labels, scope notes,
    examples, FOL lines, domain/range, quantification, super/sub
    cross-references, full paths, `CRM Property of Entity` lines, `Body
    Text` section intro prose, `Figur` captions, and the two styles a naive
    whitelist-based pass drops silently (`Properties:` under plain `Normal`,
    and the `.1` properties under `CRM Dot One Property`) -- is content of
    whatever block is currently open. There is deliberately no whitelist of
    "known" body styles: anything between two boundaries belongs to that
    block, whatever style Word happened to apply to it. Content before the
    first boundary (cover page, table of contents, table of figures) has no
    block open to join and is dropped.

    Tables are folded in too, in document order, via python-docx's
    `iter_inner_content()` -- except the three hierarchy tables under
    "Class & Property Hierarchies" (see `_SKIP_TABLE_UNDER_H1`).
    """
    import docx
    from docx.table import Table

    document = docx.Document(str(path))
    heading_levels: dict[int, str] = {}
    blocks: list[dict] = []
    current: dict | None = None

    def section_path() -> list[str]:
        return [heading_levels[level] for level in sorted(heading_levels)]

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        text = "\n".join(current["lines"]).strip()
        # A declaration is kept even if (implausibly) empty -- every
        # CRM Class/Property Label must produce a block, full stop. A
        # narrative block with nothing in it (two headings back to back,
        # or a heading immediately followed by a table-only section) is
        # not worth a chunk.
        if current["kind"] == "narrative" and not text:
            current = None
            return
        blocks.append(
            {
                "kind": current["kind"],
                "concept_id": current["concept_id"],
                "section_path": current["section_path"],
                "heading": current["heading"],
                "text": text,
            }
        )
        current = None

    for item in document.iter_inner_content():
        if isinstance(item, Table):
            path = section_path()
            if path and path[0] in _SKIP_TABLE_UNDER_H1:
                continue
            if current is not None:
                text = _table_text(item)
                if text:
                    current["lines"].append(text)
            continue

        style = item.style.name if item.style is not None else ""
        text = item.text.strip()

        if style in _HEADING_STYLES:
            flush()
            level = _HEADING_STYLES[style]
            for existing_level in list(heading_levels):
                if existing_level >= level:
                    del heading_levels[existing_level]
            heading_levels[level] = text
            path = section_path()
            current = {
                "kind": "narrative",
                "concept_id": None,
                "section_path": path,
                "heading": path[-1] if path else "",
                "lines": [],
            }
        elif style in _LABEL_STYLES:
            flush()
            match = _CONCEPT_ID_RE.match(text)
            current = {
                "kind": "declaration",
                "concept_id": match.group(1) if match else None,
                "section_path": section_path(),
                "heading": text,
                "lines": [],
            }
        else:
            if current is None:
                continue
            if text:
                current["lines"].append(text)

    flush()
    return blocks


def load_document(spec: dict, root: str | Path) -> list[dict]:
    """Dispatch to a format-specific parser by file suffix.

    `spec` is one entry of `config: documents:` -- `{id, path, title, cite}`.
    `root` is resolved against `spec["path"]` (mirrors how `cfg["mbox"]` is
    resolved against `PROJECT_ROOT` in lib/clean.py), so tests can point it
    at a tmp_path fixture instead of the real project directory.

    Keeps every docx-specific detail behind `parse_docx`: the next
    publication that shows up as a PDF or HTML page gets its own parser
    added here, beside this one, not folded into it.
    """
    path = Path(root) / spec["path"]
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return parse_docx(path)
    raise ValueError(f"load_document: no parser registered for {suffix!r} ({path})")


def chunk_document(
    spec: dict,
    blocks: list[dict],
    chunk_size: int,
    chunk_overlap: int,
    id_pattern: str,
    onto: dict,
) -> list[dict]:
    """Turn parsed blocks into the record shape written to documents.jsonl.

    Declarations stay whole: one chunk_id per concept_id
    (`{doc_id}#{concept_id}`), never split, because the concept dossier
    addresses them by that id and a split would break the very thing that
    makes them useful (the FOL and full-path lines have to be in the same
    chunk as the scope note that motivates them).

    Narrative blocks are split exactly as `lib.index.chunk_records` splits
    message bodies -- the same `RecursiveCharacterTextSplitter`,
    `chunk_size` and `chunk_overlap` -- and numbered with a stable
    sequential id (`{doc_id}#s0042`) so a citation into this document stays
    valid across rebuilds as long as the document's block order does not
    change.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    from lib.clean import extract_entities

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    doc_id, doc_title, cite = spec["id"], spec["title"], spec["cite"]

    def make(chunk_id: str, kind: str, concept_id: str | None, section_path: list[str],
              heading: str, text: str) -> dict:
        entities, entities_historical = extract_entities(text, id_pattern, onto)
        return {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "doc_title": doc_title,
            "cite": cite,
            "kind": kind,
            "concept_id": concept_id,
            "section_path": section_path,
            "heading": heading,
            "text": text,
            "entities": entities,
            "entities_historical": entities_historical,
        }

    records: list[dict] = []
    seq = 0
    for block in blocks:
        if block["kind"] == "declaration":
            records.append(
                make(
                    f"{doc_id}#{block['concept_id']}", "declaration", block["concept_id"],
                    block["section_path"], block["heading"], block["text"],
                )
            )
            continue
        # A document may declare its own kind. The default is "narrative",
        # which lib.retrieve treats as part of the reference model and
        # searches by default -- correct for the specification, wrong for a
        # working draft alongside it. Measured when the Conceptual Modelling
        # Principles v0.1.2 was first indexed as narrative: its 66 short
        # chunks, each containing the word "principle" in a header row, took
        # all five slots for "minimality principle" and pushed the
        # specification's own Minimality section off the page entirely.
        # Same burial that put SPEC_KINDS in retrieve.py, one level down.
        narrative_kind = spec.get("kind") or "narrative"
        for piece in splitter.split_text(block["text"]):
            if not piece.strip():
                continue
            records.append(
                make(
                    f"{doc_id}#s{seq:04d}", narrative_kind, None,
                    block["section_path"], block["heading"], piece,
                )
            )
            seq += 1
    return records


def build_documents(cfg: dict, onto: dict, root: str | Path) -> list[dict]:
    """Build the full data/documents.jsonl record set for one archive config.

    `cfg["documents"]` is the registry entry from config/archives.yaml (see
    lib/config.py's default `documents: []`); each spec is parsed and
    chunked independently and the results concatenated.
    """
    records: list[dict] = []
    for spec in cfg.get("documents") or []:
        blocks = load_document(spec, root)
        records.extend(
            chunk_document(
                spec, blocks, cfg["chunk_size"], cfg["chunk_overlap"],
                cfg["ontology"]["id_pattern"], onto,
            )
        )
    return records
