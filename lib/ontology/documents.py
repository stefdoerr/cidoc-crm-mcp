"""Checking a whole document, and the house XML example-format reader.

`validate_link` decides one triple; this module decides a *document*,
which starts one step earlier -- resolving what a document's own element
names and `in_class` declarations mean before there is a triple to check
at all. `crm_example_links`/`crm_example_class_uses` read the published
CIDOC CRM example XML format (labels as element names, classes named in
`in_class` text); `validate_document` and `validate_class_labels` turn
either that reader's or the RDF reader's links into verdicts. It is about a
document's report, not a single link, which is why it sits here rather
than in `validate.py` even though it is the shared checker both readers
feed.
"""

import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from .graph import _model_view, required_properties
from .uris import _namespace_of, _owned_namespaces
from .validate import _property_candidates, validate_link

# ---- checking a document as written ---------------------------------------
#
# validate_link takes a triple, which means the caller has already decided
# what each element name means. That decision is where an error hides. A
# modelling agent given this tool extracted "105 class-property-class shapes"
# from its own finished XML, resolved each name to an identifier as it went,
# and validated the identifiers -- so `changed_ownership_by`, which is not a
# CRM label at all, was silently read as P24 during extraction and reached
# the validator already corrected. It shipped four times. An earlier run
# without the tool, checking element names against real labels with a
# hand-written script, caught the same string and fixed it.
#
# Giving it a validator therefore made its checking narrower. The remedy is
# for the tool to read the artifact rather than a transcription of it.

# Elements of the published example format that are not properties. Listed
# rather than skipped-by-default: an unrecognised name is the whole point of
# this check, so the exemptions are enumerated and reported, never inferred.
_STRUCTURAL_ELEMENTS = frozenset({"CRM_Entity", "in_class", "value", "unit"})

_IN_CLASS = re.compile(r"\s*([A-Za-z]+\d+(?:\.\d)?)\s*[:.]")


def load_xml(xml_path: str | Path) -> ET.Element:
    """Parse one example-format document, once.

    Both readers below used to call `ET.parse` themselves, so validating a
    document with `--completeness` walked the same file three times. Each
    takes an already-parsed root element in place of a path, so a caller
    needing more than one parses here.
    """
    return ET.parse(str(xml_path)).getroot()


def _as_root(source) -> ET.Element:
    """`source` is a path to parse or a root element already parsed."""
    return source if isinstance(source, ET.Element) else load_xml(source)


def _indexed_children(node: ET.Element):
    """(child, index suffix) for each child, indexed only where its tag
    repeats among its siblings -- so a tag that appears once keeps the bare
    path it always had.

    Shared by both walkers below because they describe the same tree. Each
    used to carry its own copy of this rule, and the copies disagreed: one
    counted `in_class` among the siblings and the other did not, and they
    rooted their walks in two different places entirely, so a class-label
    finding and a link finding on the same element could never be matched up.
    """
    repeated = Counter(c.tag for c in node)
    seen: Counter = Counter()
    for child in node:
        seen[child.tag] += 1
        yield child, (f"[{seen[child.tag]}]" if repeated[child.tag] > 1 else "")


def crm_example_links(source) -> list[dict]:
    """Every parent-class / element-name / child-class link in a document
    written in the published CIDOC CRM example format.

    That format (crm_amol_1.xml, crm_clayton1.xml) carries no identifiers: a
    record is a `CRM_Entity` whose `in_class` names its class, and each
    property is an ELEMENT NAMED AFTER THE PROPERTY LABEL, in whichever
    direction the nesting runs. So `is_documented_in` is P70 read backwards,
    and the only way to know which property an element means is to look at
    the classes on either side of it.
    """
    root = _as_root(source)

    def class_of(node: ET.Element) -> str | None:
        text = node.findtext("in_class")
        found = _IN_CLASS.match(text) if text else None
        return found.group(1) if found else None

    links: list[dict] = []

    def walk(node: ET.Element, parent_class: str | None, path: str,
             parent_property: str | None = None) -> None:
        # `path` is node IDENTITY, not decoration: document_completeness
        # counts instances by it, and a finding names the element by it. This
        # format nests by element name, so eight <has_dimension> children of
        # one node all produced one string and were counted as one node --
        # "1 of 1" where the truth was "8 of 8". See _indexed_children.
        for child, nth in _indexed_children(node):
            if child.tag == "in_class":
                continue
            child_class = class_of(child)
            here = f"{path}/{child.tag}{nth}"
            if child.tag not in _STRUCTURAL_ELEMENTS:
                links.append({"subject": parent_class, "name": child.tag,
                              "object": child_class, "path": here,
                              # What this link actually hangs off. A property
                              # element with no in_class carries a literal, so
                              # anything nested inside it qualifies THE
                              # PROPERTY, not the class two levels up. Both
                              # published examples type their notes this way
                              # -- <has_note>text<has_type>Statement</...> --
                              # meaning P3.1, and inheriting the grandparent
                              # silently turned that into P2: amol asserts a
                              # silk textile "has type Statement", and a model
                              # written from it asserted a bronze vessel "has
                              # type Absence of evidence" 21 times. The link
                              # was legal, so the checker passed it.
                              "via_property": parent_property})
            # a property element with a class of its own re-roots the subject;
            # one without a class is a literal, and its children qualify it
            nested_property = None if child_class else (
                child.tag if child.tag not in _STRUCTURAL_ELEMENTS else parent_property)
            walk(child, child_class or parent_class, here, nested_property)

    # From the root, not once per `root.findall("CRM_Entity")`. That loop
    # rooted every record at `CRM_Entity[<its class>]` with no occurrence
    # index, so a document holding several records of one class gave them all
    # the same path -- and with it the same node identity. Six of the eight
    # models in this repository do that; crm_houmuwu.xml has fourteen E31
    # records that counted as one. CRM_Entity is a structural element, so
    # walking it emits no link of its own; a root child that is NOT one is now
    # walked and reported rather than silently skipped.
    walk(root, None, "")
    return links


def validate_document(onto: dict, links: list[dict]) -> dict:
    """Verdict every link, keeping unresolvable NAMES distinct from illegal ones.

    The two failures are different and a reader must be able to tell them
    apart: an illegal link uses a real property in a place the CRM forbids,
    while an unresolved name is not a property at all and no amount of
    reasoning about domain and range applies to it.
    """
    findings: list[dict] = []
    for link in links:
        # A predicate that does not resolve is one of two different things,
        # told apart by NAMESPACE rather than by how close the spelling
        # looks to a real property. A predicate in a FOREIGN namespace --
        # rdfs:label, a Dublin Core term, an application's own vocabulary --
        # is legitimately outside the CRM, and a CRM validator has no
        # standing to reject it: `not_crm`, and it does not fail the check.
        # A predicate in a namespace this model OWNS is asserting, by its
        # own URI, to BE one of its terms -- `crm:was_produced_by` claims to
        # be CIDOC CRM, and it is not one (P108i's real form carries the
        # `P108i_` prefix) -- so that is a misspelling, not outside
        # vocabulary, and gets `unknown_name` instead, matching what the XML
        # reader would call the identical mistake. Folding this case into
        # `not_crm` -- which is what this guard did before it checked
        # namespace at all -- meant a misspelled CRM property name exited 0
        # under `--rdf` and 1 under `--xml`; see test_rdf.py for the
        # round-trip fixture that found the gap between the two readers.
        if link.get("predicate_uri") and not _property_candidates(
                onto, link["name"]):
            if _namespace_of(link["predicate_uri"]) in _owned_namespaces(onto):
                findings.append({**link, "verdict": "unknown_name",
                                 "detail": f"{link['predicate_uri']} is in a "
                                           "namespace this model owns, but "
                                           "names no property in it"})
            else:
                findings.append({**link, "verdict": "not_crm",
                                 "detail": f"{link['predicate_uri']} is not "
                                           "a CRM property; not checked"})
            continue
        if not link.get("subject"):
            findings.append({**link, "verdict": "unchecked",
                             "detail": "no class on the subject end"})
            continue
        # A literal-valued property (P3 has note, P90 has value) carries text,
        # not a nested record, so there is no object class to read. Check the
        # domain anyway rather than skipping the link: the name can still be
        # wrong and the subject can still be the wrong class for it, and those
        # are exactly the two failures this pass exists to find. Reporting 55
        # of these as "unchecked" buried the 11 real findings underneath them.
        # The CRM permits multiple instantiation, so a node may satisfy a
        # property's domain or range through any of its types. Judging only
        # the first would fail correct models -- Da Yu ding types one segment
        # as both E19 Physical Object and CRMsci S13 Sample.
        #
        # BOTH ends, which is the whole point and was half-implemented once:
        # the loop below iterated subject types only, while `crm_rdf_links`
        # emitted `object_types` that nothing read. The same segment fails as
        # an OBJECT that passes as a subject, and since rdf:type order is
        # arbitrary the outcome depended on which type sorted first --
        # `E12, E22` as the object of P108_has_produced reported "E12 is not
        # a E24" and exited 1 on a sound model.
        #
        # A literal object leaves `object_types` empty and `object` None, so
        # the fallback yields [None] and validate_link checks the domain
        # alone, exactly as before. The XML reader sets neither key, so it
        # gets one subject and one object and takes the identical path.
        subject_candidates = link.get("subject_types") or [link["subject"]]
        object_candidates = link.get("object_types") or [link.get("object")]
        result = None
        for subject_type in subject_candidates:
            for object_type in object_candidates:
                attempt = validate_link(onto, subject_type, link["name"],
                                        object_type)
                if result is None or attempt["legal"]:
                    result = attempt
                    if attempt["legal"]:
                        # Name the types that carried it, but only where there
                        # was a choice -- on a single-typed end the answer adds
                        # nothing and clutters every ordinary finding.
                        if len(subject_candidates) > 1:
                            attempt["via_type"] = subject_type
                        if len(object_candidates) > 1:
                            attempt["via_object_type"] = object_type
                        break
            if result is not None and result["legal"]:
                break
        # Order matters. A legal reading wins over every other verdict: six of
        # the sixteen property-of-property labels collide with a real property
        # name -- "has type" is P2's direct name AND P3.1's label -- so testing
        # for a property-of-property candidate first reported all 63 sound
        # has_type links as unrepresentable.
        if link.get("via_property"):
            # Legal by the classes on either side, and not what the document
            # means: the subject here is the enclosing PROPERTY, which the CRM
            # models with a property-of-property (P3.1 for a note's type) and
            # this format has no way to write.
            findings.append({**link, "verdict": "attached_to_property",
                             "detail": f"nested inside {link['via_property']!r}, "
                                       "which carries a literal -- this qualifies "
                                       "that property, not "
                                       f"{link['subject']}; the CRM wants a "
                                       "property-of-property and the format "
                                       "cannot write one"})
        elif result["legal"] and result.get("ambiguous"):
            # Legal, but the document does not say which property it means.
            # Folding this into "ok" lost it entirely: `assigned` between an
            # E15 and an E42 is P37 or P141, and this format writes property
            # LABELS as element names, so the file cannot express the
            # difference. Reported, and not a failure -- the fix is not in
            # the document.
            findings.append({**link, "verdict": "ambiguous",
                             "detail": " or ".join(result["ambiguous"])
                             + " both fit; the element name cannot distinguish them"})
        elif result["legal"]:
            findings.append({**link,
                             "verdict": "ok" if link.get("object") else "ok_literal",
                             "detail": (result["resolved"] or "")
                             + (f" via {result['via_type']}"
                                if result.get("via_type") else "")
                             + (f" onto {result['via_object_type']}"
                                if result.get("via_object_type") else "")})
        # A real construct the format cannot carry is not a misspelling, and
        # conflating them costs the reader the one piece of information that
        # tells them which fix applies.
        elif any(c.get("legal") is None for c in result.get("candidates") or []):
            findings.append({**link, "verdict": "not_a_class_link",
                             "detail": next(c["reason"] for c in result["candidates"]
                                            if c.get("legal") is None)})
        elif result.get("error", "").startswith("no property matches"):
            findings.append({**link, "verdict": "unknown_name",
                             "detail": f"{link['name']!r} is not a CRM property label"})
        elif result.get("error"):
            findings.append({**link, "verdict": "unknown_class",
                             "detail": result["error"]})
        elif not result["legal"]:
            reasons = "; ".join(c["reason"] for c in result["candidates"])
            findings.append({**link, "verdict": "illegal", "detail": reasons})
        else:
            findings.append({**link, "verdict": "illegal",
                             "detail": "no legal reading"})
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["verdict"]] = counts.get(f["verdict"], 0) + 1
    return {"links": len(findings), "counts": counts, "findings": findings,
            "structural_elements_skipped": sorted(_STRUCTURAL_ELEMENTS)}


# ---- does this document pass? ---------------------------------------------
#
# One rule, in one place. It used to be written out four times -- the two
# exit-code expressions in search.py and the two verdict lines in
# mcp_server.py -- and they had already drifted once: `not_a_class_link` was
# missing from the RDF rule, and the comment recording the repair says it
# "was omitted from this rule only because the verdict predates the rule".
# Four copies is how a verdict predates a rule.

_FAILING_LINKS = {
    # Wrong wherever it appears.
    "both": ("illegal", "unknown_name", "unknown_class"),
    # RDF addresses everything by URI, so a class label cannot be malformed
    # and a property-of-property cannot be smuggled in by nesting.
    "xml": ("malformed", "attached_to_property"),
    # The house XML format cannot WRITE a property-of-property link, so
    # failing a document for one names a limitation of the format that its
    # author cannot fix. RDF can write one -- it is an ordinary triple -- so
    # there the same finding is a plain modelling error with a fix available,
    # and a check that exits 0 on it is not checking.
    "rdf": ("not_a_class_link",),
}

# Neither of these fails a document, and for the same reason in both halves
# of a triple: `not_crm` is a foreign term this validator has no standing
# over, and `label_mismatch` is a retired name or a role qualifier, which the
# tool cannot tell apart and must not fail on. Everything else in
# `class_labels` is a class the document got wrong.
_TOLERATED_CLASS_VERDICTS = frozenset({"label_mismatch", "not_crm"})

# A claim the CRM does not make. `bridge` and `foreign` are a document
# declaring its own vocabulary and are not ours to reject.
_FAILING_CLAIMS = frozenset({"contradicted", "not_invertible"})


def document_failures(report: dict, reader: str) -> list[str]:
    """Why this document fails, phrased for a reader; empty means it passes.

    `reader` is "xml" or "rdf" and decides exactly one thing -- whether
    `not_a_class_link` fails -- for the reason given on `_FAILING_LINKS`.
    Everything else is shared, including both halves of the triple: link
    verdicts live in `counts`, class verdicts in `class_labels` (an rdf:type
    is not a link and is counted separately), and `owl:inverseOf` claims in
    `inverse_claims`, which only an RDF report carries.

    `not_crm` and `unchecked` appear in no list here, deliberately. They mean
    "not examined", not "fine": a foreign predicate is outside this
    validator's authority, and an untyped subject was never checked at all,
    which is a different thing from having been checked and found legal.
    Neither is the document's error to answer for.
    """
    if reader not in ("xml", "rdf"):
        raise ValueError(f"reader must be 'xml' or 'rdf', not {reader!r}")

    counts = report.get("counts") or {}
    reasons = []
    for verdict in _FAILING_LINKS["both"] + _FAILING_LINKS[reader]:
        if counts.get(verdict):
            reasons.append(f"{counts[verdict]} {verdict.replace('_', ' ')}")

    bad_classes = [f for f in report.get("class_labels") or []
                   if f["verdict"] not in _TOLERATED_CLASS_VERDICTS]
    if bad_classes:
        reasons.append(f"{len(bad_classes)} bad class "
                       f"({', '.join(sorted({f['verdict'] for f in bad_classes}))})")

    bad_claims = [c for c in report.get("inverse_claims") or []
                  if c["verdict"] in _FAILING_CLAIMS]
    if bad_claims:
        reasons.append(f"{len(bad_claims)} false owl:inverseOf claim "
                       f"({', '.join(sorted({c['verdict'] for c in bad_claims}))})")
    return reasons


def document_completeness(onto: dict, links: list[dict]) -> list[dict]:
    """What the CRM expects a typed node to carry, that this document omits.

    This is guidance, not validation, and the distinction is the CRM's own,
    not house style invented for this tool. The specification says so in as
    many words (crm732#s0037, "Property Quantifiers"):

        "Quantifiers for properties are provided for the purpose of semantic
        clarification only, and should not be treated as implementation
        recommendations. The CIDOC CRM has been designed to accommodate
        alternative opinions and incomplete information, and therefore all
        properties should be implemented as optional and repeatable for
        their domain and range ("many to many (0,n:0,n)"). Therefore, the
        term "cardinality constraints" is avoided here, as it typically
        pertains to implementations."

    A property the CRM quantifies `necessary` -- "many to one, necessary
    (1,1:0,n)" for P108 on E12, in the same table -- is a claim about the
    CONCEPT: an E12 Production is not fully described without naming what it
    produced. It is not a claim about any one document, which may legitimately
    record a partial account, an in-progress catalogue entry, or a deliberate
    omission (the specification's own "incomplete information"). So a node
    missing a necessary property is exactly the gap `required_properties`
    already computes -- `is_required` reads the same string -- and this
    function reports it as a finding a reader may want to act on, never as an
    error: it does not, and given the passage above must not, affect
    `validate_document`'s verdicts or search.py's exit code.

    For the same reason there is no "too many" counterpart. A quantifier's
    upper bound ("many to ONE") reads, on first glance, like a limit worth
    flagging when a document repeats a property past it. The specification
    forbids that reading as directly as it forbids failing on the lower
    bound: quantifiers are "for the purpose of semantic clarification only",
    every property "should be implemented as ... repeatable", and the text
    names "cardinality constraints" itself as the term being avoided. A
    repetition check would invent, in code, exactly the constraint the
    passage disclaims in prose -- so it is not implemented here, and should
    not be added later without revisiting this passage first.

    A node's identity is its link records' `path` field -- the only identity
    both readers supply (the XML reader an element path, the RDF reader a
    subject URI or blank-node label) -- and its classes come from
    `subject_types` when present, else `subject`, the same fallback
    `validate_document` uses for multiply-instantiated nodes. A property
    counts as stated under ANY name `_property_candidates` resolves to that
    id, not by comparing the raw string in `link["name"]`: a document may
    write `P108` or `has produced` for the same property, and a document that
    stated it under the other spelling is not the gap this exists to find.

    Returns one record per (class, property) actually missing from at least
    one instance -- a pair fully covered everywhere it applies is not a
    finding and is not returned at all -- with `missing` (instances lacking
    it) out of `instances` (instances of that class the property applies
    to), sorted by `(class_id, property_id)` so the CLI's output is stable.
    """
    nodes: dict[object, dict] = {}
    for link in links:
        subject = link.get("subject")
        if not subject:
            continue
        node = nodes.setdefault(link.get("path"),
                                {"classes": set(), "stated": set()})
        node["classes"].update(link.get("subject_types") or [subject])
        for prop_id, _inverse in _property_candidates(onto, link.get("name")):
            node["stated"].add(prop_id)

    aggregate: dict[tuple[str, str], dict] = {}
    for node in nodes.values():
        for class_id in node["classes"]:
            for req in required_properties(onto, class_id):
                key = (class_id, req["id"])
                record = aggregate.setdefault(key, {
                    "class_id": class_id, "property_id": req["id"],
                    "property_name": req["name"], "missing": 0,
                    "instances": 0})
                record["instances"] += 1
                if req["id"] not in node["stated"]:
                    record["missing"] += 1

    findings = [r for r in aggregate.values() if r["missing"]]
    findings.sort(key=lambda r: (r["class_id"], r["property_id"]))
    return findings


def crm_example_class_uses(source) -> list[dict]:
    """Every `in_class` declaration in the document, id AND label.

    `crm_example_links` reads only the identifier out of these and throws the
    label away, so a document could say `E22: Utter Nonsense Here` and
    validate perfectly clean. That is not hypothetical: both published
    examples carry RETIRED labels -- `E22: Man-Made Object` (current:
    Human-Made Object) and `E42: Object Identifier` (current: Identifier) --
    and a modeller following them propagates names the standard dropped,
    silently, because the id is right and the id is all anything checked.
    """
    root = _as_root(source)
    uses: list[dict] = []

    def walk(node: ET.Element, path: str) -> None:
        # Literally the same rule as crm_example_links, now that both call
        # _indexed_children -- see there for what two copies of it cost.
        for child, nth in _indexed_children(node):
            if child.tag == "in_class" and (child.text or "").strip():
                raw = child.text.strip()
                found = _IN_CLASS.match(raw)
                label = raw[found.end():].strip() if found else ""
                uses.append({"id": found.group(1) if found else None,
                             "label": label, "raw": raw, "path": path})
            walk(child, f"{path}/{child.tag}{nth}")

    walk(root, "")
    return uses


def validate_class_labels(onto: dict, uses: list[dict]) -> list[dict]:
    """Findings for class declarations whose label does not match the model.

    Three outcomes, kept apart:
      * `malformed`   -- no identifier could be read at all ("E:55")
      * `unknown_class` -- the id resolves to nothing
      * `label_mismatch` -- the id is real and the label is not the current one

    A stale label is reported, not corrected: it is usually a name the
    standard used to carry, and the reader has to decide whether they are
    quoting an old edition on purpose.
    """
    classes, properties = _model_view(onto)
    findings: list[dict] = []
    seen: set[tuple] = set()
    for use in uses:
        key = (use["raw"], use["path"])
        if key in seen:
            continue
        seen.add(key)
        if not use["id"]:
            findings.append({**use, "verdict": "malformed",
                             "detail": "no identifier could be read"})
            continue
        entry = classes.get(use["id"]) or properties.get(use["id"])
        if entry is None:
            findings.append({**use, "verdict": "unknown_class",
                             "detail": f"{use['id']} resolves to nothing"})
            continue
        current = (entry.get("label") or entry.get("direct_name") or "").strip()
        if use["label"] and current and use["label"].lower() != current.lower():
            # Two different things look the same here and cannot be told
            # apart without a version history the corpus does not carry:
            #   * a RETIRED name -- "E22: Man-Made Object", which v7 renamed
            #     Human-Made Object, and which both published examples use
            #   * a ROLE QUALIFIER -- "E55: Appellation Type", meaning an E55
            #     serving as the type of an appellation, which the format has
            #     no other slot for
            # A containment rule does not separate them: E42's retired name
            # "Object Identifier" ends in its current one, "Identifier",
            # exactly as a qualifier would. So it is reported as a mismatch,
            # described as both possibilities, and does NOT fail the check --
            # failing a document over a distinction the tool cannot make
            # would be worse than reporting it.
            findings.append({**use, "verdict": "label_mismatch",
                             "detail": f"{use['id']} is named {current!r} in the "
                                       f"model; document says {use['label']!r} "
                                       "-- a retired name, or a role qualifier"})
    return findings
