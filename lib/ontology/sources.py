"""Folding in a source the specification XML is not.

`cidoc_crm_v7.1.3.xml` is not the only text this package has to reconcile:
the newer declarations corpus (v7.3.2) names concepts the XML has never
heard of, the normative RDFS encoding carries constructs the presentation
XML has no entry for (P81a/P81b, P82a/P82b, ...), and the family
extensions' own RDFS gives their entries the URIs `crm_family.json` never
recorded. `add_spec_additions`, `add_rdfs_additions` and `add_family_rdfs`
are the three ways something not in the XML gets added to the model
afterwards; `_decl_section`/`_first_id`/`_family_local_id` are the small
readers each of them needs and no one else does.
"""

import re
from pathlib import Path

from .uris import (CRM_NAMESPACE, _NAMESPACE_CACHE, _URI_INDEX_CACHE,
                   _namespace_of, resolve_uri, uri_index)

# ---- concepts newer than the XML ------------------------------------------
#
# data/ontology.json is parsed from cidoc_crm_v7.1.3.xml, but the declarations
# corpus is CIDOC CRM v7.3.2, and 7.3.2 added concepts 7.1.3 has never heard
# of. Before this, those landed in the `historical` bucket -- because
# add_historical sweeps every archive-mentioned id the XML does not define
# into it -- and `concept P200` answered:
#
#     P200 -- no definition in v7.1.3 (deprecated vocabulary)
#     CIDOC CRM v7.1.3 no longer defines this identifier. The archive below
#     is the only surviving record of what it meant and why it was removed.
#
# which is the exact opposite of the truth for a property added later. The
# bucket means "the standard dropped this"; these are "the standard gained
# this", and the two must not be confused. `eval_domains` also reported a
# correct citation of P200 as an unknown identifier, because the merged model
# view reads classes, properties and extensions but not historical.

_DECL_ID = re.compile(r"\b([EP]\d{1,3})\b")


def _decl_section(text: str, header: str) -> list[str]:
    """Non-blank lines under `header` in a flattened declaration block."""
    headers = {"Subclass of:", "Subproperty of:", "Superclass of:",
               "Superproperty of:", "Domain:", "Range:", "Quantification:",
               "Scope note:", "Properties:", "Full path:", "Examples:",
               "Example:", "In first-order logic:"}
    lines = text.split("\n")
    try:
        start = lines.index(header) + 1
    except ValueError:
        return []
    end = start
    while end < len(lines) and lines[end].strip() not in headers:
        end += 1
    return [ln.strip() for ln in lines[start:end] if ln.strip()]


def _first_id(lines: list[str], letter: str = "EP") -> str | None:
    """First identifier of the wanted kind on these lines.

    `letter` matters. A class states its parent plainly -- "E73 Information
    Object" -- but a property states a full path, "E90 Symbolic Object.
    P128i is carried by (carries): E18 Physical Thing", whose FIRST id is the
    domain class and whose parent is the property in the middle. Taking the
    first id of any kind recorded P200's parent as E90, a class, which is not
    a property and not its parent.
    """
    pattern = re.compile(rf"\b([{letter}]\d{{1,3}})i?\b")
    for line in lines:
        found = pattern.search(line)
        if found:
            return found.group(1)
    return None


def add_spec_additions(onto: dict, declarations: dict[str, dict]) -> list[str]:
    """Fold concepts the newer specification declares but the XML lacks.

    `declarations` maps concept id -> a record with `heading` and `text`, as
    data/documents.jsonl stores them.

    Added to `classes`/`properties` rather than to a bucket of their own, so
    every existing reader gets them for free: the merged model view, the
    applicable-property closure, `connect`, `validate` and the listing all
    work without knowing this function ran. Each carries
    `source: "CIDOC CRM v7.3.2"`, because "current" here rests on a different
    document from every neighbouring entry and a reader comparing two scope
    notes should be able to see that.

    A parent is read as the first identifier on the line: a class states it
    plainly ("E73 Information Object") but a property states a full path
    ("E36 Visual Item. P138 represents (has representation): E1 CRM Entity"),
    where the parent is the property in the middle.

    Returns the ids added, and removes each from `historical` -- leaving it
    there would keep `concept` reporting a new property as deprecated.
    """
    added: list[str] = []
    known = set(onto.get("classes") or {}) | set(onto.get("properties") or {})
    for cid, record in sorted(declarations.items()):
        if cid in known:
            continue
        text = record.get("text") or ""
        heading = (record.get("heading") or cid).strip()
        # "P199 represents instance of type (type of instance represented)"
        rest = heading[len(cid):].strip() if heading.startswith(cid) else ""
        direct, inverse = rest, ""
        if rest.endswith(")") and "(" in rest:
            direct, inverse = rest[:rest.rindex("(")].strip(), \
                rest[rest.rindex("(") + 1:-1].strip()

        common = {
            "id": cid,
            "full_name": heading,
            "scope_note": " ".join(_decl_section(text, "Scope note:")),
            "examples": _decl_section(text, "Examples:"),
            "status": "current",
            "source": "CIDOC CRM v7.3.2",
        }
        if cid.startswith("E"):
            onto.setdefault("classes", {})[cid] = {
                **common,
                "label": direct or heading,
                "sub_class_of": [p for p in [_first_id(
                    _decl_section(text, "Subclass of:"), "E")] if p],
            }
        else:
            onto.setdefault("properties", {})[cid] = {
                **common,
                "direct_name": direct,
                "inverse_name": inverse,
                "domain": _first_id(_decl_section(text, "Domain:")),
                "range": _first_id(_decl_section(text, "Range:")),
                "sub_property_of": [p for p in [_first_id(
                    _decl_section(text, "Subproperty of:"), "P")] if p],
                "quantification": " ".join(_decl_section(text, "Quantification:")),
            }
        (onto.get("historical") or {}).pop(cid, None)
        added.append(cid)
    return added
# ---- the RDFS as a second source -------------------------------------------
#
# data/ontology.json is parsed from the spec's presentation XML, and the XML
# synthesizes every URI from a label (_local_name does the synthesis). CIDOC
# also publishes a normative RDFS encoding, and real CRM RDF is written
# against THAT, not against the presentation text. The two are not the same
# document: the RDFS carries constructs that exist only because RDF needs
# them. A fuzzy date boundary -- "sometime between the 3rd and the 5th
# century" -- is written in real CRM RDF with P81a/P81b (the outer bound of
# "ongoing throughout") and P82a/P82b (the outer bound of "at some time
# within"), and the presentation XML has no entry for any of the four, so
# before this function existed the validator rejected the standard way to
# write a date. Measured (2026-08-09): the RDFS declares 76 classes and 309
# properties in the CRM namespace; of those, exactly 7 are not already
# reachable through the XML-derived model: P81a, P81b, P82a, P82b, P90a,
# P90b and E33_E41_Linguistic_Appellation -- a class the RDFS declares
# subClassOf BOTH E33 Linguistic Object and E41 Appellation, the one shape
# in this batch a single-parent assumption would silently mishandle.

# rdflib logs a full traceback to stderr when a literal's lexical form will
# not convert to its declared datatype -- and then keeps the literal anyway,
# as a plain string, which is exactly what this reader wants. The commonest
# trigger here is a BCE date: "-0900-01-01"^^xsd:date is legal Turtle and
# meaningful to a heritage modeller, and Python's date type cannot hold it.
#
# The parse succeeds, the document validates, and the link is reported
# ok_literal -- the checker never needs a literal's typed VALUE, only that
# its subject and predicate are legal. But 21 lines of traceback do not read
# as "fine": an agent modelling a Western Zhou bronze saw one, concluded its
# BCE date was unparseable, and edited a correct file to remove it.
#
# Quieted at parse time only, and only rdflib's own converter logger. A
# genuine syntax error still raises, and still surfaces.
def _quiet_literal_warnings():
    import logging

    for name in ("rdflib.term", "rdflib"):
        logging.getLogger(name).setLevel(logging.ERROR)


def add_rdfs_additions(onto: dict, rdfs_path: str | Path) -> list[str]:
    """Fold in every identifier the normative RDFS declares and we lack.

    data/ontology.json is parsed from the spec's presentation XML, which
    synthesizes URIs from labels. Real CRM RDF is written against CIDOC's
    RDFS encoding, and the two are not identical: the RDFS carries
    constructs that exist only because RDF needs them. P82a/P82b and
    P81a/P81b are how a fuzzy date boundary is written, and before this
    the validator rejected all four -- the standard way to write a date.

    Additive only. Where an identifier already exists the XML wins: it is
    the normative text and it carries the scope notes. Measured before
    this was written: the two sources agree on domain and range across
    all 158 properties present in both, so nothing is lost by preferring
    the XML, and the agreement is asserted by a test rather than assumed.

    Derived, never hand-listed -- a later RDFS release brings its own
    additions with no code change here. Concretely: every CRM-namespace
    subject typed as a class or a property is a *candidate*; a candidate
    already reachable through `uri_index` is skipped (requirement 3); of
    what remains, an identifier is recovered by stripping the
    "_Label_With_Underscores" suffix the RDFS local name carries -- never
    by splitting on the first underscore, which breaks the one identifier
    in this release that itself contains an underscore (E33_E41). A
    candidate whose local name does not end in its own label, or that
    carries no usable label at all, cannot be resolved this way and is
    reported by raising rather than silently dropped -- the RDFS evolving
    in a way this derivation cannot follow is exactly the situation a
    silent skip would hide.

    Every added entry carries `source: "rdfs"`, the same shape a
    same-source scan already reports; see
    `test_rdfs_additions_are_marked_with_their_source`.
    """
    from rdflib import Graph, OWL, RDF, RDFS
    from rdflib.term import URIRef

    graph = Graph()
    _quiet_literal_warnings()
    graph.parse(str(Path(rdfs_path)), format="xml")

    # Requirement 1: the RDFS's own rdf:type usage is inconsistent about
    # WHICH of these five it picks for a given property (P1_is_identified_by
    # is typed rdf:Property, others in the same file are typed
    # owl:ObjectProperty), so typing alone cannot separate classes from
    # properties. `_model_view` already answered this for the merged model
    # view by checking for a `domain` key instead of trusting the caller's
    # label for what kind of thing an entry is -- the same split is applied
    # below, on `rdfs:domain` rather than on rdf:type.
    _CANDIDATE_TYPES = {RDFS.Class, OWL.Class, RDF.Property,
                        OWL.ObjectProperty, OWL.DatatypeProperty}

    candidates: dict[str, URIRef] = {}
    for subject, _, rdf_type in graph.triples((None, RDF.type, None)):
        if rdf_type in _CANDIDATE_TYPES and str(subject).startswith(CRM_NAMESPACE):
            candidates[str(subject)] = subject

    # Requirement 3 + requirement 9's premise: computed ONCE, before any
    # mutation of `onto` below. Every lookup against the pre-existing model
    # in this function reads THIS snapshot, not a live `onto["properties"]`
    # walk, so an addition made partway through this loop can never make an
    # earlier-processed candidate look "already known" -- the ordering is
    # irrelevant to correctness, only to which of two equally-valid parents
    # gets picked first when several are known.
    index = uri_index(onto)

    def local_name(uri: str) -> str:
        return uri[len(CRM_NAMESPACE):]

    def english_label(subject: URIRef) -> str | None:
        # Requirement 5: every property in this file carries a label in six
        # languages (en, de, el, fr, pt, ru; confirmed by reading P82a's
        # triples directly), and rdflib's own iteration order over multiple
        # objects of the same predicate is not the document order -- it is
        # whatever its internal store's hash seed gives, the same
        # nondeterminism `crm_rdf_links` already sorts its own output
        # against. Taking "whichever rdflib yields first" would derive an
        # identifier from a German or Greek label at random. en always wins
        # when present; a label with no xml:lang at all is the fallback for
        # anything published with only one label.
        labels = list(graph.objects(subject, RDFS.label))
        for lit in labels:
            if lit.language == "en":
                return str(lit)
        for lit in labels:
            if lit.language is None:
                return str(lit)
        return None

    def derive_ident(local: str, label: str) -> str | None:
        # Requirement 4: the local name is
        # f"{identifier}_{label with spaces as underscores}", so the
        # identifier is recovered by stripping that suffix, not by
        # splitting on the first underscore. A first-underscore split gives
        # E33 for E33_E41_Linguistic_Appellation's local name, which is a
        # real CRM identifier (Human-Made Object's superclass) but the
        # WRONG one -- the RDFS names this class E33_E41, not E33, because
        # it is the union of E33 and E41 (see the module comment above).
        suffix = "_" + re.sub(r"\s+", "_", label.strip())
        if local.endswith(suffix) and len(local) > len(suffix):
            return local[: -len(suffix)]
        return None

    def resolved_parent(uri_value) -> str | None:
        """The identifier `uri_value` already resolves to in the
        pre-mutation model, or None if the RDFS points somewhere this
        model does not (yet) know. Used for domain, range and every
        subClassOf/subPropertyOf parent -- all of them are, structurally,
        "a URI this model may already have an opinion about."""
        if uri_value is None:
            return None
        hit = index.get(local_name(str(uri_value)).lower())
        return hit[0] if hit else None

    added: list[str] = []
    unresolved: list[str] = []
    literal_range = str(RDFS.Literal)

    for uri_str in sorted(candidates):
        local = local_name(uri_str)
        if local.lower() in index:
            continue  # requirement 3: the XML (or an earlier pass) already has this

        subject = candidates[uri_str]
        label = english_label(subject)
        if label is None:
            unresolved.append(f"{uri_str}: no rdfs:label carries an 'en' "
                              f"tag or no tag at all")
            continue
        ident = derive_ident(local, label)
        if ident is None:
            unresolved.append(f"{uri_str}: local name does not end in "
                              f"the label suffix derived from {label!r}")
            continue

        comment = next(iter(graph.objects(subject, RDFS.comment)), None)
        scope_note = str(comment) if comment is not None else ""
        # Requirement 1, second half: a subject carrying rdfs:domain is a
        # property; everything else that survived the type filter above is
        # a class. E33_E41_Linguistic_Appellation carries no domain.
        is_property = (subject, RDFS.domain, None) in graph

        if is_property:
            domain_obj = next(iter(graph.objects(subject, RDFS.domain)), None)
            range_obj = next(iter(graph.objects(subject, RDFS.range)), None)
            domain_id = resolved_parent(domain_obj)
            range_id = None
            if range_obj is not None and str(range_obj) != literal_range:
                range_id = resolved_parent(range_obj)
            sub_property_of = [i for i in (
                resolved_parent(p) for p in graph.objects(subject, RDFS.subPropertyOf)
            ) if i]
            if range_id is None:
                # Requirement 6: rdfs:Literal is not a class this model
                # has, so the range comes from the first subPropertyOf
                # parent whose OWN range is known instead -- P82a inherits
                # E61 from P82 (E52 -> E61 Time Primitive), P90a inherits
                # E60 from P90 (E54 -> E60 Number). If no parent supplies
                # one, range stays absent: inventing a value here would be
                # exactly the fabrication `add_spec_additions` already
                # refuses for the property-of-property domain.
                for parent in sub_property_of:
                    parent_range = (onto.get("properties") or {}) \
                        .get(parent, {}).get("range")
                    if parent_range:
                        range_id = parent_range
                        break
            entry = {
                "id": ident,
                "full_name": f"{ident} {label}",
                "direct_name": label,
                # Requirement 7: None, not "" -- the RDFS declares no
                # inverse for any of these seven, and `_local_name`
                # already treats a falsy inverse_name as "no inverse
                # name to derive", so this is the value that keeps
                # `uri_index` from inventing an "P82ai_..." entry nobody
                # asked for.
                "inverse_name": None,
                "domain": domain_id,
                "range": range_id,
                "sub_property_of": sub_property_of,
                "scope_note": scope_note,
                "examples": [],
                "quantification": "",
                "status": "current",
                "source": "rdfs",
            }
            onto.setdefault("properties", {})[ident] = entry
        else:
            sub_class_of = [i for i in (
                resolved_parent(p) for p in graph.objects(subject, RDFS.subClassOf)
            ) if i]
            entry = {
                "id": ident,
                "full_name": f"{ident} {label}",
                "label": label,
                "sub_class_of": sub_class_of,
                "scope_note": scope_note,
                "examples": [],
                "status": "current",
                "source": "rdfs",
            }
            onto.setdefault("classes", {})[ident] = entry
        added.append(ident)

    if unresolved:
        # No silent skips: a candidate this function cannot fold in is a
        # signal the RDFS has moved in a way this derivation does not
        # cover, and swallowing it would leave a validator that quietly
        # knows less than the file it just read.
        raise ValueError(
            f"add_rdfs_additions: {len(unresolved)} RDFS declaration(s) "
            "could not be resolved to an identifier (reported, not "
            "dropped): " + "; ".join(sorted(unresolved))
        )

    # Requirement 9: `onto` was just mutated above, and this function's own
    # call to `uri_index(onto)` at the top -- needed to know what NOT to
    # add -- populated `_URI_INDEX_CACHE[id(onto)]` with the answer from
    # BEFORE that mutation. `_owned_namespaces` has no reason to change here
    # (no entry gained a `uri` field) but is cleared too, on the same
    # reasoning `uri_index` is: both are memoized on id(onto) alone, with
    # no way to know their memoized answer went stale, so the caller that
    # populated them is the only one positioned to invalidate them. Left
    # in place, a caller that resolved a URI through this `onto` before
    # calling this function -- as this function itself just did -- would
    # keep getting the pre-addition answer after it returns.
    _URI_INDEX_CACHE.drop(onto)
    _NAMESPACE_CACHE.drop(onto)

    return sorted(added)


def add_family_rdfs(onto: dict, paths) -> dict[str, dict]:
    """Give the family extension entries the URIs their own RDFS declares.

    `crm_family.json` is scraped from the Classes & Properties declaration
    pages, and four models publish no URI there at all -- CRMact, CRMba,
    FRBRoo and PRESSoo, 171 entries between them. An entry with no `uri`
    still RESOLVES, because `uri_index` also keys on the label-derived local
    name and on the bare identifier, so `crmba:B1_Built_Work` was found. What
    it could not do is make the namespace known: `_owned_namespaces` is built
    from `uri` fields, so a namespace no entry carried was foreign, and a
    MISSPELLED term in it -- `crmba:B99_gaga` -- came back `not_crm` and
    exited 0 while the same mistake in CRMsci exited 1. That is the XML/RDF
    divergence this branch already closed once, reproduced between two
    extension models.

    The namespaces cannot be guessed, which is why they are read from the
    files rather than derived from the model name. Measured, not assumed:
    CRMba is `http://www.ics.forth.gr/isl/CRMba/` in its v1.4 file and
    `http://www.cidoc-crm.org/extensions/crmba/` in the URIs it declares;
    PRESSoo is `http://www.iflastandards.info/fr/pressoo/` -- a different
    host AND path from LRMoo's `http://iflastandards.info/ns/lrm/lrmoo/`,
    down to the `www.`. Any rule that built these from the model name would
    have been confidently wrong for three models out of eleven.

    A model's namespace is the one most of its declarations share, rather
    than every namespace appearing in the file. CIDOC's own CRMact v0.2
    draft contains one malformed subject --
    `.../crmact/actP12_was_intended_to_apply_within/from` -- whose namespace
    is a property URI. Taking every namespace would make the validator claim
    ownership of that, and then report a typo under it as a real term. The
    majority rule rejects it 37 to 1 and is unanimous on the other ten files.

    Returns {model: {"namespace", "declared", "uris_filled", "added"}}.
    """
    from rdflib import Graph, RDF, RDFS, OWL, URIRef

    _CANDIDATE_TYPES = {RDFS.Class, OWL.Class, RDF.Property,
                        OWL.ObjectProperty, OWL.DatatypeProperty}
    extensions = onto.setdefault("extensions", {})
    known = set(onto["classes"]) | set(onto["properties"])
    index = uri_index(onto)
    report: dict[str, dict] = {}

    for path in sorted(Path(p) for p in paths):
        # CRMsci_v3.2.rdf -> CRMsci. The file names the model; nothing inside
        # reliably does (three of the eleven carry no xml:base at all).
        model = path.name.split("_v")[0].split(".")[0]
        graph = Graph()
        _quiet_literal_warnings()
        graph.parse(str(path), format="xml")

        subjects = {s for s, _, t in graph.triples((None, RDF.type, None))
                    if t in _CANDIDATE_TYPES and isinstance(s, URIRef)}
        if not subjects:
            report[model] = {"namespace": None, "declared": 0,
                             "uris_filled": 0, "added": []}
            continue
        counts: dict[str, int] = {}
        for subject in subjects:
            ns = _namespace_of(str(subject))
            counts[ns] = counts.get(ns, 0) + 1
        namespace = max(sorted(counts), key=lambda n: counts[n])

        filled, added = 0, []
        for subject in sorted(subjects, key=str):
            uri = str(subject)
            if _namespace_of(uri) != namespace:
                continue                      # the malformed-subject case
            local = uri[len(namespace):]
            ident, inverse = index.get(local.lower(), (None, False))
            if ident is None:
                ident, inverse = resolve_uri(onto, uri)
            # An inverse URI names the same property from the other side.
            # Storing it as THE uri would make the entry's own identity the
            # backwards one, and `_local_name` would then disagree with it.
            if ident is not None and inverse:
                continue
            if ident in known:
                continue                      # CRMbase wins any collision
            entry = extensions.get(ident) if ident else None
            if entry is not None:
                if not entry.get("uri"):
                    entry["uri"] = uri
                    filled += 1
                continue
            label = None
            for lit in graph.objects(subject, RDFS.label):
                if lit.language == "en":
                    label = str(lit)
                    break
                if lit.language is None and label is None:
                    label = str(lit)
            if not label:
                continue
            suffix = "_" + re.sub(r"\s+", "_", label.strip())
            if not (local.endswith(suffix) and len(local) > len(suffix)):
                continue
            new_id = local[: -len(suffix)].upper()
            if new_id in known or new_id in extensions:
                continue
            domain = graph.value(subject, RDFS.domain)
            entry = {
                "id": new_id,
                "status": "current",
                "label": label,
                "model": model,
                "kind": "property" if domain is not None else "class",
                "mentions": 0,
                "uri": uri,
            }
            if domain is not None:
                entry["domain"] = _family_local_id(onto, index, domain)
                rng = graph.value(subject, RDFS.range)
                if rng is not None:
                    entry["range"] = _family_local_id(onto, index, rng)
            extensions[new_id] = entry
            added.append(new_id)

        report[model] = {"namespace": namespace, "declared": len(subjects),
                         "uris_filled": filled, "added": sorted(added)}

    # Same reasoning as add_rdfs_additions: this read uri_index before
    # mutating, and entries just gained `uri` fields, which is exactly what
    # _owned_namespaces is built from.
    _URI_INDEX_CACHE.drop(onto)
    _NAMESPACE_CACHE.drop(onto)
    return report


def _family_local_id(onto: dict, index: dict, uri) -> str | None:
    """The model's identifier for a domain/range URI, or None.

    None rather than a guess: an unresolvable range is most often
    `rdfs:Literal`, which the model has no class for, and `validate_link`
    already treats an absent range as "anything goes" instead of inventing
    a constraint the source does not state.
    """
    resolved, _ = resolve_uri(onto, str(uri))
    if resolved:
        return resolved
    local = _namespace_of(str(uri))
    tail = str(uri)[len(local):]
    hit = index.get(tail.lower())
    return hit[0] if hit else None
