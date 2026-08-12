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


def crm_example_links(xml_path: str | Path) -> list[dict]:
    """Every parent-class / element-name / child-class link in a document
    written in the published CIDOC CRM example format.

    That format (crm_amol_1.xml, crm_clayton1.xml) carries no identifiers: a
    record is a `CRM_Entity` whose `in_class` names its class, and each
    property is an ELEMENT NAMED AFTER THE PROPERTY LABEL, in whichever
    direction the nesting runs. So `is_documented_in` is P70 read backwards,
    and the only way to know which property an element means is to look at
    the classes on either side of it.
    """
    root = ET.parse(str(xml_path)).getroot()

    def class_of(node: ET.Element) -> str | None:
        text = node.findtext("in_class")
        found = _IN_CLASS.match(text) if text else None
        return found.group(1) if found else None

    links: list[dict] = []

    def walk(node: ET.Element, parent_class: str | None, path: str,
             parent_property: str | None = None) -> None:
        # An occurrence index, but only where a tag repeats among its
        # siblings. This format nests by element name, so eight <has_dimension>
        # children of one node all produced the string
        # ".../is_composed_of/is_composed_of/has_dimension" -- one path for
        # eight different nodes. A reader told a link is wrong "at
        # .../has_dimension" could not tell which of the eight, the same
        # unfollowable-advice failure this codebase has fixed twice
        # elsewhere; and `document_completeness`, which uses `path` as node
        # identity, counted the eight as one and reported "1 of 1" where the
        # truth was "8 of 8".
        #
        # Indexed only when ambiguous, so a tag that appears once keeps the
        # path it always had. Most paths are unaffected.
        repeated = Counter(c.tag for c in node if c.tag != "in_class")
        seen: Counter = Counter()
        for child in node:
            if child.tag == "in_class":
                continue
            child_class = class_of(child)
            seen[child.tag] += 1
            nth = f"[{seen[child.tag]}]" if repeated[child.tag] > 1 else ""
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

    for record in root.findall("CRM_Entity"):
        walk(record, class_of(record), f"CRM_Entity[{class_of(record)}]")
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


def crm_example_class_uses(xml_path: str | Path) -> list[dict]:
    """Every `in_class` declaration in the document, id AND label.

    `crm_example_links` reads only the identifier out of these and throws the
    label away, so a document could say `E22: Utter Nonsense Here` and
    validate perfectly clean. That is not hypothetical: both published
    examples carry RETIRED labels -- `E22: Man-Made Object` (current:
    Human-Made Object) and `E42: Object Identifier` (current: Identifier) --
    and a modeller following them propagates names the standard dropped,
    silently, because the id is right and the id is all anything checked.
    """
    root = ET.parse(str(xml_path)).getroot()
    uses: list[dict] = []

    def walk(node: ET.Element, path: str) -> None:
        # Indexed the same way crm_example_links indexes, and it has to be
        # the same rule: both walkers describe the same tree, and a reader
        # who sees a class-label finding at one path and a link finding at
        # another has no way to tell they are the same element.
        repeated = Counter(c.tag for c in node)
        seen: Counter = Counter()
        for child in node:
            text = (child.findtext("in_class") or "").strip() if len(child) else ""
            if child.tag == "in_class" and (child.text or "").strip():
                raw = child.text.strip()
                found = _IN_CLASS.match(raw)
                label = raw[found.end():].strip() if found else ""
                uses.append({"id": found.group(1) if found else None,
                             "label": label, "raw": raw, "path": path})
            seen[child.tag] += 1
            nth = f"[{seen[child.tag]}]" if repeated[child.tag] > 1 else ""
            walk(child, f"{path}/{child.tag}{nth}")

    walk(root, "")
    return uses


def validate_class_labels(onto: dict, uses: list[dict]) -> list[dict]:
    """Findings for class declarations whose label does not match the model.

    Three outcomes, kept apart:
      * `malformed`   -- no identifier could be read at all ("E:55")
      * `unknown_class` -- the id resolves to nothing
      * `stale_label` -- the id is real and the label is not the current one

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
