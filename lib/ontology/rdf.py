"""Reading RDF: triples, rdf:type as a class check, and owl:inverseOf claims.

An RDF document (Turtle, RDF/XML, JSON-LD, ...) addresses everything by
URI and needs its own reader rather than `documents.py`'s example-format
walk: `crm_rdf_links` turns triples into the same link shape the example
reader produces, `crm_rdf_class_uses` checks `rdf:type` assertions as class
names, and `crm_inverse_claims` checks `owl:inverseOf` assertions against
what the CRM actually declares. `crm_rdf_links` deliberately skips
`owl:inverseOf` triples -- `crm_inverse_claims` is the other half of that
pair, and a caller has to run both to see everything a document asserts.
"""

from pathlib import Path

from .graph import _model_view
from .uris import _namespace_of, _owned_namespaces, resolve_uri

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


def crm_rdf_class_uses(path: str | Path, onto: dict) -> list[dict]:
    """Every `rdf:type` in the document, checked as a class name.

    `crm_rdf_links` keeps the types that resolve and drops the rest, so a
    subject whose only type is misspelled looks UNTYPED, and its links land
    as `unchecked` -- which does not fail. A stale CRMsci name typed
    `S4_Observation` (v3.2 renamed it S4_Single_Observation) produced no
    finding at all and exited 0. So did `E22_Human_Made_Object`, an
    underscore where the CRM writes a hyphen, on the OBJECT end: the link
    printed `None -> None` and passed.

    That is the failure this codebase keeps rediscovering in new places --
    exit 0 on a document that looks checked -- and it is the likeliest error
    an LLM makes, because a stale or plausible-but-wrong class name is what
    outdated training data produces. A misspelled PREDICATE has been caught
    since the namespace rule landed; this is the same rule applied to the
    other half of every triple, and deliberately reuses its verdicts and its
    wording so the two read alike.

    Three verdicts, matching the predicate side:
      unknown_class -- in a namespace this model owns, names no class in it
      not_a_class   -- resolves, but to a property; `a crm:P108_has_produced`
                       is not a type, and saying "unknown" would be false
      not_crm       -- a foreign namespace, reported and not a failure, the
                       same standing rdfs:label gets as a predicate

    Shaped like the records `validate_class_labels` returns so
    `format_document_validation` renders both without knowing which reader
    produced them.
    """
    from rdflib import Graph, URIRef
    from rdflib.term import BNode

    path = Path(path)
    graph = Graph()
    _quiet_literal_warnings()
    graph.parse(str(path), format=_RDF_FORMATS.get(path.suffix.lower()))
    classes, properties = _model_view(onto)
    owned = _owned_namespaces(onto)
    pop = onto.get("property_of_property") or {}

    findings = []
    for subject, _, obj in graph.triples((None, URIRef(_RDF_TYPE), None)):
        if not isinstance(obj, URIRef):
            continue
        uri = str(obj)
        ident, _inverse = resolve_uri(onto, uri)
        where = f"_:{subject}" if isinstance(subject, BNode) else str(subject)
        if ident is not None and ident in classes:
            continue
        if ident is not None and (ident in properties or ident in pop):
            findings.append({
                "verdict": "not_a_class", "raw": uri, "path": where,
                "detail": f"{ident} is a property, not a class; rdf:type "
                          "takes a class"})
        elif _namespace_of(uri) in owned:
            findings.append({
                "verdict": "unknown_class", "raw": uri, "path": where,
                "detail": f"{uri} is in a namespace this model owns, but "
                          "names no class in it"})
        else:
            findings.append({
                "verdict": "not_crm", "raw": uri, "path": where,
                "detail": f"{uri} is not a CRM class; not checked"})
    return sorted(findings, key=lambda f: (f["path"], f["raw"]))


_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_OWL_INVERSE_OF = "http://www.w3.org/2002/07/owl#inverseOf"

# rdflib infers the parser from the suffix, and these are the ones the CRM
# world actually publishes. `.rdf` and `.owl` are RDF/XML; `.json` is treated
# as JSON-LD because a bare .json CRM file is invariably that.
_RDF_FORMATS = {".ttl": "turtle", ".turtle": "turtle", ".n3": "n3",
                ".nt": "nt", ".rdf": "xml", ".owl": "xml", ".xml": "xml",
                ".jsonld": "json-ld", ".json": "json-ld"}


def crm_rdf_links(path: str | Path, onto: dict,
                  aliases: list[dict] | None = None) -> list[dict]:
    """Every triple in an RDF document, as the link records the checker takes.

    Produces the same shape `crm_example_links` produces, so
    `validate_document` needs no knowledge of which format it was handed.

    `aliases`, when given, is a `crm_inverse_claims` result (Task 5). A
    `bridge` claim in it tells us how the document means its own predicate to
    be read, and honouring it is what lets this function check a document
    that is not written purely in CRM URIs -- a foreign predicate the
    document itself declares against a CRM property gets the same domain and
    range check every CRM predicate gets, instead of landing as `not_crm` and
    going unchecked. Only `bridge` is honoured: a `contradicted` claim is
    false, and honouring an unchecked claim would let a document define its
    way out of any error by declaring a false inverse -- the whole reason
    `crm_inverse_claims` has to run and verify the claim BEFORE this function
    is allowed to act on it. The default, `None`, leaves every existing
    caller's behaviour exactly as it was: no aliasing happens unless the
    caller opts in by supplying claims.

    A subject may carry several `rdf:type` assertions -- the CRM permits
    multiple instantiation and the models written against this repository use
    it, one core segment being both an E19 Physical Object and a CRMsci S13
    Sample. Every CRM type is kept in `subject_types`; `subject` holds the
    first for display, and the checker is given all of them.

    Predicates outside the model resolve to nothing and are still emitted,
    named by their URI. An RDF file legitimately carries rdfs:label and
    application vocabulary, and a CRM validator has no standing to reject
    them -- but dropping them silently would be indistinguishable from
    dropping a misspelled CRM predicate, which is the failure this codebase
    keeps rediscovering.

    `owl:inverseOf` triples are the one deliberate exception to that "never
    drop silently" rule, and only because this function is one half of a
    pair. This half skips them; `crm_inverse_claims` is the half that reads
    and checks them. The skip is safe exactly as long as a caller runs both
    over the same document -- which the CLI does (`validate --rdf` calls
    both and reports both) -- but nothing here enforces that pairing. A
    caller that invokes this function alone drops every `owl:inverseOf`
    claim in the document with no trace at all. Nothing today does that, but
    nothing stops a future caller from doing it either.

    Returned sorted by (path, name): `for subject, predicate, obj in graph`
    walks rdflib's internal store in whatever order its hash seed gives it,
    confirmed to differ across separate runs of the same file, and a
    validator whose findings reorder between two runs of the same input
    cannot be diffed -- the same reason `full_listing` sorts its rows.
    """
    from rdflib import Graph, URIRef
    from rdflib.term import BNode, Literal

    path = Path(path)
    graph = Graph()
    _quiet_literal_warnings()
    graph.parse(str(path), format=_RDF_FORMATS.get(path.suffix.lower()))

    # A `bridge` claim from crm_inverse_claims tells us how the document
    # means its own predicate to be read, and honouring it is what lets this
    # check a file not written purely in CRM URIs. Only `bridge` -- a
    # `contradicted` claim is false, and honouring an unchecked claim would
    # let a document define its way out of any error by declaring one.
    #
    # The direction inverts: `ex:madeBy inverseOf P108_has_produced` says
    # ex:madeBy is the OPPOSITE of forward P108, so it means P108 inverse.
    alias_map: dict[str, tuple[str, bool]] = {}
    for claim in aliases or []:
        if claim["verdict"] != "bridge":
            continue
        for near, far in ((claim["subject"], claim["object"]),
                          (claim["object"], claim["subject"])):
            if resolve_uri(onto, near)[0] is None:
                ident, inverse = resolve_uri(onto, far)
                if ident is not None:
                    alias_map.setdefault(near, (ident, not inverse))

    def node_types(node) -> list[str]:
        out = []
        for obj in graph.objects(node, URIRef(_RDF_TYPE)):
            ident, _ = resolve_uri(onto, str(obj))
            if ident:
                out.append(ident)
        return sorted(set(out))

    def where(node) -> str:
        return f"_:{node}" if isinstance(node, BNode) else str(node)

    links: list[dict] = []
    for subject, predicate, obj in graph:
        # owl:inverseOf is a statement about the vocabulary, not an instance
        # link, and `crm_inverse_claims` checks it against the model. Left
        # here it would land as `not_crm` on the predicate plus `unchecked`
        # on an untyped subject: two findings that say nothing, about a
        # triple that IS checked. Skipped here, never unreported -- the same
        # bargain rdf:type already gets.
        if str(predicate) in (_RDF_TYPE, _OWL_INVERSE_OF):
            continue
        pid, inverse = alias_map.get(str(predicate)) \
            or resolve_uri(onto, str(predicate))
        subject_types = node_types(subject)
        object_types = [] if isinstance(obj, Literal) else node_types(obj)
        links.append({
            "subject": subject_types[0] if subject_types else None,
            "subject_types": subject_types,
            "name": (pid + "i" if inverse else pid) if pid else str(predicate),
            "predicate_uri": str(predicate),
            "object": object_types[0] if object_types else None,
            "object_types": object_types,
            "path": where(subject),
            "via_property": None,
        })
    links.sort(key=lambda link: (link["path"], link["name"]))
    return links


def _not_invertible_cause(onto: dict, classes: dict, ident: str) -> str:
    """Why `ident` -- already confirmed to be in the CRM, already confirmed
    not to be a property -- has no inverse. Two different mistakes read
    alike if collapsed to one message ("not a property with an inverse"),
    and they call for different corrections, so `crm_inverse_claims` looks
    the identifier up to tell them apart instead of naming both possible
    causes every time regardless of which one actually applies.

    A property-of-property's domain is the relationship it qualifies, not a
    class -- the same fact `validate_link` reports, for the same identifiers,
    as `"not_a_class_link: its domain is the property X, not a class"` -- so
    the concept of an inverse (a property read the other direction) simply
    does not apply to it. Naming a class where a property belongs is the
    other, plainer mistake: a category error, not a subtler one.
    """
    pop = onto.get("property_of_property") or {}
    if ident in pop:
        parent = pop[ident].get("of_property")
        return (f"{ident}'s domain is the property {parent}, not a class -- "
                f"a property-of-property has no inverse (same reason "
                f"validate_link calls {ident} not_a_class_link)")
    if ident in classes:
        return f"{ident} is a class, not a property -- a class has no inverse"
    return f"{ident} is not a property with an inverse"  # unreached in practice


def crm_inverse_claims(path: str | Path, onto: dict) -> list[dict]:
    """Every `owl:inverseOf` triple, checked against what the CRM says.

    A document can assert what a property's inverse IS. Until this existed
    nothing read those assertions, so a file could state that
    P108i_was_produced_by is the inverse of P14_carried_out_by -- false --
    and every other check passed it, because an owl:inverseOf triple is not
    an instance link and the link checker has nothing to say about it.

    The rule needs no judgement: a claim is correct iff both sides resolve
    to the same identifier with opposite direction flags, which is exactly
    the pair `resolve_uri` returns.

    Two of the five verdicts do not fail the document. A file may define its
    own predicates and declare them against the CRM (`bridge`) or declare
    them against each other (`foreign`); a CRM validator has no standing
    over either. They are still named, because a `bridge` is how an
    application vocabulary is checked at all (see `crm_rdf_links`) and a
    silent pass is indistinguishable from a silent drop.

    This function is one half of a pair with `crm_rdf_links`, which SKIPS
    every `owl:inverseOf` triple rather than reporting it as an unresolved or
    unchecked link. That skip is only honest because this function reads and
    checks the very same triples -- a caller that ran `crm_rdf_links` alone
    would see those claims vanish with no trace. The CLI (`validate --rdf`)
    runs both and reports both; nothing enforces that pairing structurally,
    so a future caller of `crm_rdf_links` on its own must re-supply this
    function itself, not assume the skip is free.
    """
    from rdflib import Graph, URIRef

    path = Path(path)
    graph = Graph()
    _quiet_literal_warnings()
    graph.parse(str(path), format=_RDF_FORMATS.get(path.suffix.lower()))
    classes, properties = _model_view(onto)

    claims = []
    for subject, _, obj in graph.triples((None, URIRef(_OWL_INVERSE_OF), None)):
        left, right = str(subject), str(obj)
        lid, linv = resolve_uri(onto, left)
        rid, rinv = resolve_uri(onto, right)
        known = [i for i in (lid, rid) if i is not None]

        if not known:
            verdict, detail = "foreign", (
                "neither side is in the CRM -- an application declaring its "
                "own vocabulary against itself, which is not ours to check")
        # Invertibility of whatever CRM side there is comes BEFORE the bridge
        # test, not after. Ordered the other way, a claim naming a CRM CLASS
        # against a foreign name -- `E22_Human-Made_Object owl:inverseOf
        # ex:madeBy` -- matched `bridge` on the strength of one side being
        # unresolved and was never asked whether the other side has an
        # inverse at all. It exited 0, while the identical falsehood with a
        # CRM property opposite it exited 1. Worse, a bridge is HONOURED:
        # ex:madeBy was aliased to E22 inverse, and the report named a
        # property `E22i` that exists in neither the model nor the document.
        elif not_prop := list(dict.fromkeys(
                i for i in (lid, rid) if i is not None and i not in properties)):
            verdict, detail = "not_invertible", "; ".join(
                _not_invertible_cause(onto, classes, i) for i in not_prop)
        elif lid is None or rid is None:
            # Exactly one side is CRM and it IS an invertible property, which
            # is the only shape worth honouring: the document telling us how
            # to read its own predicate. crm_rdf_links aliases these.
            crm_side = lid or rid
            verdict, detail = "bridge", (
                f"declares a name outside the CRM as the inverse of "
                f"{crm_side}")
        elif lid != rid:
            verdict, detail = "contradicted", (
                f"{lid} and {rid} are different properties; the CRM makes "
                f"neither the inverse of the other")
        elif linv == rinv:
            verdict, detail = "contradicted", (
                f"both sides name {lid} in the same direction, so the claim "
                f"makes it its own inverse")
        else:
            verdict, detail = "ok", f"{lid}, in both directions"

        claims.append({"subject": left, "object": right,
                       "verdict": verdict, "detail": detail})
    return sorted(claims, key=lambda c: (c["subject"], c["object"]))
