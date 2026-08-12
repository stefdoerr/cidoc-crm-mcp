#!/usr/bin/env python3
# mcp_server.py
"""CIDOC CRM ontology and validator, served as MCP tools over stdio.

`search.py` is a CLI: an agent that wants a concept dossier or a document
checked has to shell out, re-read `data/ontology.json` from disk, and (for
anything that touches the archive) reload an embedding model -- 6-12s the
modelling brief spent a paragraph apologising for. This module is that same
functionality reached directly, in-process, over the Model Context Protocol,
so a long-lived assistant session pays the load cost once.

Every tool here is a thin wrapper: find the verb's branch in `search.py
main()`, reproduce exactly what it assembles before formatting, and return
the same string the CLI would have printed with `--json` omitted. Text, not
structured JSON, and deliberately so -- `format_concept`,
`format_document_validation` and the rest were tuned against the modelling
evaluations (leading with the definition, leading with counts and only the
failures, and so on). Inventing a second rendering for MCP would mean a
second thing to keep in sync with those evaluations, for no reader who
needs it: an agent can parse prose as easily as it can parse JSON, and this
way there is exactly one text to get right.

Two layers (see docs/superpowers/specs/2026-08-09-mcp-server-design.md):
an ontology layer that needs only `data/ontology.json`, always registered,
and an archive layer over the 26-year mailing list that needs
`data/clean.jsonl`, `data/threads.json` and `data/documents.jsonl`,
registered only when all three are present. A client reads the tool list
once -- a tool that is advertised and always fails is worse than one that
was never offered, the same "looks checked, is not" shape this codebase
keeps finding elsewhere (a stale class URI that resolves to nothing and
passes silently, an inverseOf claim nobody checks, ...). `build_server`
decides which layer(s) to register from the filesystem at construction
time and, if the archive layer is skipped, names the first missing file on
stderr -- never stdout, which carries the JSON-RPC transport and where a
stray line would corrupt it (confirmed empty in Task 2's stdio check).
Building `Retriever` at module scope is what makes that decision cheap:
every one of its data attributes is a `cached_property`, so constructing it
touches no archive file at all, and the twelve tools below -- which only
ever reach `.ontology`, `.episodes`, `.messages`, `.documents`, `.threads`
through methods that already return empty rather than raise when their
file is absent (Task 1, commit 6da8b26; `.threads` itself, this task) --
work unmodified whether or not the archive was ever built.
"""

import os
import sys
import tempfile
from pathlib import Path

from mcp.server import MCPServer

from lib.config import DATA_DIR
from lib.ontology import (
    connecting_properties,
    document_completeness,
    crm_example_class_uses,
    crm_example_links,
    crm_inverse_claims,
    crm_rdf_class_uses,
    crm_rdf_links,
    full_listing,
    resolve_uri,
    validate_class_labels,
    validate_document,
    validate_link,
)
from lib.retrieve import Retriever
from search import (
    concept_chronology,
    format_concept,
    format_connect,
    format_document_chunk,
    format_document_validation,
    format_documents,
    format_hits,
    format_issue,
    format_message,
    format_ontology,
    format_quote_result,
    format_thread,
    format_validation,
)

# The modelling evaluations' hard-won findings, verbatim from the design
# spec's Instructions section -- this is where they belong precisely
# because an instructions string is read once and then shapes every call
# a session makes, unlike a docstring on one tool that only the caller of
# that tool ever sees.
INSTRUCTIONS = """\
This server exposes the CIDOC CRM (v7.1.3, plus the family extensions and
the 7.3.2 declarations) as tools, and a validator for models written
against it.

Validate a whole document, not a link at a time. An agent that checks only
the links it already doubts skips the ones it got wrong -- this was
measured, not assumed.

`not_crm` and `unchecked` are reported and do not fail the check. They mean
"not examined", not "fine": a foreign predicate is outside this validator's
authority, and an untyped subject was never checked at all, which is a
different thing from having been checked and found legal.

Most intuitive binary relationships conceal a temporal entity. "Person made
Object" almost always has to be modelled through an E12 Production (or
similar event) rather than as a direct property -- the event-mediation
rule, and the single most common modelling error this validator sees.

The archive tools, where present, answer "why", which the ontology alone
cannot: a scope note says what a class is; the SIG mailing-list thread
behind it says what it is for and what was tried and rejected on the way
there.
"""

# Constructed once, at import time, and reused by every tool call below.
# Every data-bearing attribute is a cached_property (see lib/retrieve.py),
# so this line touches no archive file -- it only loads config/archives.yaml
# -- and is cheap enough that a test suite building dozens of servers pays
# nothing extra for it. Reusing one instance across calls is the entire
# point of a long-lived server process: the alternative is `search.py`'s
# per-invocation reload of data/ontology.json (and, for archive tools, the
# embedding model) that this module exists to stop paying for.
_RETRIEVER = Retriever()

# Prompts are files, not string literals in this module.
#
# The modelling prompt is the part of this server most worth iterating on:
# it is advice, it is wrong in ways only a real modelling run reveals, and
# the fix for "check the subject of every property, not only the property"
# was a paragraph. Keeping it in source means every such paragraph is a
# rebuild -- and in a container, a rebuild of a 2.5GB image to change 40
# words. `CRM_PROMPT_DIR` points at a directory of overrides; the packaged
# `prompts/` is the default and the fallback for any file not overridden.
#
# Deliberately re-read on every request rather than cached at import: the
# file is a few KB, the prompt is fetched rarely, and the point of the
# override is a loop where you edit and immediately try again. Caching would
# buy nothing measurable and cost a restart per edit.
_PACKAGED_PROMPTS = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str, **fields: str) -> str:
    """Read prompt `name` from the override dir, else from the packaged one.

    Substitution is `str.replace`, not `str.format`: a prompt is Markdown
    that may well grow a Turtle example, and Turtle is full of braces. A
    format string would make `{` an error in the one file most likely to be
    edited by someone who is not reading this comment.
    """
    override = os.environ.get("CRM_PROMPT_DIR")
    candidates = [Path(override) / f"{name}.md"] if override else []
    candidates.append(_PACKAGED_PROMPTS / f"{name}.md")

    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for key, value in fields.items():
            text = text.replace("{" + key + "}", value)
        return text

    raise FileNotFoundError(
        f"no prompt {name!r} in " + " or ".join(str(p.parent) for p in candidates)
    )


class _SourceError(Exception):
    """Raised inside a document-validator tool, and caught before it can
    leave it.

    A tool has no exit code, and (confirmed against the installed SDK) a
    function that raises out of `@server.tool` does not become an
    `is_error` result a caller can read `.content[0].text` from -- it
    propagates as an uncaught `ToolError` that kills the call. A malformed
    request (both `content` and `path`, or neither) is exactly the kind of
    mistake an agent needs to see and correct, not a reason to blow up the
    transport, so every raise site for this exception is paired with a
    `try/except _SourceError` in the same function, one frame up.
    """


def _resolve_source(
    content: str | None, path: str | None, default_suffix: str,
    rdf_format: str | None = None,
) -> tuple[str, bool]:
    """Turn `content` XOR `path` into a real filesystem path.

    Returns (path, is_temporary). The three readers this feeds
    (`crm_rdf_links`, `crm_inverse_claims`, `crm_rdf_class_uses`,
    `crm_example_links`) each take a path, and rdflib picks its parser from
    the path's suffix -- there is no "parse this string as Turtle" entry
    point to call instead. An MCP client is not guaranteed to share a
    filesystem with the server, and a model that just wrote some Turtle
    should be able to check it without saving a file first, so `content` is
    the common case for a remote caller and is written to a NamedTemporary
    File whose suffix `rdf_format` can override; `path` stays because the
    local case is the common one and a large document inline costs tokens
    on every call.

    Raises `_SourceError` (never returns) when the caller supplied neither
    or both -- a genuine "which one did you mean" mistake, not a case to
    silently default out of.
    """
    if (content is None) == (path is None):
        received = "both content and path" if content is not None else "neither content nor path"
        raise _SourceError(
            f"crm_validate needs exactly one of content or path (received {received})."
        )
    if path is not None:
        return path, False
    suffix = default_suffix
    if rdf_format:
        suffix = rdf_format if rdf_format.startswith(".") else f".{rdf_format}"
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8")
    try:
        fh.write(content)
    finally:
        fh.close()
    return fh.name, True


# ---- crm_concept ------------------------------------------------------------


def _crm_concept(identifier: str) -> str:
    """Mirrors `search.py main()`'s `concept` branch exactly (the entry
    lookup, the mention count's three-way bucket split, siblings,
    declaration and narratives, in that order) rather than reconstructing
    any of it from `format_concept`'s docstring -- see the module docstring
    on `search.py` concept_chronology and the CLI branch it comes from for
    why each of those five pieces is gathered before formatting at all.

    Returns "No such concept: <identifier>" text instead of the CLI's
    `SystemExit` for an unknown id: a tool has no exit code to carry that
    signal, and swallowing it (returning nothing, or an empty string) would
    be silent in exactly the way the source material has been repeatedly
    burned by. Mention counting iterates `r.messages`, which is `{}` in a
    checkout with no archive (Task 1) -- so a mention count of 0 there is
    the true count, not a stand-in for "couldn't check archive".
    """
    entry = _RETRIEVER.get_concept(identifier)
    if entry is None:
        hint = ""
        if "." in identifier:
            hint = ("\n(This looks like a property of a property. If "
                    "data/ontology.json predates the propertyOfProperty "
                    "parser, rebuild it: uv run python build.py ontology)")
        return f"No such concept: {identifier}{hint}"
    chrono = concept_chronology(_RETRIEVER.episodes, entry["id"])
    if entry.get("bucket") == "extensions":
        # Messages are never tagged with entities_extension (only episodes
        # are), so there is nothing to recount here -- the mention count
        # ontology.json already carries IS the count.
        mentions = entry.get("mentions", 0)
    elif entry.get("bucket") == "property_of_property":
        # Never counted: format_concept explains why on screen (the entity
        # index records the parent property, not the .N suffix).
        mentions = 0
    else:
        mentions = sum(
            1 for rec in _RETRIEVER.messages.values()
            if entry["id"] in rec.get("entities", []) + rec.get("entities_historical", [])
        )
    siblings = _RETRIEVER.concept_siblings(entry["id"])
    declaration = _RETRIEVER.get_declaration(entry["id"])
    narratives = _RETRIEVER.concept_narratives(entry["id"])
    return format_concept(entry, chrono, mentions, _RETRIEVER.ontology,
                          siblings, declaration, narratives)


# ---- crm_list ---------------------------------------------------------------


def _crm_list(model: str | None = None) -> str:
    """Mirrors the CLI's `ontology` branch: every identifier, or one model's
    if `model` is given, matched case-insensitively against `full_listing`'s
    own `source` field exactly as the CLI does."""
    listing = full_listing(_RETRIEVER.ontology)
    if model:
        wanted = model.lower()
        filtered = [s for s in listing if s["source"].lower() == wanted]
        if not filtered:
            models = sorted({s["source"] for s in listing})
            return f"No model named {model!r}. Known: {', '.join(models)}"
        listing = filtered
    return format_ontology(listing, onto=_RETRIEVER.ontology)


# ---- identifier normalisation -----------------------------------------------


def _as_identifier(value: str | None) -> str | None:
    """A class or property argument in whatever spelling the caller used.

    These tools print URIs and RDF local names -- `crm_concept` shows
    `http://www.cidoc-crm.org/cidoc-crm/E22_Human-Made_Object`, `crm_list`
    prints `E22_Human-Made_Object` in its name column -- and then only
    accepted the bare `E22`. An agent that had just read a local name off
    one tool and passed it to another got "No such concept:
    E22_HUMAN-MADE_OBJECT", four times in a row in one observed session,
    before falling back to guessing the short form.

    That is our inconsistency, not the caller's, and it was introduced by
    printing the local names in the first place: the more useful the output
    got, the more obviously wrong the input handling looked.

    `resolve_uri` already accepts a full URI, a `crm:`-prefixed name and a
    bare local name, and `uri_index` is what it reads, so this is the same
    resolution the validator applies to a document -- one spelling rule
    across the server. A prose label ("Human-Made Object") is not a URI and
    resolves to nothing here, so it falls through to `get_concept`, which
    is what handles labels.
    """
    if not value:
        return None
    resolved, _inverse = resolve_uri(_RETRIEVER.ontology, value)
    if resolved:
        return resolved
    entry = _RETRIEVER.get_concept(value)
    return entry["id"] if entry else None


# ---- crm_connect ------------------------------------------------------------


def _crm_connect(subject_class: str, object_class: str) -> str:
    """Mirrors the CLI's `connect` branch: both classes checked to exist
    before querying, both directions computed, and the CRM's own full-path
    expansion attached wherever the declaration carries one."""
    subject, obj = _as_identifier(subject_class), _as_identifier(object_class)
    for given, ident in ((subject_class, subject), (object_class, obj)):
        if ident is None:
            return (f"No such concept: {given}\n"
                    "(a bare identifier like E22, an RDF local name like "
                    "E22_Human-Made_Object, a full URI, or a label all work)")
    forward = connecting_properties(_RETRIEVER.ontology, subject, obj)
    backward = connecting_properties(_RETRIEVER.ontology, obj, subject)
    full_paths: dict[str, list[str]] = {}
    for row in forward + backward:
        declaration = _RETRIEVER.get_declaration(row["id"])
        if declaration and declaration.get("full_path"):
            full_paths[row["id"]] = declaration["full_path"]
    return format_connect(subject, obj, forward, backward, full_paths=full_paths)


# ---- crm_validate_link ------------------------------------------------------


def _crm_validate_link(subject: str, crm_property: str, object_class: str | None = None) -> str:
    """Mirrors the CLI's `validate` branch for a single triple (the --file
    and multi-triple summary line are CLI-only conveniences that do not
    apply to a tool call carrying exactly one triple). `format_validation`
    already states the verdict in its own text (LEGAL/no per candidate,
    then AMBIGUOUS / "Use X." / "no reading is legal"), so no extra verdict
    line is appended here the way the two document validators need one."""
    # Same spelling tolerance as crm_connect: the classes may arrive as a
    # bare id, a local name or a URI. The PROPERTY is left as given --
    # validate_link resolves property names itself, including ambiguous
    # labels, and reports every reading rather than picking one.
    subject = _as_identifier(subject) or subject
    object_class = _as_identifier(object_class) or object_class
    result = validate_link(_RETRIEVER.ontology, subject, crm_property, object_class)
    return format_validation(result)


# ---- crm_validate_rdf / crm_validate_xml ------------------------------------
#
# Both exist for the same reason `validate_document`'s docstring gives: an
# agent extracting shapes from its own model and validating the extracted
# identifiers checks a transcription, not the artifact, and a mistranscribed
# element name reaches the validator already "corrected". These read the
# document itself.


def _crm_validate_rdf(content: str | None = None, path: str | None = None,
                      rdf_format: str | None = None,
                      completeness: bool = False) -> str:
    """Mirrors search.py's ENTIRE `args.rdf` branch, not just the link
    check -- `crm_inverse_claims` first (its result is the `aliases` the
    reader needs to honour a document's own bridge claims), then
    `crm_rdf_links`, then `crm_rdf_class_uses` into `report["class_labels"]`,
    then `structural_elements_skipped` blanked (RDF has none to skip; that
    key exists only because `validate_document` cannot tell which reader
    produced its links), then `report["inverse_claims"] = claims`.

    Omitting any one of those steps drops a whole category of finding
    silently -- exactly the "exit 0 on a document that looks checked"
    failure this branch has been found to have four separate times, most
    recently by a reviewer who typed a CRMsci class the model renamed away
    from years ago and got no complaint at all, because nothing populated
    class_labels for the RDF path.

    The verdict line mirrors the CLI's own SystemExit rule so a caller can
    see pass/fail without an exit code to read: `illegal`, `unknown_name`,
    `unknown_class` or `not_a_class_link` in the link counts, an unknown or
    mistyped rdf:type in class_labels, or a contradicted/not_invertible
    owl:inverseOf claim -- any one of those fails the document, same as
    `search.py validate --rdf` exiting 1.
    """
    try:
        resolved, is_temp = _resolve_source(content, path, ".ttl", rdf_format)
    except _SourceError as e:
        return str(e)
    try:
        onto = _RETRIEVER.ontology
        claims = crm_inverse_claims(resolved, onto)
        report = validate_document(onto, crm_rdf_links(resolved, onto, aliases=claims))
        report["class_labels"] = crm_rdf_class_uses(resolved, onto)
        report["structural_elements_skipped"] = []
        report["inverse_claims"] = claims
        if completeness:
            report["completeness"] = document_completeness(
                onto, crm_rdf_links(resolved, onto, aliases=claims))
        text = format_document_validation(report)

        counts = report["counts"]
        bad_types = [f for f in report["class_labels"]
                     if f["verdict"] in ("unknown_class", "not_a_class")]
        wrong_claims = [c for c in claims
                       if c["verdict"] in ("contradicted", "not_invertible")]
        failed = bool(counts.get("illegal", 0) or counts.get("unknown_name", 0)
                     or counts.get("unknown_class", 0)
                     or counts.get("not_a_class_link", 0)
                     or bad_types or wrong_claims)
        verdict = (
            "FAILED -- at least one illegal or unresolved link, an unknown or "
            "mistyped class, or a false owl:inverseOf claim (the conditions "
            "`search.py validate --rdf` exits 1 on)."
            if failed else
            "PASSED -- every link resolves within its declared domain and "
            "range, every rdf:type is a class this model declares, and every "
            "owl:inverseOf claim holds (the conditions `search.py validate "
            "--rdf` exits 0 on)."
        )
        return f"{text}\n\nVerdict: {verdict}"
    finally:
        if is_temp:
            Path(resolved).unlink(missing_ok=True)


def _crm_validate_xml(content: str | None = None, path: str | None = None,
                      completeness: bool = False) -> str:
    """Mirrors search.py's `args.xml` branch: `crm_example_links` into
    `validate_document`, then `validate_class_labels` over
    `crm_example_class_uses` into `report["class_labels"]` -- the check that
    catches a document naming a class by a label the standard retired
    (both published CIDOC CRM examples do exactly this: `E22: Man-Made
    Object`, `E42: Object Identifier`).

    The verdict line mirrors the CLI's own SystemExit rule: `unknown_name`,
    `illegal`, `unknown_class`, `malformed` or `attached_to_property` in the
    link counts, or any class_labels finding other than the (non-failing)
    `label_mismatch`, fails the document -- same as `search.py validate
    --xml` exiting 1.

    `completeness` adds the opt-in section the CLI's --completeness flag
    prints: the properties the CRM declares `necessary` for a class that an
    instance does not state. Off by default, and it never changes the
    verdict, because the specification calls quantifiers "semantic
    clarification only" and asks that every property be implemented as
    optional -- so a missing one is guidance for an author, not an error
    (CIDOC CRM v7.3.2, Introduction > Applied Form > Property Quantifiers).
    """
    try:
        resolved, is_temp = _resolve_source(content, path, ".xml")
    except _SourceError as e:
        return str(e)
    try:
        onto = _RETRIEVER.ontology
        report = validate_document(onto, crm_example_links(resolved))
        report["class_labels"] = validate_class_labels(
            onto, crm_example_class_uses(resolved))
        if completeness:
            report["completeness"] = document_completeness(
                onto, crm_example_links(resolved))
        text = format_document_validation(report)

        counts = report["counts"]
        failed = bool(
            counts.get("unknown_name", 0) or counts.get("illegal", 0)
            or counts.get("unknown_class", 0) or counts.get("malformed", 0)
            or counts.get("attached_to_property", 0)
            or any(f["verdict"] != "label_mismatch" for f in report["class_labels"])
        )
        verdict = (
            "FAILED -- at least one unresolved name, illegal link, unknown "
            "class, malformed class label, or property nested inside a "
            "literal-valued one (the conditions `search.py validate --xml` "
            "exits 1 on)."
            if failed else
            "PASSED -- every element name resolves to a legal link and every "
            "in_class label is one the model currently uses (the conditions "
            "`search.py validate --xml` exits 0 on)."
        )
        return f"{text}\n\nVerdict: {verdict}"
    finally:
        if is_temp:
            Path(resolved).unlink(missing_ok=True)


# ---- the archive layer -------------------------------------------------------
#
# Six tools over the 26-year SIG mailing list, registered only when its data
# is present (see `_first_missing_archive_file` and `build_server` below).
# Each mirrors one `search.py main()` branch: the same assembly, in the same
# order, before the same `format_*` call -- not a rebuild from a formatter's
# docstring, for the reason `crm_validate_rdf` above already gives (four
# separate incidents of a step silently dropped).

_ARCHIVE_FILES = ("clean.jsonl", "threads.json", "documents.jsonl")


def _first_missing_archive_file() -> str | None:
    """The first of the three files the archive layer needs that is not on
    disk, or None if all three are there.

    Three, not the Chroma stores the design spec also names: this is the
    condition the brief states, and the brief is what decides scope here --
    inventing a fourth check the source material never asked for is exactly
    the kind of unstated constraint the global rules warn against. In every
    checkout this was verified against, the three files and the stores
    arrive together (one build pipeline writes both), so the distinction is
    academic in practice and literal in what was specified.

    Checked in a fixed order (`clean.jsonl`, `threads.json`,
    `documents.jsonl`) so the stderr line below is deterministic -- the same
    checkout always reports the same missing file, rather than whichever
    `os.listdir` order happened to return.
    """
    for name in _ARCHIVE_FILES:
        if not (DATA_DIR / name).exists():
            return name
    return None


# ---- crm_search ---------------------------------------------------------


def _crm_search(
    query: str, k: int = 10, mode: str = "hybrid", expand: bool = True,
    from_email: str | None = None, after: int | None = None,
    before: int | None = None, entity: str | None = None,
) -> str:
    """Mirrors the fallback branch at the bottom of `search.py main()` --
    the one reached when `query` matches none of the subcommand words --
    exactly: every filter `Retriever.search` exposes (`mode`, `expand`,
    `from_email`, `after`, `before`, `entity`), not just the query text,
    then `format_hits`. Dropping any one of those would silently narrow what
    a caller can ask for relative to the CLI it wraps.

    `Retriever.search` raises `ValueError` for an unknown `mode` -- the same
    check argparse's `choices=[...]` enforces before the CLI ever calls it.
    A tool has no argparse in front of it, so the check happens here
    instead, at the same place the CLI's user-facing message would: caught
    and returned as text, per this module's established rule that a raise
    out of a tool function becomes an uncaught `ToolError`, not a readable
    result (verified for `crm_validate_rdf`'s `_SourceError`, same mechanism).
    """
    try:
        hits = _RETRIEVER.search(
            query, top_k=k, mode=mode, expand=expand, from_email=from_email,
            after=after, before=before, entity=entity,
        )
    except ValueError as e:
        return str(e)
    return format_hits(hits)


# ---- crm_show -------------------------------------------------------------


def _crm_show(message_id: str, raw: bool = False) -> str:
    """Mirrors the CLI's `show` branch exactly, including the fallback the
    module docstring above warns not to assume away: `get_message` first,
    and only if that misses AND the id is a key in `r.documents` does this
    render a document chunk instead of a message -- `docs` prints a
    ~300-character snippet of chunks that run past 2,000, and this is the
    only place the rest of one can be read (see `format_document_chunk`'s
    own docstring for the reconstruction-by-probing incident that follows
    from skipping it).

    `raw` only ever reaches `format_message` (`body_raw` vs. the cleaned
    `body`); a document-chunk hit has no such distinction and ignores it,
    same as the CLI.

    Returns the CLI's own "No such message or document chunk" text, with
    its hint about where chunk ids come from, instead of `SystemExit`, for
    the reason every other miss in this module does: a tool has no exit
    code to carry that signal.
    """
    rec = _RETRIEVER.get_message(message_id)
    if rec is None and message_id in _RETRIEVER.documents:
        return format_document_chunk(_RETRIEVER.documents[message_id])
    if rec is None:
        return (
            f"No such message or document chunk: {message_id}\n"
            "(document chunk ids look like crm732#E12 or crm732#s0071 "
            "and are printed by `crm_docs`)"
        )
    return format_message(rec, raw=raw)


# ---- crm_thread -------------------------------------------------------------


def _crm_thread(thread_id: str) -> str:
    """Mirrors the CLI's `thread` branch: `get_thread` then `format_thread`.

    `get_thread` returns `[]` for an unknown id (never raises -- `threads`
    itself now returns `{}` rather than raise when `data/threads.json` is
    absent, the fix this task makes to `lib/retrieve.py`), and
    `format_thread([])` already renders "No such thread." -- so there is no
    miss case to special-case here the way `crm_show` and `crm_issue` need
    one for their own None branches.
    """
    return format_thread(_RETRIEVER.get_thread(thread_id))


# ---- crm_docs ---------------------------------------------------------------


def _crm_docs(query: str, k: int = 10, mode: str = "hybrid",
              kind: str | None = None) -> str:
    """Mirrors the CLI's `docs` branch: `search_documents(query, top_k=k,
    mode=mode, kind=kind)` then `format_documents`. `kind=None` is passed
    through rather than defaulted here, exactly as the CLI comment on this
    branch explains -- `search_documents` itself defaults to the reference
    model (declarations + narrative guidance) so the specification is never
    outranked by the much larger issue-page and minutes corpora simply for
    being smaller; a caller wanting those passes `kind="issue"` or
    `kind="minutes"` explicitly, the same as `--kind` on the CLI.

    `search_documents` raises `ValueError` for an unknown `mode` or `kind`
    (argparse's `choices=[...]` enforces both before the CLI reaches it);
    caught and returned as text for the same reason `crm_search` catches it.
    """
    try:
        docs = _RETRIEVER.search_documents(query, top_k=k, mode=mode, kind=kind)
    except ValueError as e:
        return str(e)
    return format_documents(docs)


# ---- crm_quote --------------------------------------------------------------


def _crm_quote(source_id: str, phrase: str) -> str:
    """Mirrors the CLI's `quote` branch: `find_quote(source_id, phrase)`
    then `format_quote_result`. Parameter named `source_id`, not `target`,
    to match `Retriever.find_quote`'s own parameter -- it already accepts a
    thread, episode, message or document-chunk id and resolves which kind
    itself, so there is no clearer or more specific name to invent here.

    `find_quote` raises `ValueError` on an empty phrase. The CLI never
    reaches that path (its branch requires `args.phrase` to be truthy before
    calling `find_quote` at all, so an empty phrase there falls through to a
    different, more confusing branch instead); a tool call has no such
    positional-argument gate, so an empty `phrase` is caught here and named
    directly rather than reproducing the CLI's accidental fallthrough.
    """
    if not phrase or not phrase.strip():
        return "crm_quote needs a non-empty phrase to search for."
    try:
        result = _RETRIEVER.find_quote(source_id, phrase)
    except ValueError as e:
        return str(e)
    return format_quote_result(result)


# ---- crm_issue --------------------------------------------------------------


def _crm_issue(issue_id: str) -> str:
    """Mirrors the CLI's `issue` branch: `get_issue` then `format_issue`,
    with the CLI's own "not known here" message (register size and how many
    issues carry archive discussion or page content in this build) returned
    as text instead of raised -- a miss here is exactly the kind of thing an
    agent needs to see and try a different id for, not a reason to kill the
    call.
    """
    issue = _RETRIEVER.get_issue(issue_id)
    if issue is None:
        return (
            f"No SIG issue {issue_id} is known here. The register holds "
            f"715 issues; {len(_RETRIEVER.issues):,} have archive discussion "
            "or recorded page content (outcome/background/proposals) in "
            "this build."
        )
    return format_issue(issue)


# ---- server assembly --------------------------------------------------------


def build_server(archive: bool = True) -> MCPServer:
    """Construct the MCP server: the ontology layer's six tools always, and
    the archive layer's six more when its data is present.

    A plain function, not module-level construction, so a test can build a
    fresh server per call (as `tests/test_mcp_server.py` does) without any
    registration state leaking between tests.

    `archive` defaults to True, meaning "register it if the data is there" --
    the real decision is made below, from the filesystem
    (`_first_missing_archive_file`), not from this flag. Passing `archive=
    False` forces the layer off unconditionally, which exists for exactly
    one reason: `test_the_archive_layer_is_absent_without_its_data` needs to
    exercise the absent-data code path in a checkout (like this repository's
    own) where the data actually IS present, and moving or hiding 38MB+ of
    real archive files just to test a code path would be a worse test than
    a flag. Forcing the layer off this way is a deliberate test-only choice,
    not a missing file, so it prints no stderr line -- the diagnostic below
    is for the genuine "data is missing" case, and a caller who explicitly
    asked for the layer off already knows why it is off.
    """
    server = MCPServer(name="cidoc-crm", instructions=INSTRUCTIONS, version="0.1.0")

    @server.tool(description="Look up one CIDOC CRM identifier or label: "
                             "definition, hierarchy, domain/range, siblings, "
                             "archive mention count and SIG debate history.")
    def crm_concept(identifier: str) -> str:
        return _crm_concept(identifier)

    @server.tool(description="Every identifier in one model, with the RDF local name to "
                             "write (E22_Human-Made_Object, P4_has_time-span and its "
                             "inverse P4i_is_time-span_of) and the namespace at the top, "
                             "so ONE call spells every identifier in that model. Use it "
                             "instead of calling crm_concept per identifier just for a "
                             "spelling. Pass model -- CRMbase (273 rows), CRMsci, "
                             "CRMarchaeo, historical, and so on. Omitting model returns "
                             "all 936 identifiers across every model at once, roughly "
                             "130KB, which many clients will truncate: ask for the models "
                             "you need instead.")
    def crm_list(model: str | None = None) -> str:
        return _crm_list(model)

    @server.tool(description="Find every property that can legally join two "
                             "classes, in both directions, including the "
                             "CRM's own declared full-path expansion where "
                             "one exists.")
    def crm_connect(subject_class: str, object_class: str) -> str:
        return _crm_connect(subject_class, object_class)

    @server.tool(description="Check whether one subject/property/object "
                             "triple is a legal CIDOC CRM link, reporting "
                             "every reading of an ambiguous property label.")
    def crm_validate_link(subject: str, crm_property: str,
                          object_class: str | None = None) -> str:
        return _crm_validate_link(subject, crm_property, object_class)

    @server.tool(description="Validate a whole RDF model (Turtle, RDF/XML, "
                             "N-Triples or JSON-LD) against the CRM: every "
                             "link's domain and range, every rdf:type, and "
                             "every owl:inverseOf claim. Pass content OR "
                             "path, exactly one.")
    def crm_validate_rdf(content: str | None = None, path: str | None = None,
                        rdf_format: str | None = None,
                        completeness: bool = False) -> str:
        return _crm_validate_rdf(content, path, rdf_format, completeness)

    @server.tool(description="Validate a whole document written in the "
                             "published CIDOC CRM example XML format: every "
                             "property element and every in_class label. "
                             "Pass content OR path, exactly one.")
    def crm_validate_xml(content: str | None = None, path: str | None = None,
                         completeness: bool = False) -> str:
        return _crm_validate_xml(content, path, completeness)


    # ---- prompts ----------------------------------------------------------
    #
    # Distilled from the brief eight agents worked from, minus everything
    # specific to that experiment. The brief also forbade reading the
    # repository and pointed at a cached article; those were controls for
    # measuring the server, not advice, and shipping them would be nonsense
    # for a real user who has a museum record and a filesystem.
    #
    # What is left is what those runs actually established. Deliberately no
    # worked answers: an earlier version of a tool description illustrated
    # itself with the class one agent had chosen, and the next agent chose
    # the same class and cited the description. A prompt is read before every
    # decision, so an example drawn from a finding is an answer key.

    @server.prompt(
        name="model_an_object",
        title="Model an object in CIDOC CRM",
        description="Instructions for producing a CIDOC CRM model of one "
                    "object as RDF/Turtle, using this server, and for "
                    "writing up the reasoning so a reviewer can argue with "
                    "it.")
    def model_an_object(subject: str, source: str = "the material you have been given") -> str:
        return _load_prompt("model_an_object", subject=subject, source=source)

    if archive:
        missing = _first_missing_archive_file()
        if missing is None:
            _register_archive_tools(server)
        else:
            # stderr, never stdout: stdout is the JSON-RPC transport (see
            # `server.run("stdio")` in `main()`), and a stray line there
            # corrupts every frame after it -- confirmed empty on stdout in
            # Task 2's by-hand stdio check, which this line must not change.
            # Named once, for the FIRST missing file only: a caller fixing
            # that one and re-running would otherwise be told about the
            # second file next, one at a time, for no reason -- the archive
            # layer needs all three, so which one is missing first is
            # enough to act on.
            print(
                f"cidoc-crm: archive layer not registered ({DATA_DIR / missing} "
                "not found) -- crm_search, crm_show, crm_thread, crm_docs, "
                "crm_quote and crm_issue are unavailable this run.\n"
                "cidoc-crm: to get them, run `uv run python build.py fetch` "
                "(~876MB), or `build.py fetch --no-vectors` for full-text "
                "search alone (~91MB, no embedding model needed).",
                file=sys.stderr,
            )

    return server


def _register_archive_tools(server: MCPServer) -> None:
    """The six archive tools, split out of `build_server` so the "all three
    files present" branch above stays a one-line call rather than a second
    indentation level wrapped around every `@server.tool` below.
    """

    @server.tool(description="Search 26 years of CIDOC CRM Special Interest Group "
                             "discussion. Use it when the ontology tells you WHAT a class "
                             "is and you need to know what it is FOR -- which of two "
                             "plausible classes the SIG actually intends, why a property "
                             "is shaped the way it is, how others modelled the case you "
                             "are modelling. A scope note cannot answer those; this list "
                             "argued them out. Returns message and thread ids to expand "
                             "with crm_show or crm_thread.")
    def crm_search(query: str, k: int = 10, mode: str = "hybrid",
                   expand: bool = True, from_email: str | None = None,
                   after: int | None = None, before: int | None = None,
                   entity: str | None = None) -> str:
        return _crm_search(query, k, mode, expand, from_email, after, before, entity)

    @server.tool(description="Show one mailing-list message or reference-"
                             "document chunk in full, by id. A document-"
                             "chunk id (e.g. crm732#E12) falls back to the "
                             "full chunk text where crm_docs shows only a "
                             "snippet.")
    def crm_show(message_id: str, raw: bool = False) -> str:
        return _crm_show(message_id, raw)

    @server.tool(description="Read a whole SIG thread in date order, by thread id. Worth "
                             "the call when a search hit looks like it settles a modelling "
                             "question you are stuck on. The list has argued out most of "
                             "the choices the specification leaves open, including several "
                             "where the answer is a class in a family extension rather "
                             "than in CRMbase, and the reasoning is in the thread rather "
                             "than in any scope note.")
    def crm_thread(thread_id: str) -> str:
        return _crm_thread(thread_id)

    @server.tool(description="Search the CIDOC CRM specification itself -- class and "
                             "property declarations plus the narrative modelling guidance "
                             "-- or, with kind, the issue register, meeting minutes or the "
                             "Conceptual Modelling Principles. Ask it the modelling "
                             "question directly, such as when an event should mediate a "
                             "relationship, or how a dimension is recorded. Bibliographies "
                             "and see-also lists are excluded by default. The "
                             "specification is domain-agnostic, so a subject-matter query "
                             "about grave goods or ship burials finds nothing, and that "
                             "absence is itself an answer: model it from the generic "
                             "classes.")
    def crm_docs(query: str, k: int = 10, mode: str = "hybrid",
                kind: str | None = None) -> str:
        return _crm_docs(query, k, mode, kind)

    @server.tool(description="Check whether a phrase actually occurs in a "
                             "thread, episode, message or document chunk, "
                             "and show it in context -- verify a quotation "
                             "before asserting it, since existence of the "
                             "source does not mean the wording is right.")
    def crm_quote(source_id: str, phrase: str) -> str:
        return _crm_quote(source_id, phrase)

    @server.tool(description="One SIG issue by number: its register status, its outcome, "
                             "and every thread and meeting that discussed it. This is the "
                             "decision record. If a modelling question was ever settled "
                             "formally it was settled as an issue, and the outcome and the "
                             "reasoning are here.")
    def crm_issue(issue_id: str) -> str:
        return _crm_issue(issue_id)


def main() -> None:
    """stdio by default; `--http` for a local endpoint.

    stdio is the normal way an MCP client runs a local server: the client
    spawns the process and talks over its pipes. It needs the command and
    the project directory in its config, which means the config carries an
    absolute path.

    `--http` avoids that. The server is started separately and the client is
    told only a URL, so nothing about where the project lives appears in the
    client's configuration:

        {"mcpServers": {"cidoc-crm": {"url": "http://127.0.0.1:8000/mcp"}}}

    Bound to loopback unless `--host` says otherwise, and deliberately so:
    there is no authentication here. On 0.0.0.0 this is an open endpoint
    that will run searches, load a ~2GB embedding model on first use, and
    serve 26 years of archive to anyone who can reach the port. Exposing it
    beyond the machine is a decision to make with a reverse proxy and a
    token in front, not with a flag.
    """
    import argparse

    parser = argparse.ArgumentParser(description="The CIDOC CRM MCP server.")
    parser.add_argument("--http", action="store_true",
                        help="serve over HTTP (streamable-http) instead of "
                             "stdio, so a client needs only a URL and no "
                             "filesystem path")
    parser.add_argument("--sse", action="store_true",
                        help="serve over HTTP using SSE, for clients that "
                             "expect that transport (Antigravity's serverUrl "
                             "is an SSE endpoint)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="interface for --http (default: loopback; see "
                             "the warning above before changing it)")
    parser.add_argument("--port", type=int, default=8000,
                        help="port for --http (default: 8000)")
    parser.add_argument("--warm", action="store_true",
                        help="load the vector stores before serving, so the "
                             "first search is fast instead of ~9.5s")
    args = parser.parse_args()

    # Before the port is bound, so a healthcheck reports unhealthy until the
    # server can actually answer quickly, and an orchestrator does not route
    # anyone to a process that will make them wait 24s. Deliberately not the
    # default: stdio clients spawn a process per session, and paying this on
    # every spawn would be worse than paying it once on the first search.
    if args.warm:
        loaded = _RETRIEVER.warm()
        print(f"cidoc-crm: warmed {', '.join(loaded) or '(no vector stores)'}",
              file=sys.stderr)

    if not (args.http or args.sse):
        build_server().run("stdio")
        return

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"cidoc-crm: serving on {args.host}:{args.port} with no "
              f"authentication -- anyone who can reach this port can use it.",
              file=sys.stderr)
    # host/port are run() kwargs, not settings: the Settings model has no
    # such fields and assigning them raises.
    #
    # Two HTTP transports, because clients disagree about which they speak.
    # streamable-http is the current one and serves /mcp; SSE is the older
    # one and serves /sse with a companion /messages/ path. Antigravity's
    # `serverUrl` is an SSE endpoint. A client pointed at the wrong one gets
    # a 404 or a 400 rather than anything naming the mismatch, which reads
    # as the server being broken.
    if args.sse:
        build_server().run("sse", host=args.host, port=args.port)
        return

    # stateless_http, because a stateful streamable-http session rejects any
    # request that arrives without the `mcp-session-id` header, with a bare
    # 400 and no explanation. Antigravity opens fresh connections and does
    # not always carry the header -- its very first post-handshake message,
    # `notifications/roots/list_changed`, comes back 400, and it treats that
    # as the session dying:
    #
    #     MCP server connection closed unexpectedly for cidoc-crm:
    #       sending "notifications/roots/list_changed": Bad Request
    #
    # The symptom is confusing rather than obvious: discovery succeeds, the
    # client caches a complete tool manifest, and then the agent has no
    # callable tools and starts hunting the filesystem for a CLI.
    #
    # Nothing here needs a session. Every tool is a pure function over one
    # shared, read-only ontology; there is no per-client state to keep
    # between calls, so the session was only ever a way to fail.
    build_server().run("streamable-http", host=args.host, port=args.port,
                       stateless_http=True)


if __name__ == "__main__":
    main()
