"""Parse the FORTH CIDOC CRM specification XML into a concept graph.

Everything here reads `cidoc_crm_v7.1.3.xml` and produces the
{version, release_date, classes, properties, ...} dict the rest of the
package builds on: stripping the HTML-escaped scope notes and examples,
reading the id-attribute-carried class/property relationships, and folding
in the nested propertyOfProperty declarations. Nothing here knows about the
family extensions, the derived hierarchy queries, or any other source --
this module's whole job is turning the XML into that one dict.
"""

import re
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(s: str | None) -> str:
    """Drop tags first, then unescape HTML entities and collapse whitespace.

    ElementTree already unescapes once during parsing, so structural tags
    are real but content-meant-to-display (like KML) is still escaped.
    Stripping tags first preserves escaped content meant to appear as text.
    """
    if not s:
        return ""
    return _WS.sub(" ", unescape(_TAG.sub(" ", s))).strip()


def _ids(node: ET.Element, tag: str) -> list[str]:
    """Target ids of every `tag` child, read from the `id` attribute."""
    ids = [c.get("id") for c in node.findall(tag)]
    return [i for i in ids if i]


def _one_id(node: ET.Element, tag: str) -> str | None:
    found = _ids(node, tag)
    return found[0] if found else None


def _examples(node: ET.Element) -> list[str]:
    """Extract examples as a list by splitting on <li> boundaries before stripping HTML."""
    raw = node.findtext("examples")
    if not raw:
        return []
    # Split on <li> tags to separate list items
    items = re.split(r"<li[^>]*>", raw)
    # Strip HTML from each item and filter out empty ones
    result = [strip_html(item) for item in items]
    return [item for item in result if item]


def _properties_of_property(node: ET.Element, parent_id: str) -> dict:
    """Nested <propertyOfProperty> declarations, keyed by their own id.

    The XML nests these inside the property they qualify, and
    `root.findall(".//property")` never descends into them, so all 16 were
    absent from data/ontology.json and `concept P14.1` answered "No such
    concept" for a property the standard declares with its own label and
    range.

    No `domain` key is written because there is none to write: the domain is
    the parent relationship itself, which the property's own first-order
    logic states directly -- P14(x,y,z) => [P14(x,y) AND E55(z)]. Inventing
    a class-valued domain would be a fabricated constraint, the same error
    `is_required` refuses to make for the scraped family declarations.

    Keyed on the `id` attribute and generic over any `.N` suffix, not `.1`:
    CRMarchaeo's AP13.2 is attested 8 times in the issue pages and minutes,
    and drops into this bucket unchanged if the family scrape ever supplies
    it.
    """
    out = {}
    for pop in node.findall("propertyOfProperty"):
        pid = pop.get("id")
        if not pid:
            continue
        out[pid] = {
            "id": pid,
            "of_property": parent_id,
            "label": pop.findtext("labelText") or "",
            "range": _one_id(pop, "range"),
            "status": "current",
        }
    return out


def _check_declared_counts(root: ET.Element, classes: dict, properties: dict) -> None:
    """The XML header states its own counts; hold the parse to them.

    Same reasoning as `verify_collection`, which exists because a truncated
    build left 5,461 of 8,855 vectors in place with every other signal
    healthy. A source that describes itself should be checked against
    itself, not trusted.
    """
    for attr, parsed in (("classes", len(classes)), ("properties", len(properties))):
        declared = root.get(attr)
        if declared is None:
            continue
        if int(declared) != parsed:
            raise ValueError(
                f"{attr}: XML header declares {declared}, parsed {parsed}"
            )


def parse_ontology(xml_path: str | Path) -> dict:
    """Parse the CRM XML into {version, release_date, classes, properties, historical}."""
    root = ET.parse(str(xml_path)).getroot()

    classes = {}
    for node in root.findall(".//class"):
        cid = node.get("id")
        classes[cid] = {
            "id": cid,
            "full_name": node.findtext("fullName") or cid,
            "label": node.findtext("className") or "",
            "sub_class_of": _ids(node, "subClassOf"),
            "scope_note": strip_html(node.findtext("scopeNote")),
            "examples": _examples(node),
            "status": "current",
        }

    properties = {}
    property_of_property: dict[str, dict] = {}
    for node in root.findall(".//property"):
        pid = node.get("id")
        properties[pid] = {
            "id": pid,
            "full_name": node.findtext("fullName") or pid,
            "direct_name": node.findtext("directName") or "",
            "inverse_name": node.findtext("inverseName") or "",
            "domain": _one_id(node, "domain"),
            "range": _one_id(node, "range"),
            "sub_property_of": _ids(node, "subPropertyOf"),
            "scope_note": strip_html(node.findtext("scopeNote")),
            "examples": _examples(node),
            "quantification": strip_html(node.findtext("quantification")),
            "status": "current",
        }
        property_of_property.update(_properties_of_property(node, pid))

    _check_declared_counts(root, classes, properties)

    return {
        "version": root.get("version"),
        "release_date": root.get("releaseDate"),
        "classes": classes,
        "properties": properties,
        "property_of_property": property_of_property,
        "historical": {},
        "extensions": {},
    }
